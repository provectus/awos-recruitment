# Production Patterns

## Evidence Traceability

Every AI-produced output must link to its source. This is non-negotiable
in regulated environments and best practice everywhere.

### Evidence Coordinate Schema

```python
from pydantic import BaseModel

class EvidenceCoordinate(BaseModel):
    document_id: str          # Source document identifier
    page: int                 # Page number (1-indexed)
    segment_id: str           # Parsed segment identifier
    bounding_box: dict | None # {"x": int, "y": int, "w": int, "h": int}
    source_type: str          # "extraction", "enrichment", "compliance"

class ExtractedField(BaseModel):
    field_name: str
    value: Any
    confidence: float
    confidence_band: str      # "high", "medium", "low"
    confidence_stage: str     # "business_rule" or "self_consistency"
    evidence: list[EvidenceCoordinate]
    model_id: str
    prompt_version: str
```

### Extraction Node Pattern

```python
def extract_field_node(state: PipelineState) -> dict:
    """Extract a field with mandatory evidence coordinates."""
    result = invoke_model(
        prompt=build_extraction_prompt(state),
        model_tier=ModelTier.BALANCED,
    )

    # Parse structured output
    extracted = parse_extraction_response(result)

    # MANDATORY: Attach evidence coordinates
    for field in extracted:
        if not field.evidence:
            raise ValueError(
                f"Field '{field.field_name}' extracted without evidence "
                f"coordinates. This violates audit requirements."
            )

    return {"extracted_fields": extracted}
```

### Evidence Chain Through Pipeline

```
Document → Parsing (segments + bbox) → Extraction (field + evidence)
    → Enrichment (field + API source) → Assembly (all evidence merged)
        → Decision Package (complete evidence chain for audit)
```

Every step adds to the evidence chain. The final decision package must
trace every fact back through the complete chain.

---

## Error Handling and Resilience

### Retry with Exponential Backoff

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def invoke_model_with_retry(prompt, model_id):
    """Invoke Bedrock model with retry on throttling."""
    try:
        return await bedrock.invoke_model(
            modelId=model_id,
            body=prompt,
        )
    except ThrottlingException:
        raise  # Let tenacity retry
    except ModelNotAvailableException:
        # Fall through to next model in fallback chain
        return await invoke_fallback_model(prompt, model_id)
```

### Circuit Breaker for Model Routing

```python
class ModelCircuitBreaker:
    """Track model availability and skip unavailable models."""

    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failures: dict[str, int] = {}
        self.last_failure: dict[str, float] = {}
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

    def is_available(self, model_id: str) -> bool:
        if self.failures.get(model_id, 0) >= self.failure_threshold:
            elapsed = time.time() - self.last_failure.get(model_id, 0)
            if elapsed < self.reset_timeout:
                return False
            # Reset after timeout (half-open state)
            self.failures[model_id] = 0
        return True

    def record_failure(self, model_id: str):
        self.failures[model_id] = self.failures.get(model_id, 0) + 1
        self.last_failure[model_id] = time.time()

    def record_success(self, model_id: str):
        self.failures[model_id] = 0
```

### Graceful Degradation

When external services fail, degrade gracefully:

| Service | Degradation Strategy |
|---------|---------------------|
| Enrichment API down | Skip enrichment, proceed with extraction-only data. Flag in package. |
| Sanctions API down | BLOCK. Cannot proceed without sanctions check. Queue for retry. |
| Model throttled | Fall through fallback chain. If all fail, queue for retry. |
| Checkpoint store unavailable | Fail the node. State machine retries from last checkpoint. |

**Rule**: Compliance-critical services (sanctions, licensing) never degrade.
Non-critical services (enrichment, caching) can be skipped with flags.

---

## Idempotency

### Case-Level Idempotency

Use case ID as the execution name for workflow orchestration:

```python
# Step Functions pattern
sfn.start_execution(
    stateMachineArn=state_machine_arn,
    name=f"case-{case_id}",  # Prevents duplicate executions
    input=json.dumps(case_data),
)
```

### Node-Level Idempotency

Nodes should check for existing results before re-processing:

```python
def enrichment_node(state: PipelineState) -> dict:
    """Enrich case data — skip if already enriched."""
    case_id = state["case_id"]

    # Check cache for existing enrichment
    cached = cache.get(f"enrichment:{case_id}")
    if cached:
        return {"enrichment_data": cached}

    # Perform enrichment
    result = call_enrichment_api(state)

    # Cache result
    cache.set(f"enrichment:{case_id}", result, ttl=3600)

    return {"enrichment_data": result}
```

### Exactly-Once for Critical Writes

For writes to external systems (quote management, policy issuance), use
the state machine's exactly-once semantics:

```python
# Critical writes go through Step Functions (exactly-once)
# NOT through EventBridge (at-least-once)

