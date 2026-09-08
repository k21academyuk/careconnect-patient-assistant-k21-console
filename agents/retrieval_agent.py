"""
CareConnect — Retrieval Agent
=============================
Riverside Health patient-support assistant (console/CLI build).

WHAT THIS AGENT DOES
  It searches ONLY the approved Riverside Health Knowledge Base and returns the
  matching passages with their source. It never uses general knowledge and never
  gives medical advice. This is the "answer only from approved documents" agent.

HOW TO USE
  1. Set your Knowledge Base ID as an environment variable before running:
         export CARECONNECT_KB_ID="YOUR_KNOWLEDGE_BASE_ID"     # <-- UPDATE THIS
  2. Run it:
         python retrieval_agent.py
  3. Type a patient question; type 'exit' to stop.

WHERE YOU MIGHT NEED TO CHANGE THINGS
  - REGION: change if you did not build in us-east-1.
  - CARECONNECT_KB_ID: must be YOUR Knowledge Base ID (see the KB step in the guide).
"""

import os
import boto3
from strands import Agent, tool

# ---------------------------------------------------------------------------
# AWS configuration
# ---------------------------------------------------------------------------
# UPDATE THIS if you built in a different AWS region.
REGION = "us-east-1"

# Read the Knowledge Base ID from an environment variable.
# UPDATE THIS by exporting CARECONNECT_KB_ID before you run the script.
KB_ID = os.environ.get("CARECONNECT_KB_ID")
if not KB_ID:
    raise ValueError(
        "CARECONNECT_KB_ID is not set. "
        "Please set your Knowledge Base ID before running the agent."
    )

# Create the Amazon Bedrock Knowledge Base runtime client.
kb_client = boto3.client("bedrock-agent-runtime", region_name=REGION)


# ---------------------------------------------------------------------------
# The one tool this agent is allowed to use: search the approved documents.
# The @tool decorator makes this Python function available to the Strands agent.
# ---------------------------------------------------------------------------
@tool
def search_docs(query: str) -> str:
    """
    Search the approved Riverside Health documents.

    Args:
        query: The question to search for in the CareConnect Knowledge Base.
    """
    # Call the Bedrock Knowledge Base "retrieve" operation. It takes the KB ID
    # and the query text, and returns the most relevant approved passages.
    response = kb_client.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 5}
        },
    )

    results = response.get("retrievalResults", [])

    # If the approved documents contain nothing relevant, say so clearly.
    if not results:
        return (
            "No approved Riverside Health information "
            "was found for this question."
        )

    # Otherwise, format each passage with its content, source, and score.
    passages = []
    for number, result in enumerate(results, start=1):
        content = result.get("content", {}).get("text", "")
        source = (
            result.get("location", {})
            .get("s3Location", {})
            .get("uri", "Unknown source")
        )
        score = result.get("score", "Not available")
        passages.append(
            f"""
Passage {number}
{content}
Source:
{source}
Relevance score:
{score}
"""
        )

    return "\n".join(passages)


# ---------------------------------------------------------------------------
# The agent itself: a model given the search_docs tool and strict safety rules.
# ---------------------------------------------------------------------------
retrieval_agent = Agent(
    system_prompt="""
You are the CareConnect Retrieval Agent for Riverside Health.
Your only responsibility is to retrieve information from the
approved Riverside Health Knowledge Base.

Follow these rules:

1. Always use the search_docs tool.
2. Use only information returned by search_docs.
3. Never add information from general knowledge.
4. Never invent missing information.
5. Never diagnose a medical condition.
6. Never recommend medical treatment.
7. Never recommend medication or dosage changes.
8. Preserve the source information returned by the tool.
9. Return the relevant approved information with its source.
10. If the approved documents do not contain the required
    information, clearly state that no approved Riverside Health
    information was found.

Do not fill information gaps using outside knowledge.
""",
    tools=[search_docs],
)


# ---------------------------------------------------------------------------
# Simple interactive loop so you can test the agent from the terminal.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\nCareConnect Retrieval Agent")
    print("Type 'exit' to stop.\n")

    while True:
        question = input("Patient question: ").strip()

        if question.lower() in ["exit", "quit"]:
            print("Retrieval Agent stopped.")
            break

        if not question:
            continue

        response = retrieval_agent(question)
        print("\nResponse:\n")
        print(response)
        print()
