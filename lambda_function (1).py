"""
CareConnect — Deterministic Safety Lambda
=========================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS LAMBDA DOES
  This is the "predictable rules" safety layer — plain Python, no AI. Given a
  piece of text it:
    - classifies it (clinical? urgent? injection attempt? contains PII?)
    - decides must_escalate / must_block
    - masks personal data (email, SSN, MRN, phone)
    - sanitizes retrieved documents by stripping hidden instruction lines
  Because it is rule-based, it behaves the same way every time — which is what
  you want for safety-critical checks.

HOW TO DEPLOY (console)
  1. AWS Lambda → Create function → Author from scratch → Python runtime.
  2. Name it exactly:  careconnect-deterministic-safety
     (Other components call it by this name — if you rename it, update them too.)
  3. Paste this file into lambda_function.py in the Lambda code editor.
  4. Click Deploy.
  5. Test with an event like:  {"text": "Should I double my dose?"}

HOW IT IS CALLED
  Input event:   {"text": "<some text>"}
  Returns:       classification, must_escalate, must_block, masked_text, sanitized_text

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - Add/adjust patterns below if your hospital uses different terminology or
    ID formats (e.g. a different MRN pattern).
"""

import re

# ---------------------------------------------------------------------------
# Patterns that indicate a CLINICAL question (must be escalated, not answered).
# UPDATE THIS list if your organisation phrases things differently.
# ---------------------------------------------------------------------------
CLINICAL_PATTERNS = [
    r"\bdiagnose\b",
    r"\bdiagnosis\b",
    r"\bwhat disease do i have\b",
    r"\bwhat condition do i have\b",
    r"\bshould i take\b",
    r"\bshould i increase\b",
    r"\bshould i decrease\b",
    r"\bdouble (my|the) dose\b",
    r"\bchange (my|the) dose\b",
    r"\bhow much .* should i take\b",
]

# Patterns that indicate an URGENT / emergency situation (must be escalated).
URGENT_PATTERNS = [
    r"\bchest pain\b",
    r"\bsevere difficulty breathing\b",
    r"\bcan't breathe\b",
    r"\bcannot breathe\b",
    r"\bunconscious\b",
    r"\bsevere bleeding\b",
    r"\bpassed out\b",
]

# Patterns that indicate a prompt-injection / manipulation attempt (must block).
MANIPULATION_PATTERNS = [
    r"\bignore previous instructions\b",
    r"\bignore all previous instructions\b",
    r"\boverride (the )?(rules|policy|policies|instructions)\b",
    r"\bignore (the )?(rules|policy|policies)\b",
    r"\breveal (the )?system prompt\b",
    r"\bshow (me )?(the )?system prompt\b",
    r"\bdisregard previous instructions\b",
]

# Personal data (PII) patterns. UPDATE the "mrn" pattern if your medical record
# number format is different from MRN-######## (8 digits).
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "mrn": r"\bMRN-\d{8}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
}

# Lines inside a RETRIEVED document that look like injected instructions and
# should be stripped out before the document is used.
INSTRUCTION_LINE_PATTERNS = [
    r"^\s*ignore previous instructions",
    r"^\s*ignore all previous instructions",
    r"^\s*override .*instructions",
    r"^\s*disregard previous instructions",
    r"^\s*system\s*:",
    r"^\s*developer\s*:",
    r"^\s*assistant\s*:",
]


# ---------------------------------------------------------------------------
# Helper: does any pattern match the text? (case-insensitive)
# ---------------------------------------------------------------------------
def matches(text, patterns):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


# Find which PII types appear, and how many of each.
def find_pii(text):
    findings = {}
    for pii_type, pattern in PII_PATTERNS.items():
        values = re.findall(pattern, text, re.IGNORECASE)
        if values:
            findings[pii_type] = len(values)
    return findings


# Replace personal data with placeholders like [EMAIL], [MRN], etc.
def mask_pii(text):
    masked = text
    replacements = {
        "email": "[EMAIL]",
        "ssn": "[SSN]",
        "mrn": "[MRN]",
        "phone": "[PHONE]",
    }
    for pii_type, pattern in PII_PATTERNS.items():
        masked = re.sub(pattern, replacements[pii_type], masked, flags=re.IGNORECASE)
    return masked


# Remove instruction-like lines from a retrieved document (anti prompt-injection).
def sanitize_retrieved(text):
    safe_lines = []
    for line in text.splitlines():
        suspicious = any(
            re.search(pattern, line, re.IGNORECASE)
            for pattern in INSTRUCTION_LINE_PATTERNS
        )
        if not suspicious:
            safe_lines.append(line)
    return "\n".join(safe_lines)


# Classify a piece of text across all four dimensions.
def classify(text):
    return {
        "clinical": matches(text, CLINICAL_PATTERNS),
        "urgent": matches(text, URGENT_PATTERNS),
        "injection": matches(text, MANIPULATION_PATTERNS),
        "pii": find_pii(text),
    }


# ---------------------------------------------------------------------------
# Lambda entry point. Input: {"text": "..."}  Output: classification + flags.
# ---------------------------------------------------------------------------
def lambda_handler(event, context):
    text = event.get("text", "")
    result = classify(text)
    return {
        "classification": result,
        "must_escalate": (result["clinical"] or result["urgent"]),
        "must_block": result["injection"],
        "masked_text": mask_pii(text),
        "sanitized_text": sanitize_retrieved(text),
    }
