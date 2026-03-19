"""
PLUM Insurance — Department reference data and routing decision tree.
"""

DEPARTMENTS = {
    1: {
        "name": "Customer Support / Member Experience",
        "short": "Customer Support",
        "sla_hours": 72,
        "priority_default": "LOW",
        "keywords": [
            "general inquiry", "basic help", "how to", "process question",
            "registration", "login", "password", "account access",
            "bill inquiry", "information", "how do i", "query",
        ],
    },
    2: {
        "name": "Claims Team (Operations)",
        "short": "Claims Team",
        "sla_hours": 24,
        "priority_default": "HIGH",
        "keywords": [
            # Core claim keywords
            "claim status", "claim pending", "claim rejected", "claim delayed",
            "claim documents", "claim payment", "reimbursement", "tpa",
            "claim", "reimbursement pending", "claim not settled",
            "insurance claim", "submitted claim",
            # From Excel (High priority)
            "claim stuck", "delayed claim", "wrong rejection", "partial approval",
            "billing hold", "approval stuck", "pending claim",
            # From Excel (Medium priority)
            "billing issue", "cashless issue", "delayed claim", "urgent approval",
        ],
    },
    3: {
        "name": "Grievance Redressal Cell (GRO)",
        "short": "GRO",
        "sla_hours": 4,
        "priority_default": "CRITICAL",
        "keywords": [
            "escalation", "formal complaint", "grievance", "dispute resolution",
            "previous complaint unresolved", "ombudsman", "third complaint",
            "second complaint", "again complaining", "already complained",
            "ticket closed without", "not resolved yet", "formal investigation",
        ],
    },
    4: {
        "name": "Legal & Compliance",
        "short": "Legal & Compliance",
        "sla_hours": 4,
        "priority_default": "CRITICAL",
        "keywords": [
            "legal action", "court", "regulatory", "compliance", "lawsuit",
            "legal notice", "policy violation", "irdai", "consumer forum",
            "consumer court", "legal", "sue", "file case", "insurance regulator",
            # From Excel (High priority)
            "irdai complaint", "non-compliance", "policy not honored", "ombudsman",
        ],
    },
    5: {
        "name": "Insurer Coordination Team",
        "short": "Insurer Coordination",
        "sla_hours": 24,
        "priority_default": "HIGH",
        "keywords": [
            "insurer response", "coordination needed", "third-party intervention",
            "underwriter issue", "insurance company", "insurer not responding",
            "tpa coordination", "insurer delay",
        ],
    },
    6: {
        "name": "Hospital / Provider Network Team",
        "short": "Hospital & Provider",
        "sla_hours": 24,
        "priority_default": "HIGH",
        "keywords": [
            "hospital billing", "cashless process", "hospital issue",
            "in-network provider", "out-of-network", "doctor billing",
            "medical bill", "hospital", "cashless", "pre-authorization",
            "pre-auth", "admission", "discharge", "tpa desk",
            # From Excel (High priority)
            "cashless denied", "admission denied", "billing hold", "deposit demanded",
            "hospital refusing", "discharge denied", "er admission", "critical care",
            "life support", "ventilator", "oxygen support", "respiratory failure",
            "severe bleeding", "brain hemorrhage", "cardiac arrest", "code blue",
        ],
    },
    7: {
        "name": "Account Management (Corporate/B2B)",
        "short": "Account Management",
        "sla_hours": 24,
        "priority_default": "HIGH",
        "keywords": [
            "corporate account", "employer complaint", "hr escalation",
            "group policy", "employee benefit", "company billing",
            "corporate", "company", "employees", "staff", "hr", "b2b",
            "bulk", "group", "organization", "onboarding employees",
        ],
    },
    8: {
        "name": "Quality & Audit Team",
        "short": "Quality & Audit",
        "sla_hours": 48,
        "priority_default": "MEDIUM",
        "keywords": [
            "service quality", "repeat issue", "complaint quality",
            "audit", "process improvement", "sla violation",
            "poor service", "quality", "breach of", "policy breach",
        ],
    },
    9: {
        "name": "Product / Tech Team",
        "short": "Product/Tech",
        "sla_hours": 24,
        "priority_default": "HIGH",
        "keywords": [
            "app bug", "app crash", "system error", "website issue",
            "portal down", "technical issue", "login error",
            "app not working", "app", "website", "portal", "technical",
            "not loading", "error", "crash", "bug", "not opening",
        ],
    },
}


