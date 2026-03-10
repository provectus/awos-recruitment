# Technical Specification: Usage Telemetry

- **Functional Specification:** `context/spec/007-usage-telemetry/functional-spec.md`
- **Status:** Completed
- **Author(s):** AI-assisted

---

## 1. High-Level Technical Approach

Add a thin telemetry module to the Python MCP server that wraps the PostHog Python SDK. Instrument two existing code paths:

1. **Search tool** (`tools/search.py`) — emit `capability_searched` after every query.
2. **Bundle endpoints** (`server.py`) — emit `capability_installed` for each capability successfully resolved in a bundle request.

The PostHog Python SDK's `capture()` is non-blocking by design (it queues events to an internal background thread that batches and flushes), satisfying the "no added latency" requirement. If the PostHog API key is not configured, telemetry is silently disabled.

No changes to the TypeScript CLI are needed — install events are captured server-side when bundle endpoints are called.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. New Dependency

| Package | Version | Purpose |
|---|---|---|
| `posthog` | `>=7.0.0` | PostHog Python SDK v7 for event capture (requires Python >=3.10; project uses >=3.12) |

Add to `server/pyproject.toml` under `dependencies`. Reference: [posthog on PyPI](https://pypi.org/project/posthog/).

### 2.2. Configuration Changes

**File:** `server/src/awos_recruitment_mcp/config.py`

Add two new fields to the `Config` dataclass:

| Field | Env Var | Type | Default | Purpose |
|---|---|---|---|---|
| `posthog_api_key` | `AWOS_POSTHOG_API_KEY` | `str \| None` | `None` | PostHog project API key. If `None`, telemetry is silently disabled. |
| `posthog_host` | `AWOS_POSTHOG_HOST` | `str` | `https://us.i.posthog.com` | PostHog ingestion endpoint (allows EU or self-hosted instances). |

**File:** `server/.env.example` — add commented placeholders for both vars.

### 2.3. New Module: Telemetry

**File:** `server/src/awos_recruitment_mcp/telemetry.py`

Responsibilities:
- Initialize the PostHog client from config (or create a no-op if API key is absent).
- Expose two functions: `track_search()` and `track_install()`.
- Handle all PostHog errors internally — log failures via `logging.getLogger(__name__).warning()` and never raise.

| Function | Parameters | PostHog Event | Properties |
|---|---|---|---|
| `track_search(query, results)` | `query: str`, `results: list[dict]` | `capability_searched` | `query`: search query text; `results`: list of capability names returned |
| `track_install(capability_name, capability_type)` | `capability_name: str`, `capability_type: str` | `capability_installed` | `capability_name`: name of installed capability; `capability_type`: `"skill"` \| `"agent"` \| `"mcp_server"` |

Both functions use a static `distinct_id` value (e.g., `"anonymous"`) for all events.

**Client initialization pattern (PostHog Python SDK v7):**

```python
from posthog import Posthog

client = Posthog(
    project_api_key='<api_key>',
    host='<host>',
    on_error=lambda error: logger.warning("PostHog error: %s", error),
)

# Capture (non-blocking by default — queues to background thread):
client.capture('event_name', distinct_id='anonymous', properties={...})

# Clean shutdown (flush pending events + stop background thread):
client.shutdown()
```

**Lifecycle:** Create the `Posthog` client instance during server lifespan startup (in `server.py`'s `lifespan()`). Call `client.shutdown()` during lifespan teardown to flush any pending events. If no API key is configured, skip client creation entirely — `track_search()` and `track_install()` become no-ops.

### 2.4. Instrumentation Points

**Search event** — `server/src/awos_recruitment_mcp/tools/search.py`:
- After `search_index.query()` returns results and before the function returns, call `track_search(query, results)`.

**Install event** — `server/src/awos_recruitment_mcp/server.py`:
- In each of the three bundle handlers (`bundle_skills`, `bundle_mcp`, `bundle_agents`), after resolving which capabilities were found, call `track_install(name, type)` once per found capability.
- Capability type values: `"skill"` for `bundle_skills`, `"mcp_server"` for `bundle_mcp`, `"agent"` for `bundle_agents`.

### 2.5. Infrastructure Changes

**File:** `infra/ssm.tf`
- Add an `aws_ssm_parameter` resource for the PostHog API key with `type = "SecureString"`.

**File:** `infra/ecs.tf`
- Add `AWOS_POSTHOG_API_KEY` to the ECS task definition's `secrets` block (sourced from SSM).
- Optionally add `AWOS_POSTHOG_HOST` if the default needs to be overridden per environment.

---

## 3. Impact and Risk Analysis

### System Dependencies

| Dependency | Impact |
|---|---|
| PostHog cloud service | Telemetry delivery depends on PostHog availability. By design, failures are logged and discarded — zero impact on core functionality. |
| PostHog Python SDK | Adds a runtime dependency and a background thread for event batching. Minimal resource footprint. |
| AWS SSM Parameter Store | API key stored as SecureString. Already used for other config — no new infrastructure pattern. |

### Potential Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| PostHog service outage causes event loss | Low | Acceptable — events are best-effort. Failures are logged for ops awareness. |
| PostHog SDK background thread impacts server performance | Very Low | The SDK thread is lightweight (batches events, flushes periodically). No measurable impact expected. |
| API key leaked in logs or error messages | Low | Never log the API key value. PostHog SDK does not log keys by default. |
| Missing API key in production deployment | Medium | Telemetry silently disables. No user-facing impact, but ops should verify telemetry is flowing after deployment. |

---

## 4. Testing Strategy

- **Unit tests** for `telemetry.py`: mock the PostHog client and verify that `track_search()` and `track_install()` call `posthog.capture()` with the correct event names and properties, and that failures are caught and logged.
- **Unit test for disabled telemetry**: verify that when no API key is configured, calling `track_search()` / `track_install()` is a silent no-op.
- **Integration tests**: verify that the search tool and bundle endpoints call the telemetry functions by checking mock invocations during end-to-end request flows.
