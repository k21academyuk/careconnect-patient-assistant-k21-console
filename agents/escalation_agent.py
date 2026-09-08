"""
CareConnect — Escalation Agent
==============================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS AGENT DOES
  When a patient asks something clinical, CareConnect must NOT answer — it must
  hand off to a human. This module records a durable ticket in DynamoDB and
  starts a Step Functions approval workflow so a clinician can take over.

HOW TO USE
  1. Set the Step Functions state machine ARN you created earlier:
         export CARECONNECT_STATE_MACHINE_ARN="<YOUR_STATE_MACHINE_ARN>"   # <-- UPDATE THIS
  2. Run it:
         python escalation_agent.py
  It creates a sample escalation ticket and starts the workflow.

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - CARECONNECT_STATE_MACHINE_ARN: must be YOUR state machine ARN.
  - TABLE_NAME: change if you named the DynamoDB table differently.
  - region_name: change if you did not build in us-east-1.
"""

import boto3
import uuid
import json
import os
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# AWS clients. UPDATE region_name if you did not build in us-east-1.
# ---------------------------------------------------------------------------
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
stepfunctions = boto3.client("stepfunctions", region_name="us-east-1")

# UPDATE THIS if your DynamoDB table has a different name.
TABLE_NAME = "careconnect-escalations"

# UPDATE THIS by exporting CARECONNECT_STATE_MACHINE_ARN before running.
STATE_MACHINE_ARN = os.environ.get("CARECONNECT_STATE_MACHINE_ARN")

table = dynamodb.Table(TABLE_NAME)


# ---------------------------------------------------------------------------
# Save an escalation ticket to DynamoDB. Returns the new ticket's ID.
# 'expires_at' is 30 days out (2592000 seconds) so tickets auto-clean via TTL.
# ---------------------------------------------------------------------------
def create_escalation_ticket(reason, category, request_details):
    ticket_id = str(uuid.uuid4())
    item = {
        "ticket_id": ticket_id,
        "category": category,
        "reason": reason,
        "request_details": request_details,
        "status": "pending_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 2592000,
    }
    table.put_item(Item=item)
    return ticket_id


# ---------------------------------------------------------------------------
# Start the Step Functions approval workflow for a given ticket.
# ---------------------------------------------------------------------------
def start_approval_workflow(ticket_id):
    response = stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input=json.dumps({"ticket_id": ticket_id}),
    )
    return response["executionArn"]


# ---------------------------------------------------------------------------
# The full escalation: create a ticket, then start the workflow. Returns a
# patient-facing message plus the ticket ID and workflow execution.
# ---------------------------------------------------------------------------
def escalate(reason, category, request_details):
    ticket_id = create_escalation_ticket(reason, category, request_details)
    execution = start_approval_workflow(ticket_id)
    return {
        "message": "Your request has been escalated to a human reviewer.",
        "ticket_id": ticket_id,
        "workflow_execution": execution,
        "status": "pending_review",
    }


# ---------------------------------------------------------------------------
# Demo: escalate a sample clinical question and print the result.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = escalate(
        reason="Medication timing question requires clinician review.",
        category="clinical_question",
        request_details={
            "patient_request": "Should I stop my medication before my procedure?"
        },
    )
    print(json.dumps(result, indent=2))
