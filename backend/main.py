import os
import csv
import io
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import init_db, get_connection
from models import InboundMessage, EscalationUpdate
import claude_client
import sources_config
import gmail_poller
import slack_poller
import router as complaint_router
from departments import DEPARTMENTS, get_department


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[Server] Ready.")
    # Start background pollers
    gmail_task = asyncio.create_task(gmail_poller.poll_gmail_forever())
    slack_task = asyncio.create_task(slack_poller.poll_slack_forever())
    yield
    gmail_task.cancel()
    slack_task.cancel()


app = FastAPI(title="Plum Escalation Management API", version="1.0", lifespan=lifespan)

# Department auto-routing based on issue category
DEPARTMENT_MAP = {
    "Claim Processing":    "Claims Team",
    "Health ID":           "Operations Team",
    "Cashless Facility":   "TPA & Hospital Desk",
    "Document Upload":     "Operations Team",
    "Data Correction":     "Data & Finance Ops",
    "Policy Renewal":      "Renewals Team",
    "IRDAI/Legal Threat":  "Legal & Compliance",
    "Social Media Threat": "PR & Communications",
    "Training Request":    "Customer Success",
    "Other":               "Account Management",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# (startup handled by lifespan above)


# ─────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "service": "Plum Escalation API"}


# ─────────────────────────────────────────────
# Webhook — receive one message from n8n / Make.com
# ─────────────────────────────────────────────
@app.post("/webhook/ingest", status_code=201)
def ingest(msg: InboundMessage):
    import json as _json

    # 1. Claude AI — classify & enrich
    enriched = claude_client.enrich(
        source_channel=msg.source_channel,
        sender_name=msg.sender_name or "",
        sender_contact=msg.sender_contact or "",
        raw_message=msg.raw_message,
    )

    # 2. Complaint router — department routing (hybrid rule + AI)
    routing = complaint_router.route_complaint(msg.raw_message, use_ai=True)
    dept_info = get_department(routing["primary_dept_id"])
    assigned_department = dept_info["name"]

    # 3. SLA deadline — use routing dept SLA hours as primary source
    try:
        base_time = datetime.fromisoformat(msg.received_at.replace("Z", "+00:00"))
    except Exception:
        base_time = datetime.now(timezone.utc)

    sla_hours = dept_info.get("sla_hours") or {"High": 4, "Medium": 24, "Low": 72}.get(enriched["urgency"], 24)
    sla_deadline = (base_time + timedelta(hours=sla_hours)).isoformat()

    # 4. Insert into SQLite with full routing data
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO escalations (
            source_channel, source_message_id, received_at,
            sender_name, sender_contact, raw_message,
            is_escalation, account_name, issue_category,
            ai_summary, urgency, priority_score,
            action_needed, sentiment, assigned_department,
            sla_deadline_at,
            primary_dept_id, secondary_dept_ids, confidence_score,
            routing_decision, routing_reasoning, routing_method,
            tags, red_flags, requires_escalation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        msg.source_channel,
        msg.source_message_id,
        msg.received_at,
        msg.sender_name,
        msg.sender_contact,
        msg.raw_message,
        enriched["is_escalation"],
        enriched["account_name"],
        enriched["issue_category"],
        enriched["ai_summary"],
        enriched["urgency"],
        enriched["priority_score"],
        enriched["action_needed"],
        enriched["sentiment"],
        assigned_department,
        sla_deadline,
        routing["primary_dept_id"],
        _json.dumps(routing.get("secondary_dept_ids", [])),
        routing.get("confidence_score", 0),
        routing.get("routing_label", ""),
        routing.get("reasoning", ""),
        routing.get("routing_method", "rule"),
        _json.dumps(routing.get("tags", [])),
        _json.dumps(routing.get("red_flags", [])),
        1 if routing.get("red_flags") else 0,
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"[Ingest] ID={new_id} | {msg.source_channel} | {enriched['urgency']} urgency | dept={assigned_department} | is_escalation={enriched['is_escalation']}")

    return {
        "id": new_id,
        "is_escalation": enriched["is_escalation"],
        "urgency": enriched["urgency"],
        "priority_score": enriched["priority_score"],
        "account_name": enriched["account_name"],
        "department": assigned_department,
        "routing_method": routing.get("routing_method", "rule"),
    }


# ─────────────────────────────────────────────
# GET /api/escalations — list with filters
# ─────────────────────────────────────────────
@app.get("/api/escalations")
def list_escalations(
    is_escalation: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    vp_watch: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None),  # 'today' | 'yesterday' | 'week'
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if is_escalation is not None:
        conditions.append("is_escalation = ?")
        params.append(is_escalation)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if urgency:
        conditions.append("urgency = ?")
        params.append(urgency)
    if owner:
        conditions.append("owner = ?")
        params.append(owner)
    if department:
        conditions.append("assigned_department = ?")
        params.append(department)
    if vp_watch is not None:
        conditions.append("vp_watch = ?")
        params.append(vp_watch)
    if search:
        conditions.append("(account_name LIKE ? OR raw_message LIKE ? OR sender_name LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if date_filter:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago  = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        if date_filter == "today":
            conditions.append("created_at LIKE ?")
            params.append(f"{today}%")
        elif date_filter == "yesterday":
            conditions.append("created_at LIKE ?")
            params.append(f"{yesterday}%")
        elif date_filter == "week":
            conditions.append("created_at >= ?")
            params.append(f"{week_ago}T00:00:00")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    cursor.execute(f"""
        SELECT * FROM escalations
        {where_clause}
        ORDER BY priority_score DESC, received_at DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])

    rows = [dict(row) for row in cursor.fetchall()]

    cursor.execute(f"SELECT COUNT(*) FROM escalations {where_clause}", params)
    total = cursor.fetchone()[0]
    conn.close()

    return {"escalations": rows, "total": total, "limit": limit, "offset": offset}


# ─────────────────────────────────────────────
# DELETE /api/escalations — bulk clear data
# ─────────────────────────────────────────────
@app.delete("/api/escalations")
def clear_escalations(
    scope: str = Query("all"),        # 'all' | 'today' | 'channel'
    channel: Optional[str] = Query(None),
):
    """
    Delete escalation records.
    scope=all    → delete everything
    scope=today  → delete records created today
    scope=channel → delete by source_channel (requires ?channel=gmail|slack|whatsapp)
    """
    conn = get_connection()
    cursor = conn.cursor()

    if scope == "today":
        # 'localtime' modifier converts UTC stored value to local time for comparison
        cursor.execute("SELECT COUNT(*) FROM escalations WHERE date(created_at, 'localtime') = date('now', 'localtime')")
        deleted = cursor.fetchone()[0]
        cursor.execute("DELETE FROM escalations WHERE date(created_at, 'localtime') = date('now', 'localtime')")
    elif scope == "channel" and channel:
        cursor.execute("SELECT COUNT(*) FROM escalations WHERE source_channel = ?", (channel,))
        deleted = cursor.fetchone()[0]
        cursor.execute("DELETE FROM escalations WHERE source_channel = ?", (channel,))
    else:
        cursor.execute("SELECT COUNT(*) FROM escalations")
        deleted = cursor.fetchone()[0]
        cursor.execute("DELETE FROM escalations")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='escalations'")
        except Exception:
            pass

    conn.commit()
    conn.close()
    return {"deleted": deleted, "scope": scope}


# ─────────────────────────────────────────────
# GET /api/export/csv — export all data as CSV
# ─────────────────────────────────────────────
@app.get("/api/export/csv")
def export_csv(
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    is_escalation: Optional[int] = Query(None),
):
    """Export escalations as a downloadable CSV file."""
    conn = get_connection()
    cursor = conn.cursor()

    conditions, params = [], []
    if status:
        conditions.append("status = ?"); params.append(status)
    if urgency:
        conditions.append("urgency = ?"); params.append(urgency)
    if owner:
        conditions.append("owner = ?"); params.append(owner)
    if is_escalation is not None:
        conditions.append("is_escalation = ?"); params.append(is_escalation)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cursor.execute(f"SELECT * FROM escalations {where_clause} ORDER BY priority_score DESC, received_at DESC", params)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(list(row))

    output.seek(0)
    filename = f"escalations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─────────────────────────────────────────────
# GET /api/escalations/{id} — single record
# ─────────────────────────────────────────────
@app.get("/api/escalations/{esc_id}")
def get_escalation(esc_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM escalations WHERE id = ?", (esc_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return dict(row)


# ─────────────────────────────────────────────
# PATCH /api/escalations/{id} — update ownership / status / notes
# ─────────────────────────────────────────────
@app.patch("/api/escalations/{esc_id}")
def update_escalation(esc_id: int, update: EscalationUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, status FROM escalations WHERE id = ?", (esc_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Escalation not found")

    now = datetime.now(timezone.utc).isoformat()
    fields = {"updated_at": now}

    if update.owner is not None:
        fields["owner"] = update.owner
    if update.status is not None:
        fields["status"] = update.status
        if update.status == "Closed":
            fields["closed_at"] = now
    if update.resolution_notes is not None:
        fields["resolution_notes"] = update.resolution_notes
    if update.vp_watch is not None:
        fields["vp_watch"] = update.vp_watch
    if update.vp_watch_note is not None:
        fields["vp_watch_note"] = update.vp_watch_note
    if update.vp_urgency_override is not None:
        fields["vp_urgency_override"] = update.vp_urgency_override
    if update.vp_escalate_dept is not None:
        fields["vp_escalate_dept"] = update.vp_escalate_dept
    if update.vp_check is not None:
        fields["vp_check"] = update.vp_check

    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    cursor.execute(
        f"UPDATE escalations SET {set_clause} WHERE id = ?",
        list(fields.values()) + [esc_id],
    )
    conn.commit()
    conn.close()

    return {"id": esc_id, "updated": list(fields.keys())}


# ─────────────────────────────────────────────
# GET /api/stats — dashboard summary cards
# ─────────────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Total escalations (only real ones)
    cursor.execute("SELECT COUNT(*) FROM escalations WHERE is_escalation = 1")
    total = cursor.fetchone()[0]

    # High priority (score >= 8)
    cursor.execute("SELECT COUNT(*) FROM escalations WHERE is_escalation = 1 AND priority_score >= 8")
    high_priority = cursor.fetchone()[0]

    # SLA breached (deadline passed and not Closed)
    cursor.execute("""
        SELECT COUNT(*) FROM escalations
        WHERE is_escalation = 1
          AND status != 'Closed'
          AND sla_deadline_at < ?
    """, (now_iso,))
    sla_breached = cursor.fetchone()[0]

    # Blocked
    cursor.execute("SELECT COUNT(*) FROM escalations WHERE is_escalation = 1 AND status = 'Blocked'")
    blocked = cursor.fetchone()[0]

    # Closed today
    cursor.execute("""
        SELECT COUNT(*) FROM escalations
        WHERE is_escalation = 1
          AND status = 'Closed'
          AND closed_at LIKE ?
    """, (f"{today}%",))
    closed_today = cursor.fetchone()[0]

    # By urgency
    cursor.execute("""
        SELECT urgency, COUNT(*) as cnt FROM escalations
        WHERE is_escalation = 1
        GROUP BY urgency
    """)
    by_urgency = {row["urgency"]: row["cnt"] for row in cursor.fetchall()}

    # By status
    cursor.execute("""
        SELECT status, COUNT(*) as cnt FROM escalations
        WHERE is_escalation = 1
        GROUP BY status
    """)
    by_status = {row["status"]: row["cnt"] for row in cursor.fetchall()}

    # By channel
    cursor.execute("""
        SELECT source_channel, COUNT(*) as cnt FROM escalations
        WHERE is_escalation = 1
        GROUP BY source_channel
    """)
    by_channel = {row["source_channel"]: row["cnt"] for row in cursor.fetchall()}

    # By department
    cursor.execute("""
        SELECT assigned_department, COUNT(*) as cnt FROM escalations
        WHERE is_escalation = 1
        GROUP BY assigned_department
    """)
    by_department = {row["assigned_department"]: row["cnt"] for row in cursor.fetchall()}

    # VP Watch count
    cursor.execute("SELECT COUNT(*) FROM escalations WHERE is_escalation = 1 AND vp_watch = 1")
    vp_watch_count = cursor.fetchone()[0]

    conn.close()

    return {
        "total": total,
        "high_priority": high_priority,
        "sla_breached": sla_breached,
        "blocked": blocked,
        "closed_today": closed_today,
        "vp_watch_count": vp_watch_count,
        "by_urgency": by_urgency,
        "by_status": by_status,
        "by_channel": by_channel,
        "by_department": by_department,
    }


# ─────────────────────────────────────────────
# Source Connection API
# ─────────────────────────────────────────────

class GmailSourceIn(BaseModel):
    email: str
    app_password: str

class SlackSourceIn(BaseModel):
    bot_token: str
    channel_id: str
    channel_name: str = ""


@app.get("/api/sources")
def get_sources():
    """Return configured sources — no passwords returned."""
    return sources_config.public_view()


@app.post("/api/sources/gmail", status_code=201)
def add_gmail_source(body: GmailSourceIn):
    sources_config.add_gmail(body.email, body.app_password)
    print(f"[Sources] Gmail added: {body.email}")
    return {"ok": True, "email": body.email}


@app.delete("/api/sources/gmail/{email:path}")
def remove_gmail_source(email: str):
    sources_config.remove_gmail(email)
    return {"ok": True}


@app.post("/api/sources/slack", status_code=201)
def add_slack_source(body: SlackSourceIn):
    sources_config.set_slack_token(body.bot_token)
    sources_config.add_slack_channel(body.channel_id, body.channel_name)
    print(f"[Sources] Slack channel added: {body.channel_id}")
    return {"ok": True, "channel_id": body.channel_id}


@app.delete("/api/sources/slack/{channel_id}")
def remove_slack_source(channel_id: str):
    sources_config.remove_slack_channel(channel_id)
    return {"ok": True}


# ─────────────────────────────────────────────
# Source connection tests
# ─────────────────────────────────────────────
class TestGmailIn(BaseModel):
    email: str
    app_password: str

class TestSlackIn(BaseModel):
    bot_token: str

@app.post("/api/sources/test/gmail")
def test_gmail(body: TestGmailIn):
    """Test Gmail IMAP credentials without saving."""
    import imaplib
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)
        mail.login(body.email, body.app_password)
        status, data = mail.select("inbox")
        count = int(data[0]) if data[0] else 0
        mail.logout()
        return {"ok": True, "inbox_count": count}
    except imaplib.IMAP4.error as e:
        return {"ok": False, "error": f"Auth failed: {str(e)}. Make sure you're using an App Password, not your regular Gmail password."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/sources/test/slack")
def test_slack(body: TestSlackIn):
    """Test Slack bot token without saving."""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
        client = WebClient(token=body.bot_token)
        result = client.auth_test()
        return {"ok": True, "workspace": result["team"], "bot_name": result["user"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────
# Complaint Routing API
# ─────────────────────────────────────────────

class RouteRequest(BaseModel):
    complaint_text: str
    use_ai: bool = True

class BatchRouteRequest(BaseModel):
    complaints: list[dict]
    use_ai: bool = True


@app.post("/api/route")
def route_single(req: RouteRequest):
    """Route a single complaint — does NOT save to DB."""
    return complaint_router.route_complaint(req.complaint_text, use_ai=req.use_ai)


@app.post("/api/route/batch")
def route_batch_endpoint(req: BatchRouteRequest):
    """Route a batch of complaints — does NOT save to DB. Returns results + analytics."""
    return complaint_router.route_batch(req.complaints, use_ai=req.use_ai)


@app.get("/api/routing/stats")
def routing_stats():
    """Return routing analytics from the escalations DB."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT primary_dept_id, COUNT(*) as cnt FROM escalations
        WHERE primary_dept_id IS NOT NULL
        GROUP BY primary_dept_id
    """)
    by_dept_raw = cursor.fetchall()
    by_department = {
        get_department(row["primary_dept_id"])["short"]: row["cnt"]
        for row in by_dept_raw
    }

    cursor.execute("""
        SELECT routing_decision, COUNT(*) as cnt FROM escalations
        WHERE routing_decision IS NOT NULL
        GROUP BY routing_decision
    """)
    by_decision = {row["routing_decision"]: row["cnt"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT AVG(confidence_score) as avg_conf FROM escalations
        WHERE confidence_score IS NOT NULL
    """)
    avg_conf = cursor.fetchone()["avg_conf"]

    conn.close()
    return {
        "by_department": by_department,
        "by_routing_decision": by_decision,
        "avg_confidence_score": round(avg_conf, 1) if avg_conf else 0,
        "departments": {
            str(k): {"name": v["name"], "short": v["short"], "sla_hours": v["sla_hours"],
                     "priority_default": v["priority_default"]}
            for k, v in DEPARTMENTS.items()
        },
    }
