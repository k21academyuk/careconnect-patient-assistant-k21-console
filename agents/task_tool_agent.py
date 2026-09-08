"""
CareConnect — Task and Tool Agent
=================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS AGENT DOES
  It connects to the AgentCore Gateway and uses three SYNTHETIC hospital tools:
  check appointment status, check refill eligibility, and stage a refill request
  for human approval. A staged refill is only PREPARED — it is never submitted.

HOW TO USE
  1. Set the Gateway URL you copied from the AgentCore console:
         export CARECONNECT_GATEWAY_URL="<YOUR_GATEWAY_URL>"     # <-- UPDATE THIS
     Example:
         export CARECONNECT_GATEWAY_URL="https://example.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
  2. (Optional) set the region if not us-east-1:
         export AWS_REGION="us-east-1"
  3. Run it:
         python task_tool_agent.py
  4. Try: "Check the appointment status for PATIENT-DEMO-001."; type 'exit' to stop.

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - CARECONNECT_GATEWAY_URL: must be YOUR gateway URL (from the Gateway step).
  - AWS_REGION: change if you did not build in us-east-1.
"""

import os
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

# ---------------------------------------------------------------------------
# Read the Gateway URL from an environment variable.
# UPDATE THIS by exporting CARECONNECT_GATEWAY_URL before running.
# ---------------------------------------------------------------------------
GATEWAY_URL = os.environ.get("CARECONNECT_GATEWAY_URL")
if not GATEWAY_URL:
    raise ValueError("CARECONNECT_GATEWAY_URL is not configured.")

# UPDATE THIS if you built in a different region.
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


# ---------------------------------------------------------------------------
# Build the secure (IAM-signed) transport to the Gateway, then the MCP client
# that lets the agent discover and call the Gateway's tools.
# ---------------------------------------------------------------------------
def create_transport():
    return aws_iam_streamablehttp_client(
        endpoint=GATEWAY_URL,
        aws_region=AWS_REGION,
        aws_service="bedrock-agentcore",
    )


mcp_client = MCPClient(create_transport)


# ---------------------------------------------------------------------------
# Strict operational rules — especially: a staged refill is never "submitted".
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are the CareConnect Task and Tool Agent for Riverside Health.
Your role is limited to operational tool use.
You may:
1. Check synthetic appointment status.
2. Check synthetic refill eligibility.
3. Stage a refill request for human approval.
Important safety rules:
1. Never diagnose medical conditions.
2. Never recommend medication.
3. Never recommend dosage changes.
4. Never claim that a staged refill has been submitted.
5. stage_refill_request only prepares an action.
6. A staged refill must remain awaiting_approval.
7. Never change submitted=false to true.
8. Never invent information that was not returned by a tool.
9. Use only the tools supplied through AgentCore Gateway.
10. All information in this lab is synthetic.
For any refill action, clearly tell the user that the request
has been staged and still requires human approval.
"""


# ---------------------------------------------------------------------------
# Main loop: open the Gateway connection, load tools, and chat in the terminal.
# ---------------------------------------------------------------------------
def main():
    print("\nCareConnect Task and Tool Agent")
    print("Type 'exit' to stop.\n")

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        print("Gateway tools loaded successfully.\n")

        agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools)

        while True:
            request = input("Request: ").strip()

            if request.lower() in ["exit", "quit"]:
                print("Task and Tool Agent stopped.")
                break

            if not request:
                continue

            response = agent(request)
            print("\nResponse:\n")
            print(response)
            print()


if __name__ == "__main__":
    main()