# Routing decision tree — evaluated in priority order, first match wins
# Format: (condition_fn, primary_dept_id, secondary_dept_ids)
def build_routing_tree():
    """Returns ordered list of (label, dept_id, secondary_ids, detector_fn)."""
    return [
        {
            "label": "repeat_escalation",
            "dept": 3,
            "secondary": [2, 8],
            "check": lambda t: any(k in t for k in [
                "third complaint", "second complaint", "again complain",
                "already complained", "ticket closed without", "not resolved yet",
                "formal investigation", "previous complaint", "unresolved",
                "same issue", "still not resolved", "nth time",
            ]),
        },
        {
            "label": "legal_threat",
            "dept": 4,
            "secondary": [3],
            "check": lambda t: any(k in t for k in [
                "legal action", "consumer court", "consumer forum",
                "lawsuit", "legal notice", "file case",
                "irdai", "ombudsman", "regulatory",
                "i will sue", "will sue", "going to sue",
                # From Excel
                "irdai complaint", "non-compliance", "policy not honored",
            ]) or (" court" in t and "consumer" not in t and "report" not in t),
        },
        {
            "label": "tech_issue",
            "dept": 9,
            "secondary": [1],
            "check": lambda t: any(k in t for k in [
                "app crash", "app not working", "app bug", "portal down",
                "system error", "website issue", "login error",
                "not loading", "technical issue", "app is not", "crashes",
            ]),
        },
        {
            "label": "hospital_billing",
            "dept": 6,
            "secondary": [5],
            "check": lambda t: any(k in t for k in [
                "cashless", "pre-auth", "pre-authorization",
                "medical bill", "hospital billing", "tpa desk",
                "doctor billing", "in-network", "out-of-network",
                # From Excel (High priority hospital keywords)
                "cashless denied", "admission denied", "billing hold",
                "deposit demanded", "hospital refusing", "discharge denied",
                "er admission", "critical care", "life support", "ventilator",
                "oxygen support", "respiratory failure", "severe bleeding",
                "brain hemorrhage", "cardiac arrest", "code blue",
            ]) or ("hospital" in t and any(k in t for k in ["billing", "cashless", "treatment", "surgery", "refusing", "denied"])),
        },
        {
            "label": "claim_issue",
            "dept": 2,
            "secondary": [5],
            "check": lambda t: any(k in t for k in [
                "claim rejected", "claim pending", "claim delayed", "claim status",
                "claim documents", "claim payment", "reimbursement",
                "claim not settled", "insurance claim", "submitted claim",
                # From Excel
                "claim stuck", "wrong rejection", "partial approval",
                "delayed claim", "approval stuck", "billing hold",
                "pending claim", "urgent approval",
            ]) or (
                "tpa" in t and not any(k in t for k in ["cashless", "hospital", "pre-auth", "pre-authorization"])
            ) or (
                "claim" in t and not any(k in t for k in ["cashless", "hospital", "pre-auth", "pre-authorization"])
            ),
        },
        {
            "label": "corporate",
            "dept": 7,
            "secondary": [9],
            "check": lambda t: any(k in t for k in [
                "corporate", "hr", "employees", "group policy",
                "employer", "company", "staff", "bulk", "b2b",
                "organization", "onboarding employees",
            ]),
        },
        {
            "label": "service_quality",
            "dept": 8,
            "secondary": [1],
            "check": lambda t: any(k in t for k in [
                "service quality", "repeat issue", "sla violation",
                "poor service", "audit", "quality", "policy breach",
            ]),
        },
        {
            "label": "insurer_coordination",
            "dept": 5,
            "secondary": [2],
            "check": lambda t: any(k in t for k in [
                "insurer", "insurer not responding", "underwriter",
                "coordination needed", "insurance company delay",
            ]),
        },
    ]


