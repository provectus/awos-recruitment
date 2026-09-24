# AgentCore Deployment Patterns

## Contents

- [AgentCore Runtime](#agentcore-runtime) — deployment entrypoint, sessions,
  versioned endpoints
- [AgentCore Gateway](#agentcore-gateway) — turning Lambdas and APIs into MCP
  tools
- [AgentCore Policy (Cedar)](#agentcore-policy-cedar) — deterministic
  authorization, enforcement modes
- [AgentCore Memory](#agentcore-memory) — persistent context across sessions
- [AgentCore Identity](#agentcore-identity) — agent workload identity, outbound
  auth
- [CDK Deployment Patterns](#cdk-deployment-patterns) — stack layout,
  environments, agent CI/CD
- [Bedrock Foundation Models](#bedrock-foundation-models) — model IDs,
  cross-region inference
- [Bedrock Guardrails](#bedrock-guardrails) — content filters, PII, grounding,
  prompt-attack detection

Every API name below was checked against `bedrock-agentcore` 1.23 and
`aws-cdk-lib` 2.270. Both move quickly — re-check anything you pin.

## AgentCore Runtime

AgentCore Runtime provides serverless, session-isolated execution for agents.

### Key Capabilities

- **Framework agnostic**: Works with LangGraph, Strands, CrewAI, or custom agents.
- **Session isolation**: Each session runs in a dedicated microVM with isolated
  CPU, memory, and filesystem. Memory is sanitised after session completion.
- **Extended execution**: Supports both real-time interactions and long-running
  asynchronous jobs. The synchronous request timeout, the streaming duration
  and the async job ceiling are three different quotas — look up the current
  values in [Quotas for Amazon Bedrock AgentCore][quotas] before designing
  around any of them.
- **Consumption-based pricing**: Charges only for resources consumed. CPU
  billing aligns with active processing — typically no charges during I/O wait
  (e.g., waiting for LLM responses).
- **Large payloads**: Handles documents, images, and multi-modal content up to
  the invocation payload quota (see [quotas][quotas]).
- **Bidirectional streaming**: HTTP API and WebSocket connections for real-time
  interactive applications.

[quotas]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html

### Deploying a LangGraph Agent

The runtime contract is an HTTP server exposing `/invocations` and `/ping`.
`BedrockAgentCoreApp` implements it for you: `@app.entrypoint` registers the
handler and `app.run()` serves it on port 8080. The app does not wrap the
compiled graph — the handler calls the graph itself, which is what lets you
validate the payload and pick the `thread_id` first.

```python
# agent.py — Entry point for AgentCore Runtime.
# Requires: bedrock-agentcore (verified against 1.23; pin a compatible range)
from uuid import uuid4

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from langgraph.graph import StateGraph
from starlette.responses import JSONResponse

app = BedrockAgentCoreApp()

graph = StateGraph(YourState)
# ... add nodes and edges ...
compiled = graph.compile(checkpointer=your_checkpointer)


@app.entrypoint
async def invoke(payload: dict, context: RequestContext) -> dict | JSONResponse:
    """Handle one AgentCore invocation.

    The second parameter has to be named `context` — that literal name is how
    the SDK decides to pass the RequestContext. The runtime session ID lives
    there, not in the payload, and it is None when the caller omits the
    session header, so fall back rather than key a checkpoint on None.

    The payload arrives from InvokeAgentRuntime unchanged, so validate it here
    before it reaches the graph. Returning a JSONResponse gives the caller a
    400 instead of the 500 an uncaught KeyError would produce.
    """
    agent_input = payload.get("input")
    if not isinstance(agent_input, dict):
        return JSONResponse({"error": "'input' must be an object"}, status_code=400)

    thread_id = context.session_id or f"session-{uuid4()}"
    return await compiled.ainvoke(agent_input, {"configurable": {"thread_id": thread_id}})


if __name__ == "__main__":
    app.run()
```

### Session Management

```python
# Each workflow gets an isolated session.
# Sessions persist state across invocations for the lifetime of the session.

# For multi-day workflows:
# 1. Agent runs in session, hits interrupt() for HITL
# 2. Session state is checkpointed to persistent storage
# 3. Session can be terminated (cost savings)
# 4. When human completes review, new session resumes from checkpoint
```

### Versioning and Endpoints

AgentCore Runtime supports versioned deployments:

- Deploy new agent versions without disrupting active sessions.
- Route traffic between versions (canary, blue/green).
- Roll back to previous versions if issues detected.
- Each version gets a unique invocation endpoint.

---

## AgentCore Gateway

Gateway connects agents to tools by converting APIs and Lambda functions
into MCP-compatible tools.

### Key Capabilities

- **API-to-MCP conversion**: Expose REST APIs as MCP tools automatically.
- **Lambda integration**: Invoke Lambda functions as agent tools.
- **Intelligent tool discovery**: Agents can discover available tools at runtime.
- **Policy enforcement point**: All tool invocations pass through Gateway,
  enabling Cedar policy evaluation before tool access.

### Setting Up a Gateway Target

The CDK module is `aws_cdk.aws_bedrockagentcore` (one word — not
`aws_bedrock_agentcore`). Each target type has its own `add_*_target` method,
and every target needs a `tool_schema` — that schema is what the agent sees
when it discovers the tool, so the descriptions in it are load-bearing.

```python
# CDK pattern for Gateway with Lambda target (aws-cdk-lib 2.270)
from aws_cdk import aws_bedrockagentcore as agentcore

gateway = agentcore.Gateway(
    self,
    "AgentGateway",
    gateway_name="agent-gateway",
    authorizer_configuration=agentcore.CustomJwtAuthorizer(
        discovery_url=cognito_discovery_url,
        allowed_clients=[cognito_client_id],
    ),
)

gateway.add_lambda_target(
    "DataStore",
    lambda_function=data_store_lambda,
    description="Read and write records in the primary data store",
    tool_schema=agentcore.ToolSchema.from_inline([
        agentcore.ToolDefinition(
            name="get_record",
            description="Fetch one record by its primary identifier.",
            input_schema=agentcore.SchemaDefinition(
                type=agentcore.SchemaDefinitionType.OBJECT,
                properties={
                    "record_id": agentcore.SchemaDefinition(
                        type=agentcore.SchemaDefinitionType.STRING,
                        description="Primary identifier of the record.",
                    ),
                },
                required=["record_id"],
            ),
        ),
    ]),
)
```

Other target types: `add_api_gateway_target`, `add_open_api_target`,
`add_smithy_target`, `add_mcp_server_target`.

### MCP Tool Usage in LangGraph

Tools registered in Gateway are reached as MCP tools through the Gateway
endpoint, and Cedar policies are evaluated on every invocation. On the
LangChain side, tools are **bound** to the model — `bind_tools` returns a new
runnable. There is no `tools=` keyword on `invoke`; passing one silently sends
nothing.

```python
from langchain_aws import ChatBedrockConverse

def processing_node(state: dict) -> dict:
    model = ChatBedrockConverse(model_id=settings.model_id)  # from config
    result = model.bind_tools(gateway_tools).invoke(state["prompt"])
    return {"processed_results": [result]}
```

---

## AgentCore Policy (Cedar)

Policy provides deterministic, Cedar-based authorization for agent-tool
interactions, enforced at the Gateway level.

### Architecture

```
Agent ──→ AgentCore Gateway ──→ Policy Engine ──→ Tool
                                     │
                              Cedar Evaluation
                              (ALLOW / DENY)
```

The policy engine:
1. Intercepts every tool invocation request at the Gateway.
2. Evaluates Cedar policies against: principal (agent identity), action
   (tool invocation), resource (target tool), and context (runtime conditions).
3. Returns ALLOW or DENY. On DENY, the tool is never invoked.
4. Logs every decision to CloudWatch.

### Setting Up Cedar Policies

The policy engine is not attached after the fact — it is passed to the Gateway
as `policy_engine_configuration`, and that same object carries the enforcement
mode. That is the knob you flip for the shadow-mode rollout below.

```python
# CDK pattern for Policy Engine (aws-cdk-lib 2.270)
from pathlib import Path

from aws_cdk import aws_bedrockagentcore as agentcore

policy_engine = agentcore.PolicyEngine(
    self,
    "PolicyEngine",
    # Letters, digits and underscores only — a hyphen here fails at synth time.
    policy_engine_name="agent_policies",
)

gateway = agentcore.Gateway(
    self,
    "AgentGateway",
    gateway_name="agent-gateway",
    policy_engine_configuration=agentcore.GatewayPolicyEngineConfig(
        policy_engine=policy_engine,
        mode=agentcore.PolicyEngineMode.LOG_ONLY,  # → ENFORCE after shadow run
    ),
)

# Cedar policies stay in Git as .cedar files (see the stack layout below) and
# are read in at synth time, so the same text the CI step validates is the text
# that deploys. FAIL_ON_ANY_FINDINGS rejects a policy that does not validate
# against the Gateway schema.
policy_engine.add_policy(
    "AgentToolAccess",
    statement=agentcore.PolicyStatement.from_cedar(
        Path("cedar/policies/agent-access.cedar").read_text(encoding="utf-8")
    ),
    validation_mode=agentcore.PolicyValidationMode.FAIL_ON_ANY_FINDINGS,
)
```

### Natural Language Policy Authoring

AgentCore Policy supports NL-to-Cedar conversion:

```
Natural language: "Only the intake agent can invoke the document parser"
Generated Cedar:
  permit(
    principal == Agent::"intake-agent",
    action == Action::"invoke",
    resource == Tool::"document-parser"
  );
```

Generated policies are validated against the Gateway schema and checked
via automated reasoning for overly permissive or restrictive rules.

### Enforcement Modes

| Mode | Behaviour | Use Case |
|------|-----------|----------|
| `ENFORCE` | DENY blocks the tool invocation | Production |
| `LOG_ONLY` | Log decision but allow all invocations | Policy testing, shadow mode |

**Best practice**: Deploy new policies in `LOG_ONLY` mode first. Analyse
DENY decisions for 1-2 weeks. Switch to `ENFORCE` once confident.

---

## AgentCore Memory

Memory provides persistent context across agent interactions.

### Key Capabilities

- **Short-term memory**: Conversation history within a session.
- **Long-term memory**: Facts and knowledge that persist across sessions.
- **Episodic memory**: Records of past interactions for learning.

### Integration with LangGraph

The SDK client is `MemoryClient`, and it is event-shaped rather than
document-shaped: you write turns with `create_event` and read the extracted
long-term records with `retrieve_memories`, addressed by a memory ID and a
namespace. Reads are namespaced, so pick the namespace deliberately — it is
what scopes one actor's history from another's.

A memory write has to be idempotent, because a LangGraph node is not run
once: a node that interrupts re-runs from the top on resume, and a node with
a retry policy re-runs on failure. `CreateEvent` takes a `clientToken` for
exactly this, but the `MemoryClient.create_event` wrapper does not expose it,
and boto3 auto-fills the field with a fresh UUID per call — so the wrapper
writes a duplicate event every time. Call the data-plane client underneath it
with a token derived from the task instead.

```python
import json
from datetime import UTC, datetime

from bedrock_agentcore.memory import MemoryClient

memory = MemoryClient(region_name="us-west-2")

def lookup_node(state: dict) -> dict:
    # Retrieve relevant past interactions for this source
    similar_items = memory.retrieve_memories(
        memory_id=MEMORY_ID,
        namespace=f"/sources/{state['source_name']}",
        query=f"requests from {state['source_name']}",
        top_k=5,
    )

    # Use historical context to improve processing
    # ...

    # Store this interaction's outcome for future reference. memory.gmdp_client
    # is the bedrock-agentcore data-plane client; its parameters are camelCase
    # and payload is the shape create_event() builds from (text, role) tuples.
    memory.gmdp_client.create_event(
        memoryId=MEMORY_ID,
        actorId=state["source_name"],
        sessionId=state["task_id"],
        eventTimestamp=datetime.now(tz=UTC),
        payload=[{
            "conversational": {
                "content": {"text": json.dumps({
                    "task_id": state["task_id"],
                    "result_type": state["result_type"],
                    "confidence": state["confidence"],
                })},
                "role": "ASSISTANT",
            },
        }],
        # Deterministic: a replayed node writes the same event once.
        clientToken=f"{state['task_id']}-outcome",
    )

    return {"memory_hits": similar_items}
```

---

## AgentCore Identity

Identity provides authentication and authorization for agents.

### Key Capabilities

- **Agent workload identity**: Distinct identities for each agent, not shared
  credentials.
- **Corporate IdP integration**: Connects to Okta, Microsoft Entra ID, or
  Amazon Cognito.
- **Outbound authentication**: Agents can securely access third-party services
  (Slack, GitHub, external APIs) using OAuth or API keys.
- **User-level scoping**: End users authenticate to access only the agents
  they're authorised for.

---

## CDK Deployment Patterns

### Agent Stack Structure

```
infrastructure/
├── lib/
│   ├── agent-runtime-stack.ts    # AgentCore Runtime + agents
│   ├── agent-gateway-stack.ts    # Gateway + tool targets
│   ├── agent-policy-stack.ts     # Policy engine + Cedar policies
│   ├── data-stack.ts             # DynamoDB, Aurora, S3
│   └── observability-stack.ts    # CloudWatch, dashboards
├── cedar/
│   ├── schema.cedarschema        # Cedar schema (auto-generated)
│   ├── policies/
│   │   ├── agent-access.cedar    # Agent tool access policies
│   │   ├── hitl-gates.cedar      # HITL gate approval policies
│   │   └── firebreaks.cedar      # Firebreak control policies
│   └── tests/
│       └── policy-tests.cedar    # Cedar policy test cases
└── agents/
    ├── intake/
    │   ├── agent.py              # LangGraph graph definition
    │   ├── nodes/                # Individual node implementations
    │   ├── prompts/              # Prompt templates
    │   └── tests/                # Agent tests
    └── processing/
        ├── agent.py
        ├── nodes/
        ├── prompts/
        └── tests/
```

### Environment Strategy

| Environment | Purpose | Model Access | Data |
|------------|---------|-------------|------|
| `dev` | Development, experimentation | All tiers | Synthetic data |
| `staging` | Integration testing, shadow mode | All tiers | Anonymised production data |
| `prod` | Production workloads | All tiers | Real data |

### CI/CD for Agents

```yaml
# Agent deployment pipeline
stages:
  - lint-and-test:
      - python linting and type checking
      - unit tests for individual nodes
      # cedar validate takes one schema file and one policy file, and exits
      # non-zero on a validation error — run it per policy file.
      - cedar validate
          --schema cedar/schema.cedarschema
          --policies cedar/policies/agent-access.cedar
          --deny-warnings

  - integration-test:
      - deploy to dev environment
      - run agent against test cases
      - verify HITL gates trigger correctly
      - verify Cedar policies enforce correctly

  - staging-deploy:
      - deploy to staging
      - run shadow mode comparison
      - validate cost per invocation

  - production-deploy:
      - canary deployment (10% traffic)
      - monitor error rates and latency
      - full rollout if metrics healthy
      - automatic rollback on anomaly
```

---

## Bedrock Foundation Models

### Available Models via Bedrock

Families, not IDs. A Bedrock model ID carries a version and date suffix, and an
inference profile prefixes it — with a geography (`us.`, `eu.`, `apac.`) or
with `global.`. Resolve the concrete IDs available to your account and region with
`bedrock.list_foundation_models()` / `bedrock.list_inference_profiles()`, or
from the model card pages in the Bedrock user guide, and keep them in
deployment config — see *3-Tier Model Routing* in SKILL.md.

| Provider | Model | Tier | Strengths |
|----------|-------|------|-----------|
| Anthropic | Claude Haiku | Fast | Classification, routing, simple tasks |
| Anthropic | Claude Sonnet | Balanced | Extraction, summarisation, general tasks |
| Anthropic | Claude Opus | Premium | Complex reasoning, legal language, decisions |
| Amazon | Nova Micro | Fast | Cost-effective classification |
| Amazon | Nova Lite | Balanced | General processing |
| Amazon | Nova Pro | Premium | Complex multi-step tasks |

### Cross-Region Inference

Bedrock supports cross-Region inference for availability. Invoke a
system-defined inference profile instead of the bare model ID and Bedrock
routes the request to an available destination Region when the source Region
is throttled. There are two kinds, and they are not interchangeable — the
prefix decides both where a request may run and which policy it needs:

```python
# The profile ID is the model ID with a prefix: a geography (us. / eu. /
# apac.) routes inside that geography, `global.` routes across commercial
# Regions worldwide. Load the concrete value from config — do not hardcode.
model_id = settings.model_id  # e.g. "us.<vendor>.<model>-<version>:<n>"
```

**Geographic** (`us.`/`eu.`/`apac.`): destination Regions may include opt-in
Regions, so the SCP and IAM policies for every destination Region must allow
the Bedrock invoke actions — otherwise the profile fails even when some
Regions are permitted.

**Global** (`global.`): routing is worldwide and the IAM shape differs. It
needs three statements, not a destination-Region list — the source-Region
profile ARN (`…:inference-profile/global.<model>`), the source-Region
foundation-model ARN, and the Region-less
`arn:aws:bedrock:::foundation-model/<model>` under
`aws:RequestedRegion: unspecified`. Removing any one denies access. See
[Global cross-Region inference][global-cris].

[global-cris]: https://docs.aws.amazon.com/bedrock/latest/userguide/global-cross-region-inference.html

### Bedrock Guardrails

Configure guardrails for all agent I/O:

1. **Content filters**: Block harmful content (hate, violence, sexual,
   misconduct). Check the guardrails docs for the languages your tier covers
   before relying on a non-English filter.
2. **Denied topics**: Define topics agents should not discuss.
3. **Word filters**: Block specific terms.
4. **PII detection and redaction**: Automatically detect and mask PII
   in inputs and outputs.
5. **Contextual grounding**: Validate outputs against source documents
   to detect hallucinations.
6. **Prompt attack detection**: Detect and block prompt injection attempts,
   including indirect injection via documents.

```python
# Apply guardrails to model invocations
response = bedrock.invoke_model(
    modelId=settings.model_id,  # from config — see Available Models above
    guardrailIdentifier=settings.guardrail_id,
    guardrailVersion=settings.guardrail_version,
    body=request_body,
)
```

### Automated Reasoning Checks

Bedrock Guardrails includes automated reasoning: you encode domain rules as a
formal policy and it checks model responses against them, returning a verdict
with the rules applied rather than a similarity score. Use for:
- Verifying extracted values against known constraints
- Checking that decisions are logically consistent
- Ensuring numerical calculations are correct

The check is only as good as the policy you encode, so treat a `VALID` verdict
as evidence, not as proof — keep the HITL gate for anything safety-critical.
