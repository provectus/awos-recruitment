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

## New Agent Workflow

Building an agent on AgentCore is a sequence, not a menu. The interrupt/resume
test and the Cedar `LOG_ONLY` shadow phase are cheap before deployment and
expensive after, so they earn their place in the order below. Copy this
checklist into your response and tick items off as you go.

- [ ] **Define the state** — typed `TypedDict`, with a reducer on every key a
      parallel node writes (see below).
- [ ] **Write the nodes** — one responsibility each, provenance attached to
      every AI-produced value (`references/production-patterns.md`, *Evidence
      Traceability*).
- [ ] **Place the HITL gates** — pick async / blocking / deferred per gate and
      route to them on confidence, not on node success.
- [ ] **Attach a durable checkpointer** — before the first `interrupt()`, not
      after. An interrupt with an in-memory saver loses the run.
- [ ] **Move model tiers into configuration** — node→tier mapping and model IDs
      in deployment config, with a fallback chain per tier.
- [ ] **Deploy the Cedar policies in `LOG_ONLY`** — analyse the DENY decisions
      before flipping to `ENFORCE` (`references/agentcore-deployment.md`,
      *AgentCore Policy*).
- [ ] **Run the interrupt/resume test** — assert the graph stops at the gate and
      completes after `Command(resume=...)`
      (`references/production-patterns.md`, *Testing Strategies*).
- [ ] **Deploy** — `BedrockAgentCoreApp` entrypoint, then canary
      (`references/agentcore-deployment.md`, *AgentCore Runtime*).

## StateGraph Design Principles

### State Shape

`StateGraph`, `add_node`/`add_edge` wiring and `START`/`END` behave exactly as
the LangGraph docs describe. What is worth deciding deliberately is what goes
*into* the state: carry confidence, review decisions and the current stage
explicitly, so an interrupted run can be resumed and audited from the
checkpoint alone.

```python
from operator import add
from typing import Annotated, TypedDict

class PipelineState(TypedDict):
    task_id: str
    inputs: list[dict]
    processed_results: Annotated[list[dict], add]  # reducer for accumulation
    confidence_scores: dict[str, float]
    review_decisions: list[dict]
    status: str
    current_stage: str
```

The reducer is what makes fan-out safe. Without `Annotated[..., add]`, two
parallel nodes writing `processed_results` in the same superstep raise
`InvalidUpdateError` instead of merging.

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

### Confidence Routing

The branch that matters is the one taken on confidence: it decides which of the
three HITL patterns below a result lands in. Keep the band boundaries in
configuration (see *Per-Field Thresholds*) rather than in the router.

```python
def route_by_confidence(state: PipelineState) -> str:
    """Map overall confidence onto an auto / review / escalate branch."""
    confidence = state["confidence_scores"].get("overall", 0.0)
    if confidence >= 0.85:
        return "auto_proceed"
    if confidence >= 0.60:
        return "human_review"
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

Return `Send` objects from a conditional edge to fan out. Every target writes
back into the same state, so each key they touch needs a reducer.

```python
from langgraph.types import Send  # not langgraph.constants — deprecated in v1.0

def fan_out_enrichment(state: PipelineState) -> list[Send]:
    """Run data sources in parallel."""
    return [
        Send("external_api_lookup", state),
        Send("database_query", state),
        Send("cache_check", state),
    ]

graph.add_conditional_edges("processing_done", fan_out_enrichment)
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

An AgentCore session is bounded — check the current session, request-timeout
and async-job limits in the [AgentCore quotas][quotas] before assuming a
workflow fits inside one. The design rule does not depend on the number:
**anything that may outlive a session — a HITL gate waiting on a human, a
multi-day approval — must checkpoint to durable storage**, so a fresh session
resumes from the checkpoint instead of re-running the graph.

[quotas]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html

### Setup

```python
from langgraph.checkpoint.postgres import PostgresSaver

# from_conn_string is a context manager — it owns the psycopg connection,
# so compile and invoke inside the `with` block.
with PostgresSaver.from_conn_string(db_url) as checkpointer:
    checkpointer.setup()  # creates the checkpoint tables; idempotent

    app = graph.compile(checkpointer=checkpointer)

    # Each workflow gets its own thread
    config = {"configurable": {"thread_id": f"workflow-{task_id}"}}
    result = app.invoke(initial_state, config)
```

### Recovery and Replay

`app.get_state(config).next` is non-empty exactly when the thread is parked at
an interrupt — that is the resume check, and `app.get_state_history(config)`
walks every prior snapshot for audit and debugging.

```python
# Resume a previously interrupted workflow
if app.get_state(config).next:  # There are pending nodes
    result = app.invoke(Command(resume=human_decision), config)
```