ROUTING_TREE = build_routing_tree()


def get_department(dept_id: int) -> dict:
    return DEPARTMENTS.get(dept_id, DEPARTMENTS[1])


def rule_based_route(complaint_text: str) -> dict:
    """
    Fast rule-based routing — runs without AI.
    Returns primary_dept_id, secondary_dept_ids, confidence, routing_label.
    """
    text = complaint_text.lower()

    for rule in ROUTING_TREE:
        if rule["check"](text):
            return {
                "primary_dept_id": rule["dept"],
                "secondary_dept_ids": rule["secondary"],
                "routing_label": rule["label"],
                "confidence_score": 80,  # rule-based = 80% confidence
            }

    # Default: Customer Support
    return {
        "primary_dept_id": 1,
        "secondary_dept_ids": [],
        "routing_label": "default",
        "confidence_score": 45,
    }


def detect_red_flags(text: str) -> list:
    """Detect red flags from complaint text."""
    text_lower = text.lower()
    flags = []

    if any(k in text_lower for k in ["third", "again", "previous complaint", "same issue", "nth time", "already complained"]):
        flags.append("repeat_complaint")
    if any(k in text_lower for k in ["irdai", "consumer court", "ombudsman", "legal notice", "lawsuit", "will sue", "i will sue", "legal action"]):
        flags.append("legal_threat")
    if any(k in text_lower for k in ["social media", "linkedin", "twitter", "facebook", "post about", "going viral", "publicly"]):
        flags.append("social_media_threat")
    if any(k in text_lower for k in [
        "angry", "furious", "outrageous", "disgusting", "unacceptable",
        "fraud", "cheating", "scam",
        # From Excel (emotional/frustrated medium priority)
        "disappointed", "frustrated", "bad experience", "delay unacceptable",
        "serious issue",
    ]):
        flags.append("angry_language")
    if any(k in text_lower for k in ["formal complaint", "formal investigation", "escalate", "escalation", "formal grievance"]):
        flags.append("escalation_request")
    if any(k in text_lower for k in [
        "emergency", "urgent", "immediately", "critical", "life-threatening",
        "icu", "surgery",
        # From Excel (High priority medical)
        "cardiac arrest", "code blue", "brain hemorrhage", "heart attack",
        "stroke", "coma", "organ failure", "ventilator", "life support",
        "respiratory failure", "unconscious", "collapse", "fatal",
        "severe bleeding", "life-threatening", "oxygen support",
    ]):
        flags.append("medical_emergency")

    return flags


def generate_tags(text: str, dept_id: int) -> list:
    """Generate 3-5 relevant tags for a complaint."""
    text_lower = text.lower()
    tags = set()

    tag_map = {
        "claim": ["claim", "reimbursement", "tpa"],
        "delay": ["delay", "pending", "waiting", "not yet", "still"],
        "rejection": ["rejected", "denial", "denied", "not approved"],
        "hospital": ["hospital", "cashless", "admission", "discharge"],
        "legal": ["legal", "court", "irdai", "sue", "lawsuit"],
        "app_bug": ["app", "crash", "bug", "technical", "portal"],
        "corporate": ["corporate", "hr", "employees", "group policy"],
        "escalation": ["escalation", "formal", "grievance", "previous complaint"],
        "urgent": ["urgent", "emergency", "immediately", "critical"],
        "quality": ["quality", "poor service", "sla", "audit"],
        "billing": ["billing", "charges", "amount", "payment", "invoice"],
        "repeat": ["again", "third", "second", "same issue", "nth"],
    }

    for tag, keywords in tag_map.items():
        if any(k in text_lower for k in keywords):
            tags.add(tag)

    # Always add department-specific tag
    dept_tags = {
        1: "support", 2: "claim", 3: "grievance", 4: "legal",
        5: "insurer", 6: "hospital", 7: "corporate", 8: "quality", 9: "technical"
    }
    tags.add(dept_tags.get(dept_id, "general"))

    return list(tags)[:5]
