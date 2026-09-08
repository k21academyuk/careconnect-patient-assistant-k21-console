# CareConnect — Setup Notes (EC2 dev box)

These are the packages and one-time setup steps referenced in the lab, collected
here so you can copy them quickly. Follow the lab guide for the full context.

## 1. Python packages

On your EC2 dev box, upgrade pip and install the core packages used by the agents:

```bash
python -m pip install --upgrade pip
pip install strands-agents boto3
```

For the Task/Tool Agent (which talks to the AgentCore Gateway over MCP), also install:

```bash
pip install mcp
pip install mcp-proxy-for-aws
```

The Verification Agent additionally uses `pydantic` (usually already present; if not):

```bash
pip install pydantic
```

Quick check that a package is installed:

```bash
pip show strands-agents
```

## 2. Confirm boto3 works

```bash
python -c "import boto3; print('Boto3 installation successful')"
```

## 3. Set your environment variables

Before running `supervisor_agent.py`, export the five values the agents need.
Edit and run `../commands/set-environment-variables.sh` (fill in YOUR values first).

## 4. Deploy troubleshooting (AgentCore Runtime)

If the deployed agent errors on the model, open the generated load file and set the
model line, then redeploy:

```bash
nano app/careconnectsupervisor/model/load.py
# change the model line to:  return BedrockModel(model_id="amazon.nova-lite-v1:0")
# save (Ctrl+O, Enter, Ctrl+X)

# the Node heap flag does not survive sessions, so set it again before redeploying:
export NODE_OPTIONS="--max-old-space-size=3072"
agentcore deploy
agentcore invoke
```

> A change only takes effect after you redeploy — the running agent is the
> previously-deployed version until you deploy again.
