"""
Seed script — inserts fully enriched demo data directly into SQLite.
No Claude API / credits needed. Perfect for demo.
Run from escalation-system folder:
    python seed_demo_data.py
"""
import sqlite3, os
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "backend", "escalations.db")

DEMO_ROWS = [
    # ── GMAIL ──────────────────────────────────────────────────────────────
    {
        "source_channel": "gmail", "source_message_id": "gmail-001",
        "received_at": "2026-03-19T06:00:00Z",
        "sender_name": "Corporate HR", "sender_contact": "hr@enterprise.com",
        "raw_message": "Dear Avik, I am writing to formally escalate the unacceptable service during our employee Rahul Gaur medical emergency (Emp ID: PM0227, Claim: 82086141). Health ID was not issued despite 20+ follow-up emails. Cashless facility was denied. We will not be renewing our policy and will pursue legal avenues if not resolved immediately.",
        "is_escalation": 1, "account_name": "Enterprise Corp",
        "issue_category": "IRDAI/Legal Threat",
        "ai_summary": "Enterprise Corp's employee faced a medical emergency but cashless facility was denied due to un-issued Health ID despite 20+ follow-ups. Customer has explicitly threatened legal action and policy non-renewal. Immediate VP-level intervention required.",
        "urgency": "High", "priority_score": 10,
        "action_needed": "Call HR immediately, arrange emergency cashless override with insurer, assign dedicated relationship manager within 1 hour.",
        "sentiment": "Threatening", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-19T10:00:00Z",
    },
    {
        "source_channel": "gmail", "source_message_id": "gmail-002",
        "received_at": "2026-03-19T08:15:00Z",
        "sender_name": "Corporate HR", "sender_contact": "hr@techfirm.com",
        "raw_message": "Dear Avik, I am extremely disappointed with the level of service post policy issuance. The claim portal is extremely complex. The website failed mid-upload. We are reconsidering our decision to choose Plum.",
        "is_escalation": 1, "account_name": "TechFirm Ltd",
        "issue_category": "Document Upload",
        "ai_summary": "TechFirm Ltd's HR is frustrated with the claim portal's complexity — strict format requirements, one-doc-at-a-time upload, and website failure mid-process. Customer is actively considering switching from Plum to a traditional agent.",
        "urgency": "High", "priority_score": 8,
        "action_needed": "Arrange manual document submission assistance, assign ops support to complete upload on customer's behalf today.",
        "sentiment": "Frustrated", "owner": "Arun Chacko", "status": "In Progress",
        "sla_deadline_at": "2026-03-19T12:15:00Z",
    },
    {
        "source_channel": "gmail", "source_message_id": "gmail-003",
        "received_at": "2026-02-28T10:00:00Z",
        "sender_name": "Karan Mehta", "sender_contact": "karan@startupco.com",
        "raw_message": "Hi, We made payment on 20/02/2026 to add an employee. As per your process it takes 3-5 working days which has elapsed. Today is 28/02/2026 and I am still following up. When will this get done?",
        "is_escalation": 1, "account_name": "StartupCo",
        "issue_category": "Data Correction",
        "ai_summary": "StartupCo paid on 20th Feb to add an employee but the addition is still pending 8 days later — well beyond the promised 3-5 working day SLA. Customer is following up for the first time formally.",
        "urgency": "Medium", "priority_score": 6,
        "action_needed": "Check employee addition status in system, provide confirmed completion date, escalate to ops if stuck in queue.",
        "sentiment": "Frustrated", "owner": "Vaishnavi Bhat", "status": "In Progress",
        "sla_deadline_at": "2026-02-29T10:00:00Z",
    },
    {
        "source_channel": "gmail", "source_message_id": "gmail-004",
        "received_at": "2026-03-19T09:00:00Z",
        "sender_name": "Referral Friend", "sender_contact": "friend@gmail.com",
        "raw_message": "Hi Avik, My brother is looking for insurance for his firm. Can you reach out to him? Regards",
        "is_escalation": 0, "account_name": "Unknown",
        "issue_category": "Other",
        "ai_summary": "This is a personal referral — not an escalation. Someone asking VP to connect their brother who is looking for insurance.",
        "urgency": "Low", "priority_score": 1,
        "action_needed": "Forward referral lead to sales team.",
        "sentiment": "Neutral", "owner": "Unassigned", "status": "Closed",
        "sla_deadline_at": "2026-03-22T09:00:00Z",
    },
    {
        "source_channel": "gmail", "source_message_id": "gmail-005",
        "received_at": "2026-03-19T08:00:00Z",
        "sender_name": "HR Manager", "sender_contact": "hr@mediumcorp.com",
        "raw_message": "Hi Mr Avik, I requested a dedicated training session for our employees on the Plum app. The common Thursday session was not engaging. Please arrange a proper dedicated session for our team.",
        "is_escalation": 1, "account_name": "MediumCorp",
        "issue_category": "Training Request",
        "ai_summary": "MediumCorp's HR is requesting a dedicated Plum app training session, as the generic Thursday session was insufficient for their team's needs. Employees haven't started using the app yet due to lack of proper onboarding.",
        "urgency": "Low", "priority_score": 3,
        "action_needed": "Schedule a dedicated 1-hour Plum app training session for MediumCorp team within this week.",
        "sentiment": "Neutral", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-22T08:00:00Z",
    },
    {
        "source_channel": "gmail", "source_message_id": "gmail-007",
        "received_at": "2026-03-19T11:00:00Z",
        "sender_name": "Sneha Kapoor", "sender_contact": "sneha.k@fintech.co",
        "raw_message": "Avik, I am absolutely not satisfied and trust me I am not going to put a good word for Plum to anyone in the HR community. The claim for our employee has been pending for over 6 weeks with no resolution.",
        "is_escalation": 1, "account_name": "FinTech Co",
        "issue_category": "Claim Processing",
        "ai_summary": "FinTech Co's HR head is threatening reputation damage in the HR community. A claim has been unresolved for 6+ weeks with no progress. Customer is highly frustrated and likely to churn and spread negative word-of-mouth.",
        "urgency": "High", "priority_score": 9,
        "action_needed": "Immediately pull claim status, get VP-level commitment to resolve within 24h, call customer with a clear resolution timeline.",
        "sentiment": "Threatening", "owner": "Unassigned", "status": "Blocked",
        "sla_deadline_at": "2026-03-19T15:00:00Z",
    },
    # ── SLACK ──────────────────────────────────────────────────────────────
    {
        "source_channel": "slack", "source_message_id": "slack-001",
        "received_at": "2026-03-19T09:30:00Z",
        "sender_name": "Vidushi M", "sender_contact": "@vidushi.m",
        "raw_message": "[Thread - Mehta Industries] User is not okay with the delay. Potential escalation for social media and he has mentioned he is going to take this up with IRDAI. Pending since Jan 15.",
        "is_escalation": 1, "account_name": "Mehta Industries",
        "issue_category": "Social Media Threat",
        "ai_summary": "Mehta Industries claim has been pending since Jan 15 with no resolution. Customer has threatened both social media escalation and formal IRDAI complaint. Internal team is aware but awaiting insurer revert.",
        "urgency": "High", "priority_score": 9,
        "action_needed": "Get Avik Bhandari to directly call insurer, set 48h resolution deadline, proactively update customer before they escalate to IRDAI.",
        "sentiment": "Threatening", "owner": "Arun Saseedharan", "status": "Blocked",
        "sla_deadline_at": "2026-03-19T13:30:00Z",
    },
    {
        "source_channel": "slack", "source_message_id": "slack-002",
        "received_at": "2026-03-19T11:00:00Z",
        "sender_name": "Mikhel Dhiman", "sender_contact": "@mikhel.dhiman",
        "raw_message": "Hey @Ipsita @Arun Chacko — following the recent call where their director was also present, discussion did not go as expected. Please draft email outlining claim details and next steps. Involve @Avik Bhandari to escalate with insurer.",
        "is_escalation": 1, "account_name": "Unknown",
        "issue_category": "Claim Processing",
        "ai_summary": "A client call attended by their director did not go well. Internal team is now coordinating to draft a formal email and escalate the claim with the insurer. VP involvement has been explicitly requested.",
        "urgency": "High", "priority_score": 8,
        "action_needed": "Draft and send claim summary email to customer's director today, escalate to insurer with Avik's backing.",
        "sentiment": "Frustrated", "owner": "Arun Chacko", "status": "In Progress",
        "sla_deadline_at": "2026-03-19T15:00:00Z",
    },
    {
        "source_channel": "slack", "source_message_id": "slack-003",
        "received_at": "2026-03-19T10:30:00Z",
        "sender_name": "Manashi", "sender_contact": "@manashi",
        "raw_message": "GWP data incorrect on SF — premium and EIDs all wrong. Policy placed with wrong data. Onboarding has to be restarted. Very sensitive customer. @Avik Bhandari please help manage.",
        "is_escalation": 1, "account_name": "Unknown",
        "issue_category": "Data Correction",
        "ai_summary": "A sensitive customer's policy was placed with completely incorrect data — wrong premium, wrong EIDs. Fixing this requires full onboarding restart. VP has been tagged and is expected to manage the relationship during correction.",
        "urgency": "High", "priority_score": 8,
        "action_needed": "Avik to call customer immediately to explain the data correction plan; ops to restart onboarding with correct EIDs today.",
        "sentiment": "Frustrated", "owner": "Manashi", "status": "In Progress",
        "sla_deadline_at": "2026-03-19T14:30:00Z",
    },
    {
        "source_channel": "slack", "source_message_id": "slack-004",
        "received_at": "2026-03-19T14:00:00Z",
        "sender_name": "Arun Saseedharan", "sender_contact": "@arun.s",
        "raw_message": "@Avik Bhandari for your eyes — Globex account claim might go as social escalation. Customer mentioned IRDAI and legal action. Need your guidance urgently.",
        "is_escalation": 1, "account_name": "Globex",
        "issue_category": "IRDAI/Legal Threat",
        "ai_summary": "Globex account has an active claim that risks becoming a social media and IRDAI escalation. Customer has explicitly mentioned both IRDAI and legal action. The situation has been flagged directly to VP Avik Bhandari.",
        "urgency": "High", "priority_score": 9,
        "action_needed": "VP to personally call Globex within 2 hours, coordinate with legal team, get insurer to fast-track the claim today.",
        "sentiment": "Threatening", "owner": "Avik Bhandari", "status": "Open",
        "sla_deadline_at": "2026-03-19T18:00:00Z",
    },
    {
        "source_channel": "slack", "source_message_id": "slack-005",
        "received_at": "2026-03-19T15:00:00Z",
        "sender_name": "Ipsita Sahu", "sender_contact": "@ipsita.sahu",
        "raw_message": "BF5278 - Disqualified DUR Pendency Closed. Can we review this? The employee is very distressed and HR is escalating to their MD.",
        "is_escalation": 1, "account_name": "Unknown",
        "issue_category": "Claim Processing",
        "ai_summary": "A claim (BF5278) was closed due to DUR pendency but the employee is distressed and HR is escalating internally to their MD. The closure reason needs to be reviewed and communicated clearly.",
        "urgency": "Medium", "priority_score": 7,
        "action_needed": "Review BF5278 DUR requirements, communicate status to HR, explore exception processing with insurer.",
        "sentiment": "Frustrated", "owner": "Rajorshi Chowdhury", "status": "Open",
        "sla_deadline_at": "2026-03-20T15:00:00Z",
    },
    # ── WHATSAPP ───────────────────────────────────────────────────────────
    {
        "source_channel": "whatsapp", "source_message_id": "wa-001",
        "received_at": "2026-03-19T07:45:00Z",
        "sender_name": "Rajesh Sharma", "sender_contact": "+919876543210",
        "raw_message": "Hi Avik bhai, urgent — employee had surgery yesterday, cashless not approved. Hospital demanding Rs 3.5L payment. Health ID was never issued. Please help urgently. Omega Pharma, 200 employees.",
        "is_escalation": 1, "account_name": "Omega Pharma",
        "issue_category": "Cashless Facility",
        "ai_summary": "Omega Pharma employee underwent surgery but cashless approval is pending as Health ID was never issued. Hospital is demanding Rs 3.5L upfront payment. Account has 200 employees and this is a critical medical emergency requiring immediate action.",
        "urgency": "High", "priority_score": 10,
        "action_needed": "Emergency: Call insurer's cashless desk immediately, arrange Health ID issuance on priority, approve cashless within 1 hour.",
        "sentiment": "Threatening", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-19T11:45:00Z",
    },
    {
        "source_channel": "whatsapp", "source_message_id": "wa-002",
        "received_at": "2026-03-19T08:30:00Z",
        "sender_name": "HR Head", "sender_contact": "+918800112233",
        "raw_message": "Avik ji good morning. Our policy renewal is due next week on 26th March and we have not received the renewal quote. Our MD is asking. If not received today we will look at other options.",
        "is_escalation": 1, "account_name": "Unknown",
        "issue_category": "Policy Renewal",
        "ai_summary": "Group policy renewal is due on 26th March but the renewal quote has not been sent. MD is involved and customer has threatened to switch insurers if quote is not received today.",
        "urgency": "High", "priority_score": 8,
        "action_needed": "Send renewal quote today before EOD, include competitive pricing, schedule call with MD to retain account.",
        "sentiment": "Threatening", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-19T12:30:00Z",
    },
    {
        "source_channel": "whatsapp", "source_message_id": "wa-003",
        "received_at": "2026-03-19T09:15:00Z",
        "sender_name": "Priya Nair", "sender_contact": "+917700123456",
        "raw_message": "Hi, this is Priya from TechStart. Can you share the Plum app download link for our team? We just onboarded last week.",
        "is_escalation": 0, "account_name": "TechStart",
        "issue_category": "Other",
        "ai_summary": "New customer TechStart is asking for the Plum app download link — routine post-onboarding query, not an escalation.",
        "urgency": "Low", "priority_score": 1,
        "action_needed": "Share Plum app download link and onboarding guide with TechStart.",
        "sentiment": "Neutral", "owner": "Unassigned", "status": "Closed",
        "sla_deadline_at": "2026-03-22T09:15:00Z",
    },
    {
        "source_channel": "whatsapp", "source_message_id": "wa-004",
        "received_at": "2026-03-19T10:00:00Z",
        "sender_name": "Suresh Kumar", "sender_contact": "+919988776655",
        "raw_message": "Avik sir very urgent — claim rejected, documents missing but uploaded 3 times. Insurer not responding. Delta Technologies. Will escalate to board and post on LinkedIn and HR forums if not resolved today.",
        "is_escalation": 1, "account_name": "Delta Technologies",
        "issue_category": "Social Media Threat",
        "ai_summary": "Delta Technologies has had a claim rejected despite uploading documents 3 times. Insurer is unresponsive. Customer has explicitly threatened LinkedIn/HR forum posts and board escalation if not resolved today.",
        "urgency": "High", "priority_score": 10,
        "action_needed": "Retrieve all submitted documents, call insurer escalation desk directly, provide customer written confirmation of resolution timeline within 2 hours.",
        "sentiment": "Threatening", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-19T14:00:00Z",
    },
    {
        "source_channel": "whatsapp", "source_message_id": "wa-005",
        "received_at": "2026-03-19T12:00:00Z",
        "sender_name": "Amit Verma", "sender_contact": "+919123456789",
        "raw_message": "Hi Avik, just checking if the new employee additions I sent last Friday have been processed. Sent Excel with 15 new employees. No confirmation received.",
        "is_escalation": 1, "account_name": "Unknown",
        "issue_category": "Data Correction",
        "ai_summary": "15 new employee additions were submitted via Excel last Friday but no confirmation has been received. Customer is following up informally but this indicates a process gap in acknowledgement.",
        "urgency": "Low", "priority_score": 4,
        "action_needed": "Check if Excel was received and processed, send confirmation with employee IDs to customer.",
        "sentiment": "Neutral", "owner": "Unassigned", "status": "Open",
        "sla_deadline_at": "2026-03-22T12:00:00Z",
    },
]


