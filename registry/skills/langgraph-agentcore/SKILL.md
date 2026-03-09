---
name: langgraph-agentcore
description: >-
  Production patterns for building LangGraph StateGraph workflows deployed on
  AWS Bedrock AgentCore. Covers graph design, interrupt-based human-in-the-loop,
  multi-day checkpointing, 3-tier model routing with fallback chains, confidence
  calibration implementation, Cedar policy enforcement for agent authorization,
  cost-aware pipeline design, AgentCore Runtime deployment, Bedrock Foundation
  Models and Guardrails, MCP tool integration via AgentCore Gateway, and
  observability with LangSmith and CloudWatch. Use when building agentic AI
  workflows with LangGraph, deploying agents on AWS Bedrock AgentCore, or
  implementing interrupt-based HITL workflows.
---

# LangGraph + AgentCore Production Patterns

This skill covers how to build production-grade agentic workflows using
LangGraph and deploy them on AWS Bedrock AgentCore.

## StateGraph Design Principles

### Graph Structure

Every workflow is a `StateGraph` with typed state, nodes, and edges:

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated

class PipelineState(TypedDict):
    task_id: str
    inputs: list[dict]
    processed_results: Annotated[list[dict], add]  # reducer for accumulation
    confidence_scores: dict[str, float]
    review_decisions: list[dict]
    status: str
    current_stage: str

graph = StateGraph(PipelineState)
graph.add_node("parse", parse_node)
graph.add_node("transform", transform_node)
graph.add_node("validate", validate_node)
graph.add_node("output", output_node)

graph.add_edge(START, "parse")
graph.add_edge("parse", "transform")
graph.add_edge("transform", "validate")
graph.add_edge("validate", "output")
graph.add_edge("output", END)
```

### Node Design Rules

1. **Single responsibility** — each node does one thing. "Parse headers"
   and "parse body" are separate nodes, not one mega-node.
2. **Explicit inputs and outputs** — nodes read specific state keys and write
   specific state keys. Document this in the node docstring.
3. **Idempotent** — nodes must produce the same output given the same state.
   This enables replay via `get_state_history()`.
4. **Provenance on every output** — every AI-produced value should include
   references linking to source data (document ID, page, coordinates). This
   enables replay, debugging, and auditability.

### Conditional Routing

Use `add_conditional_edges` for decision points:

```python
def route_by_confidence(state: PipelineState) -> str:
    confidence = state["confidence_scores"].get("overall", 0)
    if confidence >= 0.85:
        return "auto_proceed"
    elif confidence >= 0.60:
        return "human_review"
    else:
        return "escalated_review"

graph.add_conditional_edges(
    "assess_confidence",
    route_by_confidence,
    {
        "auto_proceed": "next_stage",
        "human_review": "hitl_standard",
        "escalated_review": "hitl_senior",
    }
)
```

### Parallel Execution (Fan-Out / Fan-In)

Use `Send` for parallel node execution:

```python
from langgraph.constants import Send

def fan_out_enrichment(state: PipelineState) -> list[Send]:
    """Run data sources in parallel."""
    return [
        Send("external_api_lookup", state),
        Send("database_query", state),
        Send("cache_check", state),
    ]

graph.add_conditional_edges("processing_done", fan_out_enrichment)
# All parallel nodes write to state; use a reducer to merge results
```

## Human-in-the-Loop with interrupt()

`interrupt()` is the core HITL mechanism. It pauses the graph, persists
state via checkpoint, and resumes when a human provides input.

### Basic Pattern

```python
from langgraph.types import interrupt, Command

def review_node(state: PipelineState) -> dict:
    """Pause for human review of low-confidence results."""
    results = state["processed_results"]
    low_confidence = [r for r in results if r["confidence"] < 0.85]

    if low_confidence:
        # Pause execution — state is checkpointed
        human_input = interrupt({
            "type": "field_review",
            "fields_to_review": low_confidence,
            "references": [r["source_ref"] for r in low_confidence],
            "instructions": "Review flagged fields against source data."
        })

        # Execution resumes here with human_input
        return {"review_decisions": [human_input]}

    return {}  # No review needed, continue
```

### Resuming After HITL

```python
# External system (e.g., Step Functions callback) resumes the graph:
from langgraph.types import Command

