# CareConnect — Scripts & Code (Console / CLI Build)

All the **scripts, Lambda functions, agent code, and templates** from the CareConnect
console/CLI lab, extracted into clean, separate, well-commented files. Download this folder,
open it in **VS Code** (or any text editor), read the comments to understand each piece, and
copy what you need while you follow the lab guide.

> **These files are for reading and copying as you work through the lab.** They are not a
> one-click app — you build CareConnect by following the guide step by step and using these
> files where the guide says "create this file and paste this code."

---

## How to read this folder (start here)

1. Keep the **lab guide** open as your main instructions.
2. When the guide says *"create `<file>.py` and paste this code"*, open the matching file
   here, read its header + comments so you understand what it does, then copy it into place.
3. **Fill in your own AWS values** wherever a comment tells you to. Every editable spot is
   marked with one of these tags so they're easy to find:
   - **`UPDATE THIS`** — a value you must change (e.g. a region or resource name)
   - **`>>> CHANGE #`** — a numbered edit in the proxy Lambda
   - **`>>> LEARNERS`** — a note pointing out something you set for your own account
4. None of the example values (IDs, ARNs, URLs) will work in your account — they are
   placeholders. Replace them with your own from the AWS Console.

---

## What's inside

```
README.md                         ← you are here

agents/                           ← the six specialist agents (run on your EC2 dev box)
  retrieval_agent.py              answers ONLY from approved documents (uses the Knowledge Base)
  document_processing_agent.py    structures retrieved evidence into a clean answer (adds nothing new)
  task_tool_agent.py              calls synthetic hospital tools via the AgentCore Gateway
  verification_agent.py           final safety reviewer: citations + safety + guardrail + grounding
  escalation_agent.py             human hand-off: writes a DynamoDB ticket + starts Step Functions
  supervisor_agent.py             orchestrates all of the above — RUN THIS ONE LAST

lambda-functions/                 ← three AWS Lambda functions (create in the Lambda console)
  careconnect-deterministic-safety/
    lambda_function.py            rule-based safety (clinical / urgent / injection / PII masking)
  careconnect-mock-hospital-tools/
    lambda_function.py            synthetic appointment + refill tools (all data is fake)
  careconnect-agentcore-proxy/
    lambda_function.py            API Gateway → AgentCore runtime proxy (with CORS)
    invoke-agentcore-policy.json  IAM inline policy that lets the proxy call the runtime

frontend/
  config.js                       the ONE file you edit for the S3 + CloudFront frontend

commands/
  set-environment-variables.sh    exports the five values the agents need (edit with YOUR values)
  setup-notes.md                  pip installs + deploy troubleshooting, collected in one place
```

---

## The build order (follow the lab's step numbers)

1. **Retrieval Agent** → `agents/retrieval_agent.py`
2. **Document-Processing Agent** → `agents/document_processing_agent.py`
3. **Deterministic Safety Lambda** → `lambda-functions/careconnect-deterministic-safety/`
4. **Mock Hospital Tools Lambda + Gateway** → `lambda-functions/careconnect-mock-hospital-tools/` then `agents/task_tool_agent.py`
5. **Verification Agent** → `agents/verification_agent.py`
6. **Escalation Agent** → `agents/escalation_agent.py`
7. **Supervisor Agent** → `agents/supervisor_agent.py`
8. **Deploy to AgentCore Runtime**, then the **API proxy** → `lambda-functions/careconnect-agentcore-proxy/`
9. **Frontend** → `frontend/config.js` (with S3 + CloudFront)

---

## Where you must edit — quick reference

| File | What to change | Where to find your value |
|---|---|---|
| `commands/set-environment-variables.sh` | KB ID, Gateway URL, Guardrail ID, Guardrail version, State Machine ARN | Bedrock, AgentCore, and Step Functions consoles |
| `agents/retrieval_agent.py` | `CARECONNECT_KB_ID` (via env), `REGION` if not us-east-1 | Bedrock > Knowledge Bases |
| `agents/task_tool_agent.py` | `CARECONNECT_GATEWAY_URL` (via env), `AWS_REGION` | Bedrock AgentCore > Gateways |
| `agents/verification_agent.py` | `CARECONNECT_GUARDRAIL_ID` / `_VERSION` (via env); Lambda name if renamed | Bedrock > Guardrails |
| `agents/escalation_agent.py` | `CARECONNECT_STATE_MACHINE_ARN` (via env); table name if renamed | Step Functions > State machines |
| `lambda-functions/careconnect-agentcore-proxy/lambda_function.py` | CHANGE #1 runtime ARN, #2 region, #3 allowed origin | AgentCore > Runtimes (ARN) |
| `frontend/config.js` | `API_URL` | API Gateway > your API > Stages > prod > Invoke URL + `/careconnect` |

---

## Important things to know

- **All the agent files must live in the same folder** on your EC2 dev box, because
  `supervisor_agent.py` imports from `retrieval_agent.py`, `task_tool_agent.py`,
  `escalation_agent.py`, and `verification_agent.py`. If they're split across folders, the
  imports will fail.
- **Lambda function names matter.** Other components call them by name — for example, the
  verification agent invokes `careconnect-deterministic-safety`. If you rename a Lambda,
  update every reference to it (these spots are called out in the comments).
- **All hospital data is synthetic.** The mock tools return fake data, and a staged refill is
  never actually submitted (`submitted=False`) — that human-approval boundary is intentional.
- **The proxy Lambda needs two extra console steps** besides pasting the code: attach the
  `invoke-agentcore-policy.json` inline policy to its execution role, and raise its timeout to
  5 minutes (the default 3 seconds is too short). Both are noted in the files.
- **Placeholders, not secrets.** Example IDs/ARNs/URLs here are placeholders on purpose —
  never commit real account IDs, resource IDs, or ARNs to a public repository.

---

## Quick sanity checks

Confirm the Python files are readable and syntactically valid (optional, on a machine with Python):

```bash
python -m py_compile agents/*.py lambda-functions/*/lambda_function.py
```

Confirm boto3 is installed on your EC2 dev box:

```bash
python -c "import boto3; print('Boto3 installation successful')"
```
