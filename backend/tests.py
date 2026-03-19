"""
PLUM Insurance Complaint Routing — Test Suite
Tests all 6 spec test cases + edge cases.

Run: python tests.py
"""

import sys
from router import route_complaint
from departments import rule_based_route, detect_red_flags, generate_tags

# ── ANSI colours ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def check(label: str, condition: bool, got=None, expected=None):
    if condition:
        print(f"  {GREEN}✓{RESET} {label}")
        return True
    else:
        detail = f" (got: {got!r}, expected: {expected!r})" if got is not None else ""
        print(f"  {RED}✗{RESET} {label}{detail}")
        return False


def run_test(name: str, complaint_text: str, assertions: list[tuple]) -> bool:
    """Run a single test case. assertions = list of (label, condition_fn)."""
    print(f"\n{BOLD}{CYAN}>> {name}{RESET}")
    print(f"  Message: {complaint_text[:80]}{'...' if len(complaint_text) > 80 else ''}")

    result = route_complaint(complaint_text, use_ai=False)  # fast rule-based for tests
    print(f"  → Dept: {result['primary_department']['short']} | "
          f"Confidence: {result['confidence_score']}% | "
          f"Priority: {result['priority_level']} | "
          f"Decision: {result['routing_decision']}")
    print(f"  → Red flags: {result['red_flags']}")
    print(f"  → Tags: {result['tags']}")

    passed = 0
    total  = len(assertions)
    for label, condition in assertions:
        ok = check(label, condition(result))
        if ok:
            passed += 1

    status = f"{GREEN}PASSED{RESET}" if passed == total else f"{RED}FAILED ({passed}/{total}){RESET}"
    print(f"  {status}")
    return passed == total


