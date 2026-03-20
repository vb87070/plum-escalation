import os
import json
import anthropic

# Initialize Anthropic client
# Get a free API key at: https://console.anthropic.com
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

PROMPT_TEMPLATE = """You are an escalation triage assistant for Plum, a B2B health insurance platform serving 4000+ corporate accounts.
You analyze messages sent to the Senior VP of Account Management.
Your job: classify if the message is a real escalation, extract structured data, and recommend action.
Always respond with valid JSON only. No explanation, no markdown, no text outside the JSON object.

Analyze this message received by the Plum VP of Account Management.

Channel: {source_channel}
Sender: {sender_name} ({sender_contact})
Message:
{raw_message}

Return a JSON object with exactly these fields:
{{
  "is_escalation": 1 or 0,
  "account_name": "company or account name extracted, or Unknown",
  "issue_category": "one of: Claim Processing | Health ID | Cashless Facility | Document Upload | Data Correction | Policy Renewal | IRDAI/Legal Threat | Social Media Threat | Training Request | Other",
  "ai_summary": "2-3 sentence summary covering what happened, business impact, and what the customer wants",
  "urgency": "High or Medium or Low",
  "priority_score": 5,
  "action_needed": "one specific action the account manager must take in the next hour",
  "sentiment": "Frustrated or Neutral or Threatening"
}}

Rules:
- is_escalation = 0 for referrals, spam, or non-issues (e.g. my brother wants insurance, share app link)
- is_escalation = 1 for any complaint, delay, claim issue, threat, or service failure
- urgency = High if: legal threat, IRDAI mentioned, policy non-renewal, medical emergency, cashless denial, social media threat, or already delayed past SLA
- urgency = Low if: training request, general inquiry, minor follow-up
- priority_score: integer 1-10 (10 = most critical); factor in urgency + whether already delayed + threat level
- sentiment = Threatening if customer mentions legal action, IRDAI, social media, board escalation, or non-renewal

Return ONLY the JSON object, nothing else."""


def enrich(source_channel: str, sender_name: str, sender_contact: str, raw_message: str) -> dict:
    """
    Call Claude (Anthropic) to classify and enrich an escalation message.
    Returns a dict with all AI-enriched fields.
    Falls back to safe defaults on any error.
    """
    prompt = PROMPT_TEMPLATE.format(
        source_channel=source_channel,
        sender_name=sender_name or "Unknown",
        sender_contact=sender_contact or "Unknown",
        raw_message=raw_message,
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        # Remove markdown code fences if Claude adds them
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        # Extract JSON robustly
        start = raw_text.find("{")
        end   = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        result = json.loads(raw_text[start:end])

        # Normalize all fields
        result["is_escalation"]  = int(result.get("is_escalation", 1))
        result["urgency"]        = result.get("urgency", "Medium")
        result["priority_score"] = int(result.get("priority_score", 5))
        result["sentiment"]      = result.get("sentiment", "Neutral")
        result["issue_category"] = result.get("issue_category", "Other")
        result["account_name"]   = result.get("account_name", "Unknown")
        result["ai_summary"]     = result.get("ai_summary", raw_message[:200])
        result["action_needed"]  = result.get("action_needed", "Review and follow up with customer")

        return result

    except Exception as e:
        print(f"[Claude] Error: {e}. Using keyword-based fallback.")
        return _keyword_fallback(raw_message)


def _keyword_fallback(raw_message: str) -> dict:
    """
    Keyword-based classification when Claude AI is unavailable.
    Detects urgency, sentiment, and issue category from message content.
    """
    msg = raw_message.lower()

    # ── Urgency detection ──────────────────────────────────────
    HIGH_URGENCY = [
        "irdai", "legal action", "consumer court", "will sue", "lawsuit",
        "ombudsman", "cashless denied", "cashless rejection", "medical emergency",
        "icu", "critical condition", "death", "died", "urgent", "immediate",
        "24 hours", "today itself", "escalate now", "social media", "tweet",
        "going viral", "police", "fir", "non-renewal", "policy lapse"
    ]
    LOW_URGENCY = [
        "training", "how to", "general inquiry", "just wanted to know",
        "my brother", "my friend", "referral", "share the link"
    ]

    if any(k in msg for k in HIGH_URGENCY):
        urgency = "High"
        priority_score = 8
    elif any(k in msg for k in LOW_URGENCY):
        urgency = "Low"
        priority_score = 2
    else:
        urgency = "Medium"
        priority_score = 5

    # ── Sentiment detection ────────────────────────────────────
    THREATENING = [
        "legal action", "irdai", "consumer court", "will sue", "ombudsman",
        "social media", "tweet", "post online", "board escalation", "police", "fir"
    ]
    FRUSTRATED = [
        "no response", "not resolved", "waiting since", "follow up", "3 weeks",
        "2 weeks", "month ago", "unacceptable", "disappointed", "disgusted",
        "pathetic", "worst", "useless", "terrible", "horrible", "fed up",
        "still no", "despite", "again and again", "multiple times"
    ]

    if any(k in msg for k in THREATENING):
        sentiment = "Threatening"
        priority_score = min(10, priority_score + 2)
    elif any(k in msg for k in FRUSTRATED):
        sentiment = "Frustrated"
        priority_score = min(10, priority_score + 1)
    else:
        sentiment = "Neutral"

    # ── Issue category detection ───────────────────────────────
    if any(k in msg for k in ["claim", "reimbursement", "tpa", "claim rejected"]):
        issue_category = "Claim Processing"
    elif any(k in msg for k in ["cashless", "hospital", "pre-auth", "admission"]):
        issue_category = "Cashless Facility"
    elif any(k in msg for k in ["irdai", "legal", "court", "sue"]):
        issue_category = "IRDAI/Legal Threat"
    elif any(k in msg for k in ["renew", "renewal", "policy lapse", "expir"]):
        issue_category = "Policy Renewal"
    elif any(k in msg for k in ["health id", "abha", "id card"]):
        issue_category = "Health ID"
    elif any(k in msg for k in ["document", "upload", "kyc", "form"]):
        issue_category = "Document Upload"
    elif any(k in msg for k in ["social media", "tweet", "facebook", "post"]):
        issue_category = "Social Media Threat"
    elif any(k in msg for k in ["training", "how to", "guide", "help"]):
        issue_category = "Training Request"
    else:
        issue_category = "Other"

    # ── is_escalation detection ────────────────────────────────
    NON_ESCALATION = [
        "my brother wants", "my friend wants", "referral", "share the app",
        "download link", "just asking", "general question"
    ]
    is_escalation = 0 if any(k in msg for k in NON_ESCALATION) else 1

    action_map = {
        "High": "URGENT: Contact customer within 1 hour and escalate to department head",
        "Medium": "Assign to relevant team and respond within 24 hours",
        "Low": "Route to standard support queue",
    }

    return {
        "is_escalation": is_escalation,
        "account_name": "Unknown",
        "issue_category": issue_category,
        "ai_summary": f"[Auto-classified] {raw_message[:200]}",
        "urgency": urgency,
        "priority_score": priority_score,
        "action_needed": action_map[urgency],
        "sentiment": sentiment,
    }