def compute_sla(received_at: str, urgency: str) -> str:
    hours = {"High": 4, "Medium": 24, "Low": 72}.get(urgency, 24)
    try:
        base = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
    except Exception:
        base = datetime.now(timezone.utc)
    return (base + timedelta(hours=hours)).isoformat()


def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM escalations")
    print("Cleared existing rows")

    inserted = 0
    for row in DEMO_ROWS:
        sla = row.pop("sla_deadline_at", None) or compute_sla(row["received_at"], row["urgency"])
        now = datetime.now(timezone.utc).isoformat()
        closed_at = now if row["status"] == "Closed" else None

        cursor.execute("""
            INSERT INTO escalations (
                source_channel, source_message_id, received_at,
                sender_name, sender_contact, raw_message,
                is_escalation, account_name, issue_category,
                ai_summary, urgency, priority_score,
                action_needed, sentiment,
                owner, status, resolution_notes,
                sla_deadline_at, closed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            row["source_channel"], row["source_message_id"], row["received_at"],
            row["sender_name"], row["sender_contact"], row["raw_message"],
            row["is_escalation"], row["account_name"], row["issue_category"],
            row["ai_summary"], row["urgency"], row["priority_score"],
            row["action_needed"], row["sentiment"],
            row["owner"], row["status"], None,
            sla, closed_at,
        ))
        flag = "[ESC]" if row["is_escalation"] else "[NOISE]"
        print(f"  {flag}  [{row['urgency']:6}] Score={row['priority_score']:2} | {row['account_name'][:25]:<25} | {row['source_channel']}")
        inserted += 1

    conn.commit()
    conn.close()

    print("")
    print("=" * 55)
    print(f"  DONE: {inserted} rows seeded successfully")
    print(f"  Open dashboard/index.html in your browser")
    print("=" * 55)


if __name__ == "__main__":
    print("=" * 55)
    print("  Plum Escalation - Demo Data Seeder (No API needed)")
    print("=" * 55)
    print("")
    seed()
