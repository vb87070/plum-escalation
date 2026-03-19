"""
PLUM Insurance — Complaint Auto-Routing System.
Hybrid routing: fast rule-based first, Claude AI for ambiguous cases or low confidence.
"""

import json
import os
import anthropic
from departments import (
    DEPARTMENTS, rule_based_route, detect_red_flags, generate_tags, get_department
)

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

ROUTING_PROMPT = """You are an AI routing assistant for PLUM Insurance, a B2B health insurance platform.
Your job is to analyze a customer complaint and route it to the correct internal department.

Available departments:
1. Customer Support / Member Experience — general inquiries, account access, basic help (SLA: 72h, Priority: LOW)
2. Claims Team (Operations) — claim status, reimbursement, TPA issues, claim rejection (SLA: 24h, Priority: HIGH)
3. Grievance Redressal Cell (GRO) — repeat complaints, formal grievances, escalations (SLA: 4h, Priority: CRITICAL)
4. Legal & Compliance — legal threats, IRDAI, consumer court, lawsuits (SLA: 4h, Priority: CRITICAL)
5. Insurer Coordination Team — insurer not responding, underwriter issues, coordination (SLA: 24h, Priority: HIGH)
6. Hospital / Provider Network Team — cashless, pre-authorization, hospital billing, admission (SLA: 24h, Priority: HIGH)
7. Account Management (Corporate/B2B) — corporate accounts, HR escalations, group policy (SLA: 24h, Priority: HIGH)
8. Quality & Audit Team — service quality, SLA violations, repeat issues, audit (SLA: 48h, Priority: MEDIUM)
9. Product / Tech Team — app bugs, portal issues, login errors, technical problems (SLA: 24h, Priority: HIGH)

Complaint:
{complaint_text}

Respond with ONLY a valid JSON object — no explanation, no markdown:
{{
  "primary_department_id": <1-9>,
  "secondary_department_ids": [<ids of 0-2 other depts that may need to be involved>],
  "confidence_score": <0-100>,
  "routing_reasoning": "<1-2 sentence explanation of why this department>",
  "priority_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "requires_escalation": true | false,
  "red_flags": [<list of flags: "repeat_complaint","legal_threat","social_media_threat","angry_language","escalation_request","medical_emergency">],
  "tags": [<3-5 relevant short tags>]
}}"""


def _call_claude_router(complaint_text: str) -> dict:
    """Call Claude to get AI-based routing decision."""
    prompt = ROUTING_PROMPT.format(complaint_text=complaint_text)
    response = _client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


def route_complaint(complaint_text: str, use_ai: bool = True) -> dict:
    """
    Route a complaint to the appropriate department.

    Strategy:
    - Run rule-based routing first (fast, free)
    - If confidence >= 90 → return rule-based result directly
    - If confidence 70-89 → return rule-based + flag for review
    - If confidence < 70 or use_ai=True → call Claude for a better decision

    Returns the full routing result dict.
    """
    rule_result = rule_based_route(complaint_text)
    rule_confidence = rule_result["confidence_score"]
    red_flags = detect_red_flags(complaint_text)

    # High-confidence rule match — skip AI
    if rule_confidence >= 90 and not use_ai:
        dept_id = rule_result["primary_dept_id"]
        dept = get_department(dept_id)
        tags = generate_tags(complaint_text, dept_id)
        return _build_result(
            primary_dept_id=dept_id,
            secondary_dept_ids=rule_result["secondary_dept_ids"],
            confidence_score=rule_confidence,
            routing_reasoning=f"Rule-based match: {rule_result['routing_label']}",
            priority_level=dept["priority_default"],
            requires_escalation=dept["priority_default"] in ("CRITICAL", "HIGH"),
            red_flags=red_flags,
            tags=tags,
            routing_method="rule_based",
            dept=dept,
        )

    # Use AI routing (rule-based result used as fallback)
    if use_ai:
        try:
            ai = _call_claude_router(complaint_text)
            dept_id = int(ai.get("primary_department_id", rule_result["primary_dept_id"]))
            dept = get_department(dept_id)
            ai_confidence = int(ai.get("confidence_score", 70))
            # Blend: if AI confidence is higher, use AI; otherwise blend
            confidence = ai_confidence if ai_confidence >= rule_confidence else max(ai_confidence, rule_confidence)

            # Merge red flags (AI + rule-based)
            ai_flags = ai.get("red_flags", [])
            merged_flags = list(set(red_flags + [f for f in ai_flags if isinstance(f, str)]))

            return _build_result(
                primary_dept_id=dept_id,
                secondary_dept_ids=ai.get("secondary_department_ids", rule_result["secondary_dept_ids"]),
                confidence_score=confidence,
                routing_reasoning=ai.get("routing_reasoning", f"AI routing to {dept['name']}"),
                priority_level=ai.get("priority_level", dept["priority_default"]),
                requires_escalation=bool(ai.get("requires_escalation", dept["priority_default"] in ("CRITICAL", "HIGH"))),
                red_flags=merged_flags,
                tags=ai.get("tags", generate_tags(complaint_text, dept_id)),
                routing_method="ai",
                dept=dept,
            )
        except Exception as e:
            print(f"[Router] AI routing failed: {e}. Falling back to rule-based.")

    # Fallback: rule-based result
    dept_id = rule_result["primary_dept_id"]
    dept = get_department(dept_id)
    tags = generate_tags(complaint_text, dept_id)
    return _build_result(
        primary_dept_id=dept_id,
        secondary_dept_ids=rule_result["secondary_dept_ids"],
        confidence_score=rule_confidence,
        routing_reasoning=f"Rule-based match: {rule_result['routing_label']}",
        priority_level=dept["priority_default"],
        requires_escalation=dept["priority_default"] in ("CRITICAL", "HIGH"),
        red_flags=red_flags,
        tags=tags,
        routing_method="rule_based",
        dept=dept,
    )