def main():
    print(f"\n{BOLD}{'='*60}")
    print("  PLUM Insurance — Complaint Routing Test Suite")
    print(f"{'='*60}{RESET}")

    all_passed = []

    # ── Test 1: Claim rejection ─────────────────────────────
    all_passed.append(run_test(
        "TC-01: Claim Rejection → Claims Team",
        "My health insurance claim for hospitalization has been rejected without any proper reason. "
        "The claim was submitted 30 days ago and I have all the required documents. "
        "Please resolve this immediately.",
        [
            ("Primary dept = Claims Team (2)",
             lambda r: r["primary_department"]["id"] == 2),
            ("Priority HIGH or CRITICAL",
             lambda r: r["priority_level"] in ("HIGH", "CRITICAL")),
            ("Confidence >= 70",
             lambda r: r["confidence_score"] >= 70),
        ]
    ))

    # ── Test 2: Legal threat + IRDAI ───────────────────────
    all_passed.append(run_test(
        "TC-02: Legal Threat → Legal & Compliance",
        "I am writing this as a formal legal notice. Your company has repeatedly denied my legitimate "
        "insurance claim and I will be filing a complaint with IRDAI and approaching consumer court "
        "if this is not resolved within 48 hours.",
        [
            ("Primary dept = Legal & Compliance (4)",
             lambda r: r["primary_department"]["id"] == 4),
            ("Priority CRITICAL",
             lambda r: r["priority_level"] == "CRITICAL"),
            ("legal_threat flag present",
             lambda r: "legal_threat" in r["red_flags"]),
            ("Confidence >= 80",
             lambda r: r["confidence_score"] >= 80),
        ]
    ))

    # ── Test 3: Repeat complaint → GRO ─────────────────────
    all_passed.append(run_test(
        "TC-03: Repeat Complaint → GRO",
        "This is the third time I am complaining about the same issue. My previous complaints "
        "(ticket #12345 and #12346) were closed without resolution. I need formal escalation "
        "and a senior manager to handle this.",
        [
            ("Primary dept = GRO (3)",
             lambda r: r["primary_department"]["id"] == 3),
            ("Priority CRITICAL",
             lambda r: r["priority_level"] == "CRITICAL"),
            ("repeat_complaint flag present",
             lambda r: "repeat_complaint" in r["red_flags"]),
            ("escalation_request flag present",
             lambda r: "escalation_request" in r["red_flags"]),
        ]
    ))

    # ── Test 4: Hospital / cashless ────────────────────────
    all_passed.append(run_test(
        "TC-04: Cashless Denial → Hospital & Provider",
        "The hospital is refusing cashless treatment for my father's surgery. "
        "The pre-authorization was applied 2 days ago but no response from TPA desk. "
        "My father needs immediate surgery and this is a medical emergency.",
        [
            ("Primary dept = Hospital & Provider (6)",
             lambda r: r["primary_department"]["id"] == 6),
            ("medical_emergency flag present",
             lambda r: "medical_emergency" in r["red_flags"]),
            ("Priority HIGH or CRITICAL",
             lambda r: r["priority_level"] in ("HIGH", "CRITICAL")),
        ]
    ))

    # ── Test 5: Tech / app issue ───────────────────────────
    all_passed.append(run_test(
        "TC-05: App Bug → Product/Tech",
        "The Plum app keeps crashing every time I try to upload my claim documents. "
        "I have tried reinstalling but the app is not working. The portal is also down. "
        "This is a technical issue preventing me from submitting my claim.",
        [
            ("Primary dept = Product/Tech (9)",
             lambda r: r["primary_department"]["id"] == 9),
            ("Priority HIGH or CRITICAL",
             lambda r: r["priority_level"] in ("HIGH", "CRITICAL")),
            ("Confidence >= 70",
             lambda r: r["confidence_score"] >= 70),
        ]
    ))

    # ── Test 6: Corporate / HR ─────────────────────────────
    all_passed.append(run_test(
        "TC-06: Corporate Complaint → Account Management",
        "We are a corporate client with 500 employees. Our HR team has been trying to add "
        "new employees to the group policy for the last 2 weeks but nothing has happened. "
        "This is causing serious issues with our employee benefits program.",
        [
            ("Primary dept = Account Management (7)",
             lambda r: r["primary_department"]["id"] == 7),
            ("Priority HIGH",
             lambda r: r["priority_level"] in ("HIGH", "CRITICAL")),
            ("Confidence >= 70",
             lambda r: r["confidence_score"] >= 70),
        ]
    ))

    # ── Edge Cases ─────────────────────────────────────────
    print(f"\n{BOLD}── Edge Cases ──────────────────────────────────────────{RESET}")

    # General inquiry → Customer Support (default)
    all_passed.append(run_test(
        "EC-01: General Inquiry → Customer Support (default)",
        "Hi, how do I register on the Plum portal? I need help with the login process.",
        [
            ("Primary dept = Customer Support (1)",
             lambda r: r["primary_department"]["id"] == 1),
            ("Priority LOW",
             lambda r: r["priority_level"] == "LOW"),
        ]
    ))

    # Social media threat
    result_ec2 = route_complaint(
        "I will post about this on Twitter and LinkedIn. Your service is disgusting and everyone should know how you treat customers!",
        use_ai=False
    )
    print(f"\n{BOLD}{CYAN}>> EC-02: Social Media Threat -- Red Flag Detection{RESET}")
    check("social_media_threat flag present",
          "social_media_threat" in result_ec2["red_flags"])
    check("angry_language flag present",
          "angry_language" in result_ec2["red_flags"])
    all_passed.append("social_media_threat" in result_ec2["red_flags"])

    # ── Summary ────────────────────────────────────────────
    total_tests = len(all_passed)
    total_passed = sum(bool(x) for x in all_passed)

    print(f"\n{BOLD}{'='*60}")
    if total_passed == total_tests:
        print(f"  {GREEN}ALL {total_tests} TESTS PASSED ✓{RESET}")
    else:
        print(f"  {RED}{total_passed}/{total_tests} tests passed{RESET}")
    print(f"{'='*60}{RESET}\n")

    return 0 if total_passed == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
