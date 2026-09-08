#!/bin/bash
# ============================================================
# CareConnect environment variables
# Run this whole block on your EC2 dev box BEFORE starting supervisor_agent.py.
#
# >>> LEARNERS: replace each quoted value with YOUR OWN value from the AWS
#     console. The placeholder values below are examples — they will NOT work
#     in your account. Where to find each value is noted above it.
# ============================================================

# Knowledge Base ID — used by retrieval_agent.py to query approved docs.
# Find it at: Amazon Bedrock > Knowledge Bases > (your KB) > Knowledge Base ID
export CARECONNECT_KB_ID="YOUR_KNOWLEDGE_BASE_ID"

# AgentCore Gateway MCP URL — used by task_tool_agent.py for refill/appointment tools.
# Find it at: Bedrock AgentCore > Gateways > (your gateway) > Gateway resource URL
export CARECONNECT_GATEWAY_URL="https://YOUR-GATEWAY.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"

# Bedrock Guardrail ID — used by verification_agent.py for the safety check.
# Find it at: Amazon Bedrock > Guardrails > (your guardrail) > ID
export CARECONNECT_GUARDRAIL_ID="YOUR_GUARDRAIL_ID"

# Guardrail version — the numbered version you published (NOT "Working draft").
export CARECONNECT_GUARDRAIL_VERSION="1"

# Step Functions state machine ARN — used by escalation_agent.py for human review.
# Find it at: Step Functions > State machines > (your workflow) > ARN
export CARECONNECT_STATE_MACHINE_ARN="arn:aws:states:us-east-1:YOUR_ACCOUNT_ID:stateMachine:careconnect-human-approval-workflow"

# (Optional) AWS region if you did not build in us-east-1.
export AWS_REGION="us-east-1"

# ------------------------------------------------------------
# Confirm all five are set (no value should be blank):
# ------------------------------------------------------------
for v in CARECONNECT_KB_ID CARECONNECT_GATEWAY_URL CARECONNECT_GUARDRAIL_ID \
         CARECONNECT_GUARDRAIL_VERSION CARECONNECT_STATE_MACHINE_ARN; do
  echo "$v = ${!v}"
done