# Pattern: Agent requests write → Step Functions executes → Event emitted
# The agent NEVER writes directly to external systems
```

---

## Testing Strategies

### Unit Testing Nodes

```python
def test_extraction_node():
    """Test extraction node in isolation."""
    state = PipelineState(
        case_id="test-001",
        documents=[mock_document],
        extracted_fields=[],
    )

    result = extract_field_node(state)

    assert len(result["extracted_fields"]) > 0
    for field in result["extracted_fields"]:
        assert field.evidence, "Evidence coordinates required"
        assert field.confidence > 0
```

### Integration Testing with Checkpoints

```python
def test_hitl_interrupt_resume():
    """Test that interrupt/resume preserves state correctly."""
    app = graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "test-hitl"}}

    # Run until interrupt
    result = app.invoke(initial_state, config)
    state = app.get_state(config)
    assert state.next  # Should be waiting at HITL node

    # Resume with human input
    result = app.invoke(
        Command(resume={"action": "confirmed"}),
        config,
    )
    assert not app.get_state(config).next  # Should be complete
```

### Shadow Mode Testing

Before going live, run agents in shadow mode:

1. Process submissions through both human and agent paths.
2. Compare agent outputs against human ground truth.
3. Measure: accuracy per field, confidence calibration (ECE),
   false positive rate for HITL routing, cost per submission.
4. Only promote to assisted mode after N validated shadow outcomes.

### Cedar Policy Testing

```cedar
// Test that only compliance can approve sanctions gates
@test("sanctions_gate_compliance_can_approve")
permit(
  principal == User::"compliance-officer-1",
  action == Action::"approve_gate",
  resource == Gate::"sanctions_review"
);

@test("sanctions_gate_underwriter_denied")
forbid(
  principal == User::"underwriter-1",
  action == Action::"approve_gate",
  resource == Gate::"sanctions_review"
);
```

---

## Semantic Caching

For repeated or similar queries, use semantic caching to avoid redundant
model invocations:

```python
# Use vector similarity to detect near-duplicate queries
# Cosine similarity threshold: 0.85-0.95 (configurable)

async def cached_extraction(prompt, field_name, config):
    """Check semantic cache before invoking model."""

    # Generate embedding for the prompt
    embedding = await embed(prompt)

    # Search cache for similar prompts
    cached = await vector_cache.search(
        embedding=embedding,
        threshold=config.cache_similarity_threshold,  # 0.90
        filter={"field_name": field_name},
    )

    if cached:
        return cached.result  # Cache hit

    # Cache miss — invoke model
    result = await invoke_model(prompt)

    # Store in cache
    await vector_cache.store(
        embedding=embedding,
        result=result,
        metadata={"field_name": field_name},
        ttl=config.cache_ttl,
    )

    return result
```

**When NOT to cache**: Compliance-critical outputs (sanctions, licensing),
financial-impact fields, or any output where staleness is dangerous.

---

## Bedrock Guardrails Configuration

### Multi-Layer Defense Against Prompt Injection

```python
# Layer 1: Bedrock Guardrails (applied to all model invocations)
guardrail_config = {
    "content_filters": {
        "hate": "HIGH",
        "violence": "HIGH",
        "sexual": "HIGH",
        "misconduct": "HIGH",
        "prompt_attack": "HIGH",  # Blocks prompt injection attempts
    },
    "pii_detection": {
        "action": "ANONYMIZE",  # Mask PII in outputs
        "entities": ["NAME", "EMAIL", "PHONE", "ADDRESS", "SSN"],
    },
    "contextual_grounding": {
        "enabled": True,
        "grounding_threshold": 0.7,
        "relevance_threshold": 0.7,
    },
}

# Layer 2: Cedar policies (deterministic, outside LLM loop)
# Agents cannot access tools they're not authorised for,
# regardless of what's in the prompt

# Layer 3: Input validation at trust boundaries
# Validate all agent inputs against Pydantic schemas
# before passing to LLM

# Layer 4: Output validation
# Validate all agent outputs against expected schemas
# before writing to downstream systems
```

### Document-Based Injection Defense

Insurance documents (uploaded by brokers) are a key attack vector for
indirect prompt injection:

1. **Never trust document content as instructions.** Parse documents for
   data extraction only — do not execute any instructions found in documents.
2. **Separate content from instructions.** Use clear system/user message
   boundaries. Document content goes in the user message, never in the
   system prompt.
3. **Validate extraction outputs.** Check extracted values against expected
   types, ranges, and formats before accepting.
4. **Cedar policies as final guard.** Even if an injection succeeds in
   manipulating the model's output, Cedar policies prevent unauthorized
   tool access or data writes.
