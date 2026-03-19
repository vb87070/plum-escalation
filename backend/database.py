import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "escalations.db"))


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS escalations (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Source fields
            source_channel    TEXT NOT NULL,
            source_message_id TEXT,
            received_at       TEXT NOT NULL,
            sender_name       TEXT,
            sender_contact    TEXT,
            raw_message       TEXT NOT NULL,

            -- AI Classification & Enrichment
            is_escalation     INTEGER DEFAULT 1,
            account_name      TEXT,
            issue_category    TEXT,
            ai_summary        TEXT,
            urgency           TEXT DEFAULT 'Medium',
            priority_score    INTEGER DEFAULT 5,
            action_needed     TEXT,
            sentiment         TEXT,

            -- Department routing (auto-assigned from issue_category)
            assigned_department TEXT DEFAULT 'Account Management',

            -- Ownership & Tracking
            owner             TEXT DEFAULT 'Unassigned',
            status            TEXT DEFAULT 'Open',
            resolution_notes  TEXT,
            nudge_sent        INTEGER DEFAULT 0,

            -- VP Watch
            vp_watch          INTEGER DEFAULT 0,
            vp_watch_note     TEXT,

            -- Timelines
            sla_deadline_at   TEXT,
            closed_at         TEXT,
            created_at        TEXT DEFAULT (datetime('now')),
            updated_at        TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_status        ON escalations(status);
        CREATE INDEX IF NOT EXISTS idx_urgency       ON escalations(urgency);
        CREATE INDEX IF NOT EXISTS idx_owner         ON escalations(owner);
        CREATE INDEX IF NOT EXISTS idx_is_escalation ON escalations(is_escalation);
    """)

    # Migration: safely add new columns to existing databases
    for col, definition in [
        ("assigned_department",   "TEXT DEFAULT 'Account Management'"),
        ("vp_watch",              "INTEGER DEFAULT 0"),
        ("vp_watch_note",         "TEXT"),
        # Routing system columns
        ("primary_dept_id",       "INTEGER"),
        ("secondary_dept_ids",    "TEXT"),   # JSON array
        ("confidence_score",      "INTEGER"),
        ("routing_decision",      "TEXT"),
        ("routing_reasoning",     "TEXT"),
        ("routing_method",        "TEXT"),
        ("tags",                  "TEXT"),   # JSON array
        ("red_flags",             "TEXT"),   # JSON array
        ("requires_escalation",   "INTEGER DEFAULT 0"),
        # VP escalation fields
        ("vp_urgency_override",   "TEXT"),
        ("vp_escalate_dept",      "TEXT"),
        ("vp_check",              "INTEGER DEFAULT 0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE escalations ADD COLUMN {col} {definition}")
        except Exception:
            pass  # column already exists — safe to ignore

    # Create indexes for migrated columns (safe to run after columns exist)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_vp_watch ON escalations(vp_watch)",
        "CREATE INDEX IF NOT EXISTS idx_dept     ON escalations(primary_dept_id)",
    ]:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")
