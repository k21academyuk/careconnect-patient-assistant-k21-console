# CareConnect — Patient-Support Assistant (Console / CLI Build)

**CareConnect** is a secure, multi-agent patient-support assistant for the fictional
**Riverside Health** hospital network, built on **Amazon Bedrock AgentCore**. It answers
routine patient questions (visiting hours, appointment prep, prescription refills,
insurance, billing) **only from approved hospital documents, with citations** — while
anything clinical (dosages, diagnoses, urgent symptoms) is **never answered automatically**
and is **escalated to a licensed clinician**. High-impact actions such as a prescription
refill are **staged for human approval**, never auto-submitted.

This repository is the **Console / CLI build**: the scripts, Lambda functions, agent code,
and templates you create by following the lab guide step by step in the AWS Console and on
an Ubuntu EC2 dev box.

> Companion repo (the SDK / Notebook build):
> [`careconnect-patient-assistant-k21`](https://github.com/k21academyuk/careconnect-patient-assistant-k21).

> **Scope & status.** Educational reference using **synthetic data only**. Not
> production-ready as written — see [Limitations](#limitations).

---

## Architecture

The complete CareConnect system — patient browser → API edge → the seven-agent AgentCore
runtime → knowledge/AI services → tools, escalation, and cross-cutting safety/observability.

![Full architecture](images/full-architecture.png)

**Request flow** (blue = request in, red = clinical question escalated to a human,
green = verified, guardrail-approved answer returning to the patient):

![Animated flow](images/architecture-flow-animated.gif)

---

## The seven agents

| Agent | Responsibility |
|---|---|
| **Supervisor / Orchestrator** | Plans the request, routes sub-tasks, enforces step/time budgets, verifies before replying |
| **Safety** | Deterministic gate for clinical/urgent/manipulation intent and PII |
| **Retrieval** | Searches the approved documents and returns passages **with citations** |
| **Document-Processing** | Structures retrieved evidence (e.g. into checklists) without adding content |
| **Task/Tool** | Calls synthetic hospital tools via AgentCore Gateway; **stages** actions only |
| **Verification** | Independently checks grounding, citations, safety, and Guardrail before a reply ships |
| **Escalation** | Creates a durable ticket and starts the human-approval workflow |

**Autonomy level:** deliberately kept at **Level 1–2 (assistant / human-approved)**. The
system informs and prepares; it does not independently execute clinical or high-impact
actions.

---

## Repository layout

```
README.md                         ← you are here
images/                           ← full architecture, animated flow, and step 5–19 diagrams

agents/                           ← the six specialist agents (run on your EC2 dev box)
  retrieval_agent.py
  document_processing_agent.py
  task_tool_agent.py
  verification_agent.py
  escalation_agent.py
  supervisor_agent.py             ← run this one last (imports the others)

lambda-functions/                 ← three AWS Lambda functions (create in the Lambda console)
  careconnect-deterministic-safety/lambda_function.py
  careconnect-mock-hospital-tools/lambda_function.py
  careconnect-agentcore-proxy/
    lambda_function.py
    invoke-agentcore-policy.json

frontend/
  config.js                       ← the one file you edit for the S3 + CloudFront frontend

commands/
  set-environment-variables.sh    ← exports the five values the agents need (edit with YOUR values)
  setup-notes.md                  ← pip installs + deploy troubleshooting

careconnect-approved-docs/        ← the approved Riverside Health documents (the source of truth)
careconnect-frontend-prod/        ← the built static frontend hosted on S3 + CloudFront
```

---

## How to use this repo

1. Follow the **lab guide** as your main instructions.
2. When the guide says *"create `<file>.py` and paste this code"*, open the matching file in
   `agents/` or `lambda-functions/`, read its header + comments, and copy it into place.
3. **Fill in your own AWS values** wherever a comment says so. Editable spots are tagged
   **`UPDATE THIS`**, **`>>> CHANGE #`**, or **`>>> LEARNERS`**. Every example ID/ARN/URL is
   a placeholder — replace it with your own from the AWS Console.

**Build order** (matches the diagrams below):

| Step | Focus | Files / services |
|---|---|---|
| 5 | Store approved documents | Amazon S3 (`careconnect-approved-docs/`) |
| 6 | Knowledge Base + retrieval | Bedrock Knowledge Base, S3 Vectors, Titan Embeddings |
| 7 | Patient Safety Guardrail | Bedrock Guardrails |
| 8 | Deterministic safety | `lambda-functions/careconnect-deterministic-safety/` |
| 9 | Retrieval Agent | `agents/retrieval_agent.py` |
| 10 | Document-Processing Agent | `agents/document_processing_agent.py` |
| 11 | Task/Tool Agent + Gateway | `lambda-functions/careconnect-mock-hospital-tools/`, `agents/task_tool_agent.py` |
| 12 | Verification Agent | `agents/verification_agent.py` |
| 13 | Escalation Agent | `agents/escalation_agent.py` (DynamoDB + Step Functions) |
| 14 | Supervisor Agent | `agents/supervisor_agent.py` |
| 15 | Deploy to AgentCore Runtime | AgentCore CLI on EC2 |
| 16 | API Gateway endpoint | `lambda-functions/careconnect-agentcore-proxy/` |
| 17 | Frontend (S3 + CloudFront) | `frontend/config.js`, `careconnect-frontend-prod/` |
| 18 | Evaluate, monitor & gate | CloudWatch + AgentCore Evaluations |

---

## Step-by-step diagrams

Each diagram shows the full architecture in faded context with **that step's components
highlighted**, plus a zoomed-in detail panel.

### Step 5 — Store Approved Documents in Amazon S3
![Step 5](images/step-05-s3-documents.png)

### Step 6 — Create the Knowledge Base with S3 Vectors
![Step 6](images/step-06-knowledge-base.png)

### Step 7 — Create the Patient Safety Guardrail
![Step 7](images/step-07-guardrail.png)

### Step 8 — Build & Test the Deterministic Safety Rules
![Step 8](images/step-08-deterministic-safety.png)

### Step 9 — Build the Retrieval Agent (Strands)
![Step 9](images/step-09-retrieval-agent.png)

### Step 10 — Build the Document-Processing Agent
![Step 10](images/step-10-document-processing.png)

### Step 11 — Build the Task/Tool Agent with AgentCore Gateway
![Step 11](images/step-11-task-tool-gateway.png)

### Step 12 — Build the Response Verification Agent
![Step 12](images/step-12-verification-agent.png)

### Step 13 — Build the Escalation Agent (DynamoDB + Step Functions)
![Step 13](images/step-13-escalation.png)

### Step 14 — Build the Supervisor Agent (Orchestration & Budgets)
![Step 14](images/step-14-supervisor.png)

### Step 15 — Deploy to Amazon Bedrock AgentCore Runtime
![Step 15](images/step-15-deploy-runtime.png)

### Step 16 — Create the API Gateway Endpoint
![Step 16](images/step-16-api-gateway.png)

### Step 17 — Build & Host the Frontend (S3 + CloudFront)
![Step 17](images/step-17-frontend-cloudfront.png)

### Step 18 — Evaluate, Monitor & Gate for Release
![Step 18](images/step-18-evaluate-monitor-gate.png)

### Step 19 — CareConnect, SDK / Notebook Edition
![Step 19](images/step-19-sdk-notebook-edition.png)

---

## Safety model

CareConnect uses **defense in depth** rather than trusting any single control:

1. **Deterministic rules** — predictable regex detection of clinical/dosage intent, urgent
   symptoms, prompt-injection phrases, and PII.
2. **Amazon Bedrock Guardrails** — denied topics (Diagnosis, Dosage, Treatment, Triage) plus
   PII masking and a custom MRN regex.
3. **Retrieved-content sanitising** — instruction-like lines stripped from documents to blunt
   indirect prompt injection.
4. **Independent verification** — a separate agent confirms the draft is grounded, correctly
   cited, and free of unsupported clinical/dosing claims.
5. **Human-in-the-loop** — clinical questions escalate; high-impact actions stage for
   approval and are never auto-submitted.
6. **Budgets** — the Supervisor caps steps and time to prevent loops / runaway cost.

---

## Important notes

- **All agent files must live in the same folder** (`agents/`) on your EC2 dev box —
  `supervisor_agent.py` imports the other agents.
- **Lambda function names matter** — components call them by name (e.g. the verifier invokes
  `careconnect-deterministic-safety`). Rename one and you must update its references.
- **All hospital data is synthetic.** A staged refill is never actually submitted
  (`submitted=False`) — that human-approval boundary is intentional.
- **The proxy Lambda needs two extra console steps**: attach `invoke-agentcore-policy.json`
  to its execution role, and raise its timeout to 5 minutes.
- **Placeholders, not secrets.** Never commit real account IDs, resource IDs, or ARNs.

---

## Limitations

This is a **learning reference**, not a production system. Before handling real patients it
would need: Infrastructure-as-Code (CDK/Terraform), real authentication (Cognito/JWT or IAM),
least-privilege IAM (no `"Resource": "*"`), customer-managed KMS encryption, AWS WAF, a
masked/audited logging pipeline, CI/CD with the golden-scenario evaluation as a release gate,
real (authenticated) hospital-system integrations instead of the synthetic tools, and the
full compliance work (signed AWS BAA, HIPAA-eligibility review, a defined clinician review
process, and an independent security review). **No code can make the system HIPAA-compliant
by itself.**

---

## Credits

CareConnect scenario, safety model, and agent design based on the K21Academy
*Production Ready — CareConnect Patient Assistant* build guide. Deployment patterns adapted
from AWS's `amazon-bedrock-agentcore` samples. All data is synthetic.
