"""
CareConnect — Supervisor Agent (Orchestrator)
=============================================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS AGENT DOES
  This is the "brain" that coordinates the four specialist agents you built:
    retrieval_agent.py     -> approved Knowledge Base lookups
    task_tool_agent.py     -> operational actions via AgentCore Gateway (MCP)
    escalation_agent.py    -> human-review tickets + Step Functions
    verification_agent.py  -> grounding + deterministic safety + guardrail
  For each patient request it: runs a safety check, plans which agents are
  needed, runs them, combines only the SAFE outputs into a draft, and verifies
  that draft before returning it. Clinical questions are escalated, never answered.
  It also enforces step/time budgets so it can't run away.

>>> IMPORTANT FOR LEARNERS <<<
  All FOUR agent files (retrieval_agent.py, task_tool_agent.py,
  escalation_agent.py, verification_agent.py) MUST be in the SAME folder as this
  file, because this script imports from them.

HOW TO USE
  1. Export all the environment variables first (KB ID, Gateway URL, Guardrail
     ID/version, State Machine ARN) — see the "environment variables" block in
     the guide. Each is marked ">>> LEARNERS" below where it's used.
  2. Run it:
         python supervisor_agent.py
  3. Type a patient request; type 'exit' to stop.
"""

import os
import re
import time

# These imports require the specialist files to be in the same directory.
from escalation_agent import escalate
from verification_agent import verify


# ---------------------------------------------------------------------------
# Budgets — hard limits so the workflow can't loop or run too long/expensive.
# ---------------------------------------------------------------------------
class Budgets:
    max_steps = 8
    max_cost = 0.05
    max_seconds = 30


# Tracks how many steps we've taken and stops us if we blow the budget.
class RunState:
    def __init__(self):
        self.steps = 0
        self.start = time.time()

    def spend_step(self, label):
        self.steps += 1
        if self.steps > Budgets.max_steps:
            raise RuntimeError(
                f"Budget exceeded: more than {Budgets.max_steps} steps."
            )
        if time.time() - self.start > Budgets.max_seconds:
            raise RuntimeError(
                f"Budget exceeded: over {Budgets.max_seconds} seconds."
            )
        print(f"[step {self.steps}] {label}")


# ---------------------------------------------------------------------------
# 1. Safety gate: detect clinical / dosage intent the AI must NEVER answer.
#    >>> LEARNERS: REPLACE / EXTEND to match your guardrail's deny topics.
# ---------------------------------------------------------------------------
CLINICAL_PATTERNS = [
    r"should i (stop|start|change|take|increase|decrease|double)",
    r"stop (taking|my) ",
    r"change (my )?(dose|medication|medicine)",
    r"increase .*(dose|medication)",
    r"decrease .*(dose|medication)",
    r"is it safe to (take|stop|skip)",
]


def check_safety(request, state):
    state.spend_step("Safety Agent (input check)")
    lowered = request.lower()
    hits = [p for p in CLINICAL_PATTERNS if re.search(p, lowered)]
    return {"clinical_detected": bool(hits), "matched": hits}


# ---------------------------------------------------------------------------
# 2. Planning: split a multi-intent request into tasks, each tagged with an agent.
#    >>> LEARNERS: REPLACE these keyword lists for your own request types.
# ---------------------------------------------------------------------------
INFORMATIONAL_KEYWORDS = [
    "prepare", "preparation", "how do i", "colonoscopy", "visiting hours",
    "policy", "refill process", "timing", "refill", "park", "parking",
    "appointment", "book", "hours",
]
OPERATIONAL_KEYWORDS = ["reschedule", "cancel booking"]


def create_plan(request, safety, state):
    state.spend_step("Create execution plan")
    lowered = request.lower()
    plan = []
    if any(k in lowered for k in INFORMATIONAL_KEYWORDS):
        plan.append({"task": "Retrieve approved information", "agent": "retrieval"})
    if any(k in lowered for k in OPERATIONAL_KEYWORDS):
        plan.append({"task": "Check operational status", "agent": "task"})
    if safety["clinical_detected"]:
        plan.append({"task": "Medication / clinical decision", "agent": "escalation"})
    if not plan:
        plan.append({"task": "General approved-information lookup", "agent": "retrieval"})
    for p in plan:
        print(f"     - {p['task']} -> {p['agent']} agent")
    return plan


# ---------------------------------------------------------------------------
# 3. Route + execute each task on its real specialist agent.
# ---------------------------------------------------------------------------
def run_retrieval(request, state):
    state.spend_step("Retrieval Agent")
    # >>> LEARNERS: export CARECONNECT_KB_ID="<your-kb-id>"
    if not os.environ.get("CARECONNECT_KB_ID"):
        return {"answer": "[retrieval skipped: CARECONNECT_KB_ID not set]", "passages": ""}
    from retrieval_agent import search_docs
    all_passages = search_docs(request)
    # Keep only the single top-ranked passage. Semantic search returns several
    # loosely-related chunks; extra ones (e.g. triage/dosage text) can trip the
    # guardrail even for a simple question. Verifying against the best-matching
    # passage keeps the draft grounded AND clear of unrelated safety triggers.
    top = all_passages.split("Passage 2")[0].strip()
    return {"answer": top, "passages": top}


