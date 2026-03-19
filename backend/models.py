from pydantic import BaseModel
from typing import Optional


class InboundMessage(BaseModel):
    """Payload received from n8n / Make.com / any source"""
    source_channel: str           # 'gmail' | 'slack' | 'whatsapp'
    source_message_id: Optional[str] = None
    received_at: str              # ISO8601 string
    sender_name: Optional[str] = None
    sender_contact: Optional[str] = None
    raw_message: str


class EscalationUpdate(BaseModel):
    """Payload for PATCH /api/escalations/{id}"""
    owner: Optional[str] = None
    status: Optional[str] = None              # 'Open' | 'In Progress' | 'Blocked' | 'Closed'
    resolution_notes: Optional[str] = None
    vp_watch: Optional[int] = None            # 1 = VP watching, 0 = not watching
    vp_watch_note: Optional[str] = None       # VP's note on why watching
    vp_urgency_override: Optional[str] = None # 'CRITICAL' | 'HIGH' | 'MEDIUM' — VP priority flag
    vp_escalate_dept: Optional[str] = None    # Department name VP is escalating to
    vp_check: Optional[int] = None            # 1 = flagged for VP to check


class EscalationRecord(BaseModel):
    """Full record returned by GET /api/escalations"""
    id: int
    source_channel: str
    source_message_id: Optional[str]
    received_at: str
    sender_name: Optional[str]
    sender_contact: Optional[str]
    raw_message: str
    is_escalation: int
    account_name: Optional[str]
    issue_category: Optional[str]
    ai_summary: Optional[str]
    urgency: str
    priority_score: int
    action_needed: Optional[str]
    sentiment: Optional[str]
    owner: str
    status: str
    resolution_notes: Optional[str]
    nudge_sent: int
    sla_deadline_at: Optional[str]
    closed_at: Optional[str]
    created_at: str
    updated_at: str