## 3-Tier Model Routing

Use different model tiers based on task complexity to optimise cost:

| Tier | Models | Use For | Cost |
|------|--------|---------|------|
| **Fast** | Claude Haiku, Nova Micro | Classification, triage, simple extraction | Lowest |
| **Balanced** | Claude Sonnet, Nova Lite | Standard extraction, enrichment, summaries | Medium |
| **Premium** | Claude Opus, Nova Pro | Complex reasoning, multi-step analysis, nuanced judgment | Highest |

### Implementation

Model IDs belong in configuration, never in a router literal. A Bedrock model ID
carries a version and date suffix, and a cross-region inference profile adds a
geography prefix (`us.`, `eu.`, `apac.`); both change with every model release,
and a stale literal fails at runtime with `ValidationException`. Resolve the IDs
your account can actually call with `bedrock.list_inference_profiles()` /
`list_foundation_models()` and pin the result in config, so a model retirement
is a config change rather than a code change.

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

class ModelTier(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    PREMIUM = "premium"

class NoModelAvailable(RuntimeError):
    """Every model in a tier's chain was unavailable."""

@dataclass(frozen=True, slots=True)
class RouterConfig:
    """Bedrock model IDs per tier, loaded from deployment config."""

    primary: dict[ModelTier, str]
    fallbacks: dict[ModelTier, list[str]] = field(default_factory=dict)

def get_model(
    tier: ModelTier,
    config: RouterConfig,
    is_available: Callable[[str], bool],
) -> str:
    """Return the first available model ID for *tier*.

    ``is_available`` is the circuit breaker from
    ``references/production-patterns.md`` — pass the real one, so a throttled
    model is skipped rather than retried into the same failure.

    Raises:
        NoModelAvailable: neither the primary nor any fallback was available.
    """
    chain = [config.primary[tier], *config.fallbacks.get(tier, [])]
    for model_id in chain:
        if is_available(model_id):
            return model_id
    raise NoModelAvailable(f"no model available for tier {tier}; tried {chain}")
```

### Fallback Chain

Order the per-tier `fallbacks` list so that, when a model is unavailable
(throttled, outage), the router falls through:

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

Stage 2 fans out real model calls, so the whole function is `async` — a sync
node here serialises the samples and blocks the event loop.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ConfidenceConfig:
    """Self-consistency sampling parameters, from the field catalog config."""

    sample_count: int = 5
    temperature: float = 0.7

async def estimate_confidence(field: dict, config: ConfidenceConfig) -> dict:
    """Two-stage confidence estimation."""

    # Stage 1: Business rules (deterministic, ~0ms)
    rule_result = apply_business_rules(field)
    if rule_result.tier in ("high", "low"):
        return {
            "band": rule_result.tier,
            "stage": "business_rule",
            "rules": rule_result.rules,
        }

    # Stage 2: Self-consistency (statistical, ~2-5s)
    # Only for medium-confidence outputs
    samples = await run_parallel_extractions(
        prompt=field["prompt"],
        n=config.sample_count,
        temperature=config.temperature,
    )
    agreement = compute_agreement(samples)

    band = (
        "high" if agreement >= 0.80
        else "medium" if agreement >= 0.60
        else "low" if agreement >= 0.40
        else "very_low"
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

Set `LANGSMITH_TRACING=true` and `LANGSMITH_PROJECT` in the runtime environment,
not in code, and every node execution becomes a span carrying its input state,
output state, model calls and tool calls. What matters here is what you pull off
those spans:

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

Both bundle several independent topics and open with a contents list — read the
section you need, not the file.

`references/agentcore-deployment.md` — **Runtime** when writing the deployment
entrypoint or sizing sessions; **Gateway** when exposing a Lambda or REST API as
a tool; **Policy** when authoring Cedar policies or rolling them `LOG_ONLY` →
`ENFORCE`; **Memory** for context across sessions; **Identity** for workload
identity and outbound auth; **CDK Deployment Patterns** for stack layout and
agent CI/CD; **Bedrock Foundation Models** when resolving model IDs or
cross-region inference; **Bedrock Guardrails** when configuring guardrails.

`references/production-patterns.md` — **Evidence Traceability** when designing
what a node returns; **Error Handling** when implementing the fallback chain or
circuit breaker; **Idempotency** when wiring retries or external writes;
**Testing Strategies** for the interrupt/resume check in the workflow above;
**Semantic Caching** when prompts repeat; **Bedrock Guardrails Configuration**
when hardening against prompt injection.

`references/evals.md` — behaviour checks for this skill. Read when changing the
skill, not when using it.