result = graph.invoke(
    Command(resume={
        "reviewed_fields": [...],
        "reviewer_id": "user-123",
        "action": "confirmed",
        "rationale_code": "ai_correct"
    }),
    config={"configurable": {"thread_id": task_id}}
)
```

### Three HITL Patterns

| Pattern | Implementation | Use Case |
|---------|---------------|----------|
| **Async** | `interrupt()` with timeout. External system sends `Command(resume=...)` when human completes task. | Data quality reviews, ambiguity resolution |
| **Blocking** | `interrupt()` with no timeout. Graph does not proceed on any branch until cleared. | Approval workflows, safety-critical gates |
| **Deferred** | Node proceeds with provisional value. Separate batch review process validates later. | Low-priority validations, batch auditing |

## Checkpointing for Long-Running Workflows

AgentCore supports sessions up to 8 hours. For workflows spanning days
(e.g., waiting for external input), use checkpoint persistence.

### Setup

```python
from langgraph.checkpoint.postgres import PostgresSaver

# Use PostgreSQL for durable checkpoints
checkpointer = PostgresSaver.from_conn_string(db_url)

app = graph.compile(checkpointer=checkpointer)

# Each workflow gets its own thread
config = {"configurable": {"thread_id": f"workflow-{task_id}"}}
result = app.invoke(initial_state, config)
```

### State Recovery

```python
# Resume a previously interrupted workflow
state = app.get_state(config)
if state.next:  # There are pending nodes
    result = app.invoke(
        Command(resume=human_decision),
        config
    )
```

### Replay and Debugging

```python
# Walk through all state transitions for a case
for state_snapshot in app.get_state_history(config):
    print(f"Step: {state_snapshot.next}")
    print(f"State: {state_snapshot.values}")
    print(f"Created: {state_snapshot.created_at}")
```

## 3-Tier Model Routing

Use different model tiers based on task complexity to optimise cost:

| Tier | Models | Use For | Cost |
|------|--------|---------|------|
| **Fast** | Claude Haiku, Nova Micro | Classification, triage, simple extraction | Lowest |
| **Balanced** | Claude Sonnet, Nova Lite | Standard extraction, enrichment, summaries | Medium |
| **Premium** | Claude Opus, Nova Pro | Complex reasoning, multi-step analysis, nuanced judgment | Highest |

### Implementation

```python
from enum import Enum

class ModelTier(Enum):
    FAST = "fast"
    BALANCED = "balanced"
    PREMIUM = "premium"

MODEL_MAP = {
    ModelTier.FAST: "anthropic.claude-haiku",
    ModelTier.BALANCED: "anthropic.claude-sonnet",
    ModelTier.PREMIUM: "anthropic.claude-opus",
}

def get_model(tier: ModelTier, config: dict) -> str:
    """Resolve model ID with fallback chain."""
    primary = MODEL_MAP[tier]
    fallbacks = config.get("fallbacks", {}).get(tier, [])
    return primary  # Actual implementation checks availability
```

### Fallback Chain

When a model is unavailable (throttled, outage), fall through:

1. Primary model in primary region
2. Same model via cross-region inference
3. Provisioned throughput (if available)
4. Alternative provider (e.g., direct API)
5. Degrade to cheaper tier (with data classification check)

**Critical rule**: Never fall back to a less capable tier for high-stakes
or safety-critical tasks without explicit configuration allowing it.

### Cost Targeting

Assign model tiers per pipeline node in configuration, not code:

```yaml
pipeline_nodes:
  classify_input:
    model_tier: fast
    description: "Input classification — low complexity"
  extract_fields:
    model_tier: balanced
    description: "Standard field extraction from documents"
  complex_analysis:
    model_tier: premium
    description: "Multi-step reasoning requiring high accuracy"
```

## Confidence Calibration Implementation

### Two-Stage Hybrid

```python
def estimate_confidence(field: dict, config: dict) -> dict:
    """Two-stage confidence estimation."""

    # Stage 1: Business rules (deterministic, ~0ms)
    rule_result = apply_business_rules(field, config)
    if rule_result.tier == "high":
        return {"band": "high", "stage": "business_rule", "rules": rule_result.rules}
    if rule_result.tier == "low":
        return {"band": "low", "stage": "business_rule", "rules": rule_result.rules}

    # Stage 2: Self-consistency (statistical, ~2-5s)
    # Only for medium-confidence outputs
    samples = await run_parallel_extractions(
        prompt=field["prompt"],
        n=config.sample_count,  # default 5
        temperature=config.temperature,  # default 0.7
    )
    agreement = compute_agreement(samples)

    band = (
        "high" if agreement >= 0.80 else
        "medium" if agreement >= 0.60 else
        "low" if agreement >= 0.40 else
        "very_low"
    )

    return {
        "band": band,
        "stage": "self_consistency",
        "agreement_rate": agreement,
        "sample_count": len(samples),
    }