def run_task_tool(request, state):
    state.spend_step("Task/Tool Agent (AgentCore Gateway / MCP)")
    # >>> LEARNERS: export CARECONNECT_GATEWAY_URL="<your-gateway-mcp-url>"
    if not os.environ.get("CARECONNECT_GATEWAY_URL"):
        return "[task/tool skipped: CARECONNECT_GATEWAY_URL not set]"
    try:
        from task_tool_agent import mcp_client, SYSTEM_PROMPT
        from strands import Agent
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools)
            return str(agent(request))
    except Exception as exc:
        return f"[task/tool agent error - gateway call failed: {exc}]"


def run_escalation(request, state):
    state.spend_step("Escalation Agent")
    # >>> LEARNERS: export CARECONNECT_STATE_MACHINE_ARN="<your-arn>"
    # Real side effects: writes a DynamoDB ticket + starts Step Functions.
    return escalate(
        reason="Medication/clinical decision requires clinician review.",
        category="clinical_question",
        request_details={"patient_request": request},
    )


def execute_required_agents(request, plan, state):
    results = {}
    for item in plan:
        agent = item["agent"]
        if agent == "retrieval" and "retrieval" not in results:
            results["retrieval"] = run_retrieval(request, state)
        elif agent == "task" and "task" not in results:
            results["task"] = run_task_tool(request, state)
        elif agent == "escalation" and "escalation" not in results:
            results["escalation"] = run_escalation(request, state)
    return results


# ---------------------------------------------------------------------------
# 4. Combine only the SAFE outputs into a patient-facing draft.
#    Returns BOTH the draft and the evidence (raw passages) it was built from.
# ---------------------------------------------------------------------------
def combine_safe_results(results, safety, state):
    state.spend_step("Combine safe results")
    parts = []
    evidence = ""
    if "retrieval" in results:
        evidence = results["retrieval"].get("passages", "")
        parts.append("Approved Riverside Health information:\n" + evidence)
    if "task" in results:
        parts.append("Operational status:\n" + results["task"])
    if "escalation" in results:
        esc = results["escalation"]
        # Never surface a clinical answer - only the escalation notice.
        parts.append(
            "Medication question:\n"
            "Your medication question requires review by a licensed "
            f"clinician. (Ticket: {esc.get('ticket_id', 'n/a')}, "
            f"status: {esc.get('status', 'pending_review')})"
        )
    elif safety["clinical_detected"]:
        parts.append(
            "Medication question:\n"
            "Your medication question requires review by a licensed clinician."
        )
    return "\n\n".join(parts), evidence


# ---------------------------------------------------------------------------
# 5. Verify the draft against the SAME passages retrieval returned.
#    Syncs retrieved_passages.txt so the verifier checks live evidence.
# ---------------------------------------------------------------------------
def verify_response(draft, evidence, state):
    state.spend_step("Verification Agent")
    if not evidence.strip():
        if os.path.exists("retrieved_passages.txt"):
            with open("retrieved_passages.txt", "r", encoding="utf-8") as f:
                evidence = f.read()
        else:
            return {"verification_status": "SKIPPED", "reason": "no evidence available"}
    with open("retrieved_passages.txt", "w", encoding="utf-8") as f:
        f.write(evidence)
    try:
        return verify(draft, evidence)
    except Exception as exc:
        return {"verification_status": "ERROR", "reason": str(exc)}


# ---------------------------------------------------------------------------
# Orchestrator — ties the five stages together.
# ---------------------------------------------------------------------------
def supervisor_flow(request):
    state = RunState()
    safety = check_safety(request, state)
    plan = create_plan(request, safety, state)
    results = execute_required_agents(request, plan, state)
    draft, evidence = combine_safe_results(results, safety, state)
    verification = verify_response(draft, evidence, state)
    return {
        "request": request,
        "safety": safety,
        "plan": plan,
        "draft_response": draft,
        "verification": verification,
    }


# ---------------------------------------------------------------------------
# Interactive terminal loop.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\nCareConnect Supervisor Agent")
    print("Type 'exit' to stop.\n")

    while True:
        request = input("Patient request: ").strip()

        if request.lower() in ["exit", "quit"]:
            print("Supervisor Agent stopped.")
            break

        if not request:
            continue

        try:
            outcome = supervisor_flow(request)
        except RuntimeError as exc:
            print(f"\nStopped by budget: {exc}\n")
            continue

        print("\n--- Draft response ---\n")
        print(outcome["draft_response"])
        print("\n--- Verification ---")
        print(outcome["verification"].get("verification_status", "n/a"))
        print()
