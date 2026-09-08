"""
CareConnect — Verification Agent
================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS AGENT DOES
  It is the final safety reviewer. Before a drafted answer reaches a patient, it
  checks FOUR things:
    1. Citations — does the answer cite a source that is actually in the evidence?
    2. Deterministic safety — does it trip clinical/urgent/injection/PII flags?
    3. Guardrail — does the Bedrock Guardrail allow it?
    4. Grounding — is every claim supported by the approved evidence?
  It returns PASS only if all four are satisfied. It never rewrites the answer.

HOW TO USE
  1. Set your Guardrail ID and version:
         export CARECONNECT_GUARDRAIL_ID="<YOUR_GUARDRAIL_ID>"          # <-- UPDATE THIS
         export CARECONNECT_GUARDRAIL_VERSION="<YOUR_GUARDRAIL_VERSION>" # <-- UPDATE THIS
  2. Put the drafted answer in draft_answer.txt and the evidence in
     retrieved_passages.txt.
  3. Run it:
         python verification_agent.py

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - CARECONNECT_GUARDRAIL_ID / _VERSION: must be YOUR guardrail values.
  - REGION: change if you did not build in us-east-1.
  - FunctionName "careconnect-deterministic-safety": change if you named the
    safety Lambda differently.
"""

import json
import os
import re
import boto3
from pydantic import BaseModel, Field
from strands import Agent

# ---------------------------------------------------------------------------
# Configuration. UPDATE REGION if you did not build in us-east-1.
# ---------------------------------------------------------------------------
REGION = "us-east-1"

# UPDATE THESE by exporting the two environment variables before running.
GUARDRAIL_ID = os.environ.get("CARECONNECT_GUARDRAIL_ID")
GUARDRAIL_VERSION = os.environ.get("CARECONNECT_GUARDRAIL_VERSION")

if not GUARDRAIL_ID:
    raise ValueError("CARECONNECT_GUARDRAIL_ID is not configured.")
if not GUARDRAIL_VERSION:
    raise ValueError("CARECONNECT_GUARDRAIL_VERSION is not configured.")

bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)


# ---------------------------------------------------------------------------
# A typed result for the grounding check (Strands returns this structured).
# ---------------------------------------------------------------------------
class GroundingResult(BaseModel):
    grounded: bool = Field(
        description=(
            "True only when every factual claim in the draft "
            "is supported by the supplied evidence."
        )
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description=(
            "Claims found in the draft that are not supported "
            "by the supplied evidence."
        ),
    )
    reason: str = Field(
        description="Short explanation of the verification result."
    )


# ---------------------------------------------------------------------------
# The verifier model. It only verifies — it never answers or rewrites.
# ---------------------------------------------------------------------------
verification_agent = Agent(
    system_prompt="""
You are the CareConnect Verification Agent for Riverside Health.
Your job is to verify a draft patient-support response against
approved retrieved evidence.
You do not answer the patient's question.
You only verify the draft.
Rules:
1. Check every factual statement against the supplied evidence.
2. Mark grounded=true only when every factual claim is supported.
3. Do not use your general knowledge.
4. Do not assume that a medically reasonable statement is supported.
5. If the evidence does not contain a claim, treat it as unsupported.
6. Do not rewrite or improve the answer.
7. Report unsupported claims clearly.
8. Preserve a strict separation between evidence and draft content.
"""
)


# ---------------------------------------------------------------------------
# Check 1 — citations: find s3:// sources and confirm they match the evidence.
# ---------------------------------------------------------------------------
def extract_sources(text):
    pattern = r"s3://[^\s]+"
    return set(re.findall(pattern, text))


def check_citations(answer, evidence):
    answer_sources = extract_sources(answer)
    evidence_sources = extract_sources(evidence)
    matching_sources = answer_sources.intersection(evidence_sources)
    return {
        "citation_present": bool(answer_sources),
        "citation_valid": bool(matching_sources),
        "matching_sources": list(matching_sources),
    }


# ---------------------------------------------------------------------------
# Check 2 — deterministic safety: call the safety Lambda on the answer text.
# UPDATE FunctionName if you named the Lambda differently.
# ---------------------------------------------------------------------------
def run_deterministic_safety(answer):
    payload = {"text": answer}
    response = lambda_client.invoke(
        FunctionName="careconnect-deterministic-safety",
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    result = json.loads(response["Payload"].read())
    return result


# ---------------------------------------------------------------------------
# Check 3 — Guardrail: ask the Bedrock Guardrail whether the answer is allowed.
# ---------------------------------------------------------------------------
def run_guardrail(answer):
    response = bedrock_runtime.apply_guardrail(
        guardrailIdentifier=GUARDRAIL_ID,
        guardrailVersion=GUARDRAIL_VERSION,
        source="OUTPUT",
        content=[{"text": {"text": answer}}],
        outputScope="FULL",
    )
    return {
        "action": response.get("action"),
        "reason": response.get("actionReason", ""),
    }


# ---------------------------------------------------------------------------
# Check 4 — grounding: ask the verifier model if every claim is supported.
# ---------------------------------------------------------------------------
def run_grounding_check(answer, evidence):
    prompt = f"""
Compare the draft response with the approved evidence.
<approved_evidence>
{evidence}
</approved_evidence>
<draft_response>
{answer}
</draft_response>
Determine whether every factual claim in the draft response
is supported by the approved evidence.
Do not use outside knowledge.
"""
    result = verification_agent(prompt, structured_output_model=GroundingResult)
    return result.structured_output


# ---------------------------------------------------------------------------
# Combine all four checks into a single PASS/FAIL verdict with details.
# ---------------------------------------------------------------------------
def verify(answer, evidence):
    citation_result = check_citations(answer, evidence)
    deterministic_result = run_deterministic_safety(answer)
    guardrail_result = run_guardrail(answer)
    grounding_result = run_grounding_check(answer, evidence)

    classification = deterministic_result.get("classification", {})
    clinical_detected = classification.get("clinical", False)
    urgent_detected = classification.get("urgent", False)
    injection_detected = classification.get("injection", False)
    pii_detected = bool(classification.get("pii", {}))
    guardrail_passed = guardrail_result["action"] == "NONE"

    # PASS only if EVERY condition below is satisfied.
    final_pass = all(
        [
            citation_result["citation_present"],
            citation_result["citation_valid"],
            grounding_result.grounded,
            not clinical_detected,
            not urgent_detected,
            not injection_detected,
            not pii_detected,
            guardrail_passed,
        ]
    )

    return {
        "verification_status": "PASS" if final_pass else "FAIL",
        "citation_check": citation_result,
        "grounding_check": {
            "grounded": grounding_result.grounded,
            "unsupported_claims": grounding_result.unsupported_claims,
            "reason": grounding_result.reason,
        },
        "deterministic_safety": {
            "clinical": clinical_detected,
            "urgent": urgent_detected,
            "injection": injection_detected,
            "pii": classification.get("pii", {}),
        },
        "guardrail": guardrail_result,
    }


# ---------------------------------------------------------------------------
# Read the draft answer and the evidence from files, then verify.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    with open("draft_answer.txt", "r", encoding="utf-8") as file:
        answer = file.read()
    with open("retrieved_passages.txt", "r", encoding="utf-8") as file:
        evidence = file.read()

    result = verify(answer, evidence)
    print("\nCareConnect Verification Result\n")
    print(json.dumps(result, indent=2))