def _build_result(
    primary_dept_id: int,
    secondary_dept_ids: list,
    confidence_score: int,
    routing_reasoning: str,
    priority_level: str,
    requires_escalation: bool,
    red_flags: list,
    tags: list,
    routing_method: str,
    dept: dict,
) -> dict:
    """Build the standardized routing result."""
    # Resolve secondary department info
    secondary_depts = []
    for sid in (secondary_dept_ids or []):
        try:
            sd = get_department(int(sid))
            secondary_depts.append({"id": int(sid), "name": sd["name"], "short": sd["short"]})
        except Exception:
            pass

    # Determine auto-route vs needs review
    if confidence_score >= 90:
        routing_decision = "AUTO_ROUTED"
    elif confidence_score >= 70:
        routing_decision = "NEEDS_REVIEW"
    else:
        routing_decision = "MANUAL_REVIEW"

    return {
        "primary_department": {
            "id": primary_dept_id,
            "name": dept["name"],
            "short": dept["short"],
            "sla_hours": dept["sla_hours"],
        },
        "secondary_departments": secondary_depts,
        "confidence_score": confidence_score,
        "routing_decision": routing_decision,
        "routing_reasoning": routing_reasoning,
        "priority_level": priority_level,
        "requires_escalation": requires_escalation,
        "red_flags": red_flags,
        "tags": tags,
        "routing_method": routing_method,
    }


def route_batch(complaints: list[dict], use_ai: bool = True) -> dict:
    """
    Route a batch of complaints.
    Each item in complaints must have 'complaint_text' and optionally 'id'.
    Returns results list + analytics summary.
    """
    results = []
    dept_counts = {}
    priority_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    flag_counts = {}
    confidence_sum = 0

    for item in complaints:
        text = item.get("complaint_text", "")
        item_id = item.get("id")
        result = route_complaint(text, use_ai=use_ai)
        if item_id is not None:
            result["id"] = item_id
        results.append(result)

        # Aggregate analytics
        dept_name = result["primary_department"]["short"]
        dept_counts[dept_name] = dept_counts.get(dept_name, 0) + 1
        p = result["priority_level"]
        if p in priority_counts:
            priority_counts[p] += 1
        for flag in result["red_flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        confidence_sum += result["confidence_score"]

    n = len(results)
    analytics = {
        "total": n,
        "by_department": dept_counts,
        "by_priority": priority_counts,
        "by_red_flag": flag_counts,
        "avg_confidence": round(confidence_sum / n, 1) if n > 0 else 0,
        "auto_routed": sum(1 for r in results if r["routing_decision"] == "AUTO_ROUTED"),
        "needs_review": sum(1 for r in results if r["routing_decision"] == "NEEDS_REVIEW"),
        "manual_review": sum(1 for r in results if r["routing_decision"] == "MANUAL_REVIEW"),
    }

    return {"results": results, "analytics": analytics}
