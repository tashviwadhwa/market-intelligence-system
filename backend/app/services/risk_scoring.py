"""
Hybrid risk scoring: combines the LLM's risk judgement with transparent rules.

How it works, in three steps:
  1. RULES   - look for warning signs in the text (e.g. "ban", "raises $200M")
               and add up points. Every rule that fires is recorded, so the
               result can always be explained.
  2. FUSION  - turn both opinions into numbers (LOW=1, MEDIUM=2, HIGH=3) and
               take a weighted average. The LLM's weight depends on how
               confident it says it is; the rules get the rest.
  3. SAFETY  - flag the event for human review when the LLM and the rules
               strongly disagree, and never let a confirmed regulatory
               action be scored LOW.
"""
import re

LEVEL_TO_NUMBER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

# Each rule: a name, the words/phrases that trigger it, and how many points it adds.
# A rule adds its points once, however many of its words appear.
RULES = [
    {
        "name": "regulatory_action",
        "points": 3,
        "patterns": [r"\bban(ned)?\b", r"\binvestigation\b", r"\bprobe\b", r"\braid(s|ed)?\b",
                     r"\blawsuit\b", r"\bpenalt(y|ies)\b", r"\bfined\b", r"\bcci\b",
                     r"\bfssai\b", r"\blicen[cs]e (cancelled|suspended|revoked)\b",
                     r"\bshow[- ]cause notice\b"],
    },
    {
        "name": "funding_or_ipo",
        "points": 2,
        "patterns": [r"\braise[sd]?\b", r"\bfunding\b", r"\bseries [a-h]\b", r"\bipo\b",
                     r"\bvaluation\b", r"\binvest(s|ed|ment)\b"],
    },
    {
        "name": "large_amount",
        "points": 1,
        # e.g. "$200 million", "Rs 1,500 crore", "₹500 cr", "1.2 billion"
        "patterns": [r"(\$|rs\.?|inr|₹|usd)\s?[\d,.]+\s?(m|mn|million|bn|billion|cr|crore)\b",
                     r"\b[\d,.]+\s?(million|billion|crore)\b"],
    },
    {
        "name": "market_expansion",
        "points": 2,
        "patterns": [r"\bexpan(d|ds|ded|sion)\b", r"\blaunch(es|ed)? (in|across)\b", r"\bnew cities\b",
                     r"\bdark stores?\b", r"\benters?\b", r"\bentry into\b"],
    },
    {
        "name": "price_war",
        "points": 2,
        "patterns": [r"\bprice cuts?\b", r"\bcuts? (prices|fees)\b", r"\bdiscounts?\b",
                     r"\bfree delivery\b", r"\bzero (delivery )?fees?\b", r"\bcashback\b",
                     r"\bslash(es|ed)?\b"],
    },
]

# More independent sources reporting the same event = more believable.
def source_points(source_count: int) -> int:
    if source_count >= 3:
        return 2
    if source_count == 2:
        return 1
    return 0

# How much we trust the LLM, based on its own stated confidence.
LLM_WEIGHT_BY_CONFIDENCE = {"HIGH": 0.7, "MEDIUM": 0.6, "LOW": 0.4}

MAX_RULE_POINTS = 8          # points at which the rules alone say "HIGH"
DISAGREEMENT_FOR_REVIEW = 2  # LOW vs HIGH (gap of 2) -> ask a human


def apply_rules(text: str, source_count: int = 1):
    """Return (total_points, list_of_rules_that_fired)."""
    text = (text or "").lower()
    fired = []
    for rule in RULES:
        matches = []
        for pattern in rule["patterns"]:
            found = re.search(pattern, text)
            if found:
                matches.append(found.group(0))
        if matches:
            fired.append({"rule": rule["name"], "points": rule["points"], "matched": matches})

    extra = source_points(source_count)
    if extra:
        fired.append({"rule": "multiple_sources", "points": extra,
                      "matched": [f"{source_count} sources"]})

    total = sum(r["points"] for r in fired)
    return total, fired


def points_to_number(points: int) -> float:
    """0 points -> 1.0 (LOW), 4 -> 2.0 (MEDIUM), 8 or more -> 3.0 (HIGH)."""
    return 1 + min(points, MAX_RULE_POINTS) / (MAX_RULE_POINTS / 2)


def number_to_level(value: float) -> str:
    if value < 1.67:
        return "LOW"
    if value < 2.34:
        return "MEDIUM"
    return "HIGH"


def hybrid_score(text: str, llm_risk_level: str, llm_confidence: str = "MEDIUM",
                 source_count: int = 1) -> dict:
    """Combine the LLM's risk level with the rule-based score."""
    llm_level = (llm_risk_level or "MEDIUM").upper()
    confidence = (llm_confidence or "MEDIUM").upper()
    llm_number = LEVEL_TO_NUMBER.get(llm_level, 2)

    # 1. Rules
    rule_points, rules_fired = apply_rules(text, source_count)
    rule_number = points_to_number(rule_points)

    # 2. Fusion: weighted average of the two opinions
    llm_weight = LLM_WEIGHT_BY_CONFIDENCE.get(confidence, 0.6)
    final_number = llm_weight * llm_number + (1 - llm_weight) * rule_number
    final_level = number_to_level(final_number)

    # 3. Safety rules
    safety_notes = []
    regulatory = any(r["rule"] == "regulatory_action" for r in rules_fired)
    if regulatory and source_count >= 2 and final_level == "LOW":
        final_level = "MEDIUM"
        safety_notes.append("Raised to MEDIUM: regulatory action reported by 2+ sources.")

    disagreement = abs(llm_number - rule_number)
    needs_review = disagreement >= DISAGREEMENT_FOR_REVIEW - 0.01
    if needs_review:
        safety_notes.append("LLM and rules strongly disagree: please review by hand.")

    return {
        "final_risk_level": final_level,
        "final_score": round(final_number, 2),
        "llm_risk_level": llm_level,
        "llm_confidence": confidence,
        "llm_weight": llm_weight,
        "rule_risk_level": number_to_level(rule_number),
        "rule_points": rule_points,
        "rules_fired": rules_fired,
        "needs_review": needs_review,
        "notes": safety_notes,
    }
