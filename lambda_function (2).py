"""
CareConnect — Mock Hospital Tools Lambda
========================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS LAMBDA DOES
  It pretends to be the hospital's back-end systems and returns SYNTHETIC (fake)
  data for three operations the Task/Tool Agent can call through AgentCore Gateway:
    - check_appointment_status  -> returns a fake appointment
    - check_refill_eligibility  -> returns a fake "eligible" result
    - stage_refill_request      -> PREPARES a refill but marks submitted=False
  The refill is only STAGED for human approval — it is never actually submitted.

HOW TO DEPLOY (console)
  1. AWS Lambda → Create function → Python runtime.
  2. Name it exactly:  careconnect-mock-hospital-tools
     (The Gateway target points at this function — keep the name consistent.)
  3. Paste this file into lambda_function.py and click Deploy.
  4. The AgentCore Gateway will attach to this Lambda as its tool target.

HOW THE TOOL NAME ARRIVES
  AgentCore Gateway passes the called tool name in the Lambda context as
  "bedrockAgentCoreToolName" in the format  <targetName>___<toolName>.
  get_tool_name() extracts just the tool name after the "___".

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - All data here is synthetic. In a real system you would replace each branch
    with a real (authenticated) call to your hospital systems — but NEVER let
    stage_refill_request actually submit without human approval.
"""

import uuid


# ---------------------------------------------------------------------------
# Work out which tool the Gateway is asking us to run.
# The name arrives as "<targetName>___<toolName>" — we want the part after ___.
# ---------------------------------------------------------------------------
def get_tool_name(event, context):
    try:
        custom = context.client_context.custom
        full_tool_name = custom.get("bedrockAgentCoreToolName", "")
        if "___" in full_tool_name:
            return full_tool_name.split("___", 1)[1]
        return full_tool_name
    except Exception:
        # Fallback for direct testing: allow {"_tool_name": "..."} in the event.
        return event.get("_tool_name", "")


# ---------------------------------------------------------------------------
# Lambda entry point — routes to the right synthetic operation.
# ---------------------------------------------------------------------------
def lambda_handler(event, context):
    tool_name = get_tool_name(event, context)

    # --- Tool 1: check a (fake) appointment ---
    if tool_name == "check_appointment_status":
        patient_reference = event.get("patient_reference", "PATIENT-DEMO-001")
        return {
            "patient_reference": patient_reference,
            "appointment_status": "scheduled",
            "department": "Gastroenterology",
            "appointment_reference": "APT-DEMO-1001",
        }

    # --- Tool 2: check (fake) refill eligibility ---
    elif tool_name == "check_refill_eligibility":
        drug = event.get("drug", "Unknown")
        return {
            "drug": drug,
            "eligible": True,
            "refills_remaining": 2,
            "data_type": "synthetic",
        }

    # --- Tool 3: STAGE a refill (never submitted; awaits human approval) ---
    elif tool_name == "stage_refill_request":
        drug = event.get("drug", "Unknown")
        idempotency_key = event.get("idempotency_key", str(uuid.uuid4()))
        return {
            "action": "submit_refill",
            "drug": drug,
            "status": "awaiting_approval",
            "idempotency_key": idempotency_key,
            "submitted": False,  # <-- IMPORTANT: never flip this to True automatically
        }

    # --- Unknown tool name ---
    return {"error": "Unknown tool", "tool_name": tool_name}