```

### Per-Field Thresholds

Thresholds are configuration, not code:

```yaml
field_catalog:
  primary_identifier:
    criticality: critical
    confidence_threshold: 0.95
    hitl_policy: always_review
  description_field:
    criticality: important
    confidence_threshold: 0.85
    hitl_policy: review_if_low
  reference_code:
    criticality: standard
    confidence_threshold: 0.75
    hitl_policy: batch_review
```

## Cedar Policy Enforcement

Cedar policies control agent authorization **outside** the LLM loop.
AgentCore Policy evaluates Cedar policies at the Gateway level — the agent
cannot reason past them.

### How It Works

```
Agent Node → requests tool → AgentCore Gateway → Cedar Policy Engine
                                                       │
                                              ALLOW or DENY
                                                       │
                                          Tool executes or request rejected
```

### Key Policy Patterns

```cedar
// Agent can only invoke tools within its assigned scope
permit(
  principal,
  action == Action::"invoke_tool",
  resource
) when {
  resource.scope in principal.allowed_scopes
};

// Block writes when approval status is not cleared
forbid(
  principal,
  action == Action::"write",
  resource
) when {
  context.approval_status != "approved"
};

// Enforce spend caps on external API calls
forbid(
  principal,
  action == Action::"invoke_tool",
  resource
) when {
  context.spend_to_date >= context.stage_spend_cap
};
```

### Policy-Driven HITL

Cedar policies determine who can approve which HITL gates. The gate
approval is a Cedar authorization check, not an LLM decision.

See `references/agentcore-deployment.md` for AgentCore Policy setup.

## Cost-Aware Pipeline Design

### Cheap Gates First

Structure pipelines so the cheapest checks run first:

```
Fast checks ($0.01) → Moderate checks ($0.10) → Expensive checks ($1-5)
       │                      │                         │
   70% decline            20% decline              10% decline
```

This dramatically reduces average cost-per-invocation.

### Cost Tracking Per Node

```python
def cost_aware_node(state: PipelineState) -> dict:
    """Track LLM and API costs per node."""
    spend_before = state.get("spend_to_date", 0)

    # Do work...
    result, cost = invoke_model_with_cost_tracking(...)

    spend_after = spend_before + cost
    if spend_after > state.get("stage_spend_cap", float("inf")):
        # Cedar policy will also enforce this, but fail fast here
        raise SpendCapExceeded(spend_after, state["stage_spend_cap"])

    return {"spend_to_date": spend_after, **result}
```

## Observability

### LangSmith Tracing

Instrument every agent with LangSmith for full prompt/response capture:

```python
import os
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_PROJECT"] = "my-agent-pipeline"

# All LangGraph executions are automatically traced
# Each node execution becomes a span with:
# - Input state
# - Output state
# - Model invocations (prompt, response, tokens, latency)
# - Tool calls
# - Errors
```

### Key Metrics

| Metric | Source | Purpose |
|--------|--------|---------|
| Node latency (P50/P95/P99) | LangSmith | Performance monitoring |
| Token usage per node | LangSmith | Cost attribution |
| HITL rate per gate | Application metrics | Automation effectiveness |
| Confidence calibration (ECE) | Override records | Model quality |
| Fallback rate per model | Model router | Availability monitoring |
| Cost per workflow invocation | Aggregated | Business metric |

### AgentCore Observability

AgentCore provides built-in tracing for agent reasoning:
- Decision steps and tool invocations
- Model interactions with timing
- Session lifecycle events

These integrate with CloudWatch for dashboards and alerting.

## Reference Files

- `references/agentcore-deployment.md` — AgentCore Runtime, Gateway, Policy,
  Memory, and Identity setup. CDK patterns. CI/CD for agents.
- `references/production-patterns.md` — Evidence traceability, error handling,
  idempotency, testing strategies, and Bedrock Guardrails configuration.
