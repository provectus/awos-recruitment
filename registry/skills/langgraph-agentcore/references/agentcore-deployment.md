# AgentCore Deployment Patterns

## AgentCore Runtime

AgentCore Runtime provides serverless, session-isolated execution for agents.

### Key Capabilities

- **Framework agnostic**: Works with LangGraph, Strands, CrewAI, or custom agents.
- **Session isolation**: Each session runs in a dedicated microVM with isolated
  CPU, memory, and filesystem. Memory is sanitised after session completion.
- **Extended execution**: Supports real-time interactions and long-running
  workloads up to 8 hours.
- **Consumption-based pricing**: Charges only for resources consumed. CPU
  billing aligns with active processing — typically no charges during I/O wait
  (e.g., waiting for LLM responses).
- **100MB payload support**: Handles large documents, images, and multi-modal content.
- **Bidirectional streaming**: HTTP API and WebSocket connections for real-time
  interactive applications.

### Deploying a LangGraph Agent

```python
# agent.py — Entry point for AgentCore Runtime
from langgraph.graph import StateGraph
from bedrock_agentcore.runtime import AgentCoreApp

# Define your graph
graph = StateGraph(YourState)
# ... add nodes and edges ...
app = graph.compile(checkpointer=your_checkpointer)

# Wrap for AgentCore Runtime
agentcore_app = AgentCoreApp(app)

if __name__ == "__main__":
    agentcore_app.serve()
```

### Session Management

```python
# Each case gets an isolated session
# Sessions persist state across multiple invocations within the 8-hour window

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

```python
# CDK pattern for Gateway with Lambda target
from aws_cdk import (
    aws_bedrock_agentcore as agentcore,
    aws_lambda as lambda_,
)

# Define a Lambda function as a Gateway target
gateway = agentcore.Gateway(self, "AgentGateway",
    authorizer=cognito_authorizer,
)

gateway.add_target("quote-system",
    target_type="lambda",
    function=quote_system_lambda,
    description="Create and manage quotes in the quote management system",
)

gateway.add_target("sanctions-check",
    target_type="lambda",
    function=sanctions_lambda,
    description="Screen entities against sanctions watchlists",
)
```

### MCP Tool Usage in LangGraph

```python
from langchain_aws import ChatBedrockConverse

# Tools registered in Gateway are available as MCP tools
# The agent invokes them through the Gateway endpoint
# Cedar policies are evaluated on every invocation

def extraction_node(state):
    model = ChatBedrockConverse(
        model_id="anthropic.claude-sonnet",
        # Tools bound via Gateway MCP endpoint
    )
    result = model.invoke(state["prompt"], tools=gateway_tools)
    return {"extracted_fields": result}
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

```python
# CDK pattern for Policy Engine
policy_engine = agentcore.PolicyEngine(self, "PolicyEngine")

# Attach to Gateway
gateway.attach_policy_engine(policy_engine)

# Cedar policies are deployed via CI/CD from Git
# Policies are validated against auto-generated schema at deployment time
```

### Natural Language Policy Authoring

AgentCore Policy supports NL-to-Cedar conversion:

```
Natural language: "Only the triage agent can classify emails"
Generated Cedar:
  permit(
    principal == Agent::"triage-agent",
    action == Action::"invoke",
    resource == Tool::"email-classifier"
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

```python
from bedrock_agentcore.memory import AgentCoreMemory

memory = AgentCoreMemory(agent_id="triage-agent")

def triage_node(state):
    # Retrieve relevant past cases for this broker
    similar_cases = memory.search(
        query=f"submissions from {state['broker_name']}",
        limit=5
    )

    # Use historical context to improve classification
    # ...

    # Store this case's outcome for future reference
    memory.store({
        "case_id": state["case_id"],
        "broker": state["broker_name"],
        "classification": state["classification"],
        "confidence": state["confidence"],
    })
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
    ├── triage/
    │   ├── agent.py              # LangGraph graph definition
    │   ├── nodes/                # Individual node implementations
    │   ├── prompts/              # Prompt templates
    │   └── tests/                # Agent tests
    └── extraction/
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
      - cedar policy validation (just validate-registry)

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

| Provider | Model | Tier | Strengths |
|----------|-------|------|-----------|
| Anthropic | Claude Haiku | Fast | Classification, routing, simple tasks |
| Anthropic | Claude Sonnet | Balanced | Extraction, summarisation, general tasks |
| Anthropic | Claude Opus | Premium | Complex reasoning, legal language, decisions |
| Amazon | Nova Micro | Fast | Cost-effective classification |
| Amazon | Nova Lite | Balanced | General processing |
| Amazon | Nova Pro | Premium | Complex multi-step tasks |

### Cross-Region Inference

Bedrock supports cross-region inference for availability:

```python
# Configure cross-region inference profile
model_id = "anthropic.claude-sonnet"
# Bedrock automatically routes to available region if primary is throttled
```

### Bedrock Guardrails

Configure guardrails for all agent I/O:

1. **Content filters**: Block harmful content (hate, violence, sexual,
   misconduct). Standard tier supports 60+ languages.
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
    modelId="anthropic.claude-sonnet",
    guardrailIdentifier="your-guardrail-id",
    guardrailVersion="1",
    body=request_body,
)
```

### Automated Reasoning Checks

Bedrock Guardrails includes automated reasoning that validates model
responses against logical rules with up to 99% accuracy. Use for:
- Verifying extracted values against known constraints
- Checking that compliance decisions are logically consistent
- Ensuring financial calculations are correct
