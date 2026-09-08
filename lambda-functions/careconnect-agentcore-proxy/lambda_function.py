"""
CareConnect — AgentCore Proxy Lambda (with CORS)
================================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS LAMBDA DOES
  It sits between the public API Gateway and the deployed Supervisor runtime.
  It receives a web request { "prompt": "..." }, calls the AgentCore runtime,
  cleans the streamed response into a single answer, and returns it with the
  CORS headers a browser needs. This build also returns the REAL error text so
  failures are easy to debug.

HOW TO DEPLOY (console)
  1. AWS Lambda → Create function → name it:  careconnect-agentcore-proxy
     Runtime: Python 3.12.
  2. Paste this file into lambda_function.py.
  3. >>> EDIT the three CHANGE markers below (your runtime ARN, region, origin).
  4. Deploy.
  5. Give the Lambda's execution role permission to call the runtime
     (bedrock-agentcore:InvokeAgentRuntime).
  6. Connect it to an API Gateway POST /careconnect route.

>>> THINGS YOU MUST UPDATE ARE MARKED "CHANGE #" BELOW <<<
"""

# ===========================================================================
# >>> CHANGE #1: Add YOUR real AgentCore runtime ARN (from the deploy step).
#     It looks like:
#     arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:runtime/<runtime-id>
# ===========================================================================
AGENT_RUNTIME_ARN = "REPLACE_ME_WITH_YOUR_AGENT_RUNTIME_ARN"

# >>> CHANGE #2: region (leave as-is if your agent is in us-east-1).
AWS_REGION = "us-east-1"

# >>> CHANGE #3 (optional, for production): replace "*" with your CloudFront
#     domain so only your website can call this API.
ALLOWED_ORIGIN = "*"

import json
import re
import traceback
import boto3

# CORS headers applied to EVERY response, including errors and preflight.
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST",
}


# Small helper to build a JSON response with the CORS headers attached.
def _reply(status, obj):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(obj)}


# Remove any <thinking>...</thinking> blocks from the model's text.
def _clean(full_text):
    return re.sub(
        r"<thinking\b[^>]*>.*?</thinking>", "", full_text, flags=re.DOTALL
    ).strip()


# The runtime streams its answer as "server-sent events" (SSE). This pulls the
# text pieces out of that stream and joins them into one string.
def _extract_text_from_sse(raw):
    pieces = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        try:
            evt = json.loads(line[5:].strip())
        except ValueError:
            continue
        text = (
            evt.get("event", {})
            .get("contentBlockDelta", {})
            .get("delta", {})
            .get("text")
        )
        if text:
            pieces.append(text)
    return "".join(pieces)


# ---------------------------------------------------------------------------
# Lambda entry point.
# ---------------------------------------------------------------------------
def lambda_handler(event, context):
    # Handle the browser's CORS preflight (OPTIONS) request first.
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # Read the prompt out of the request body.
    try:
        body = event.get("body") or "{}"
        body = json.loads(body) if isinstance(body, str) else body
        prompt = (body.get("prompt") or "").strip()
    except Exception as e:
        return _reply(400, {"error": "bad body", "detail": str(e)})

    if not prompt:
        return _reply(400, {"error": "Missing 'prompt'."})

    # DIAGNOSTIC 1: confirm the ARN is set and the client can be created.
    diag = {"arn_set": "REPLACE_ME" not in AGENT_RUNTIME_ARN}
    try:
        client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
        diag["client"] = "bedrock-agentcore OK"
        diag["invoke_methods"] = [m for m in dir(client) if "invoke" in m.lower()]
    except Exception as e:
        diag["client_error"] = f"{type(e).__name__}: {e}"
        try:
            import botocore.session

            diag["available_services_with_bedrock"] = [
                s
                for s in botocore.session.get_session().get_available_services()
                if "bedrock" in s or "agent" in s
            ]
        except Exception as e2:
            diag["service_list_error"] = str(e2)
        return _reply(500, {"stage": "client_creation", "diag": diag})

    # DIAGNOSTIC 2: try the invoke and report the exact error if it fails.
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            payload=json.dumps({"prompt": prompt}).encode("utf-8"),
        )
        raw_bytes = response["response"].read()
        raw = (
            raw_bytes.decode("utf-8")
            if isinstance(raw_bytes, (bytes, bytearray))
            else str(raw_bytes)
        )
    except Exception as e:
        return _reply(
            500,
            {
                "stage": "invoke",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "diag": diag,
                "trace": traceback.format_exc()[-1500:],
            },
        )

    # Turn the streamed response into a clean single answer and return it.
    answer = _clean(_extract_text_from_sse(raw)) or _clean(raw)
    return _reply(200, {"answer": answer})
