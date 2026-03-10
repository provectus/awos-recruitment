# Tasks: Usage Telemetry

---

## Slice 1: Search telemetry — emit `capability_searched` events to PostHog

After this slice, every search query emits a telemetry event. Server remains fully functional without a PostHog API key (silent no-op).

- [ ] **Sub-task 1.1:** Add `posthog>=7.0.0` to `server/pyproject.toml` dependencies and install. **[Agent: python-expert]**
- [ ] **Sub-task 1.2:** Add `posthog_api_key` and `posthog_host` config fields to `Config` dataclass in `config.py`. Update `server/.env.example` with commented placeholders. **[Agent: python-expert]**
- [ ] **Sub-task 1.3:** Create `server/src/awos_recruitment_mcp/telemetry.py` — `Posthog` client initialization with `on_error` callback (no-op if API key is absent), `track_search(query, results)` function, internal error handling with `logger.warning()`. **[Agent: python-expert]**
- [ ] **Sub-task 1.4:** Wire PostHog client lifecycle into `server.py`'s `lifespan()` — create `Posthog` instance on startup (if API key present), call `client.shutdown()` on teardown. Store in lifespan context. **[Agent: python-expert]**
- [ ] **Sub-task 1.5:** Instrument `search_capabilities()` in `tools/search.py` — call `track_search()` after `search_index.query()` returns, before returning results. **[Agent: python-expert]**
- [ ] **Sub-task 1.6:** Add unit tests for `telemetry.py` — verify `track_search()` calls `client.capture()` with correct event name/properties (`capability_searched`, `distinct_id="anonymous"`, query, results list), verify no-op when API key is absent, verify errors are caught and logged. **[Agent: python-expert]**
- [ ] **Sub-task 1.7:** Run the full test suite (`pytest`). Verify all existing tests still pass and new telemetry tests pass. **[Agent: qa-tester]**
- [ ] **Sub-task 1.8:** Git commit. **[Agent: general-purpose]**

---

## Slice 2: Install telemetry — emit `capability_installed` events to PostHog

After this slice, every capability installation (skill, agent, MCP server) emits one event per resolved capability.

- [ ] **Sub-task 2.1:** Add `track_install(capability_name, capability_type)` function to `telemetry.py`. **[Agent: python-expert]**
- [ ] **Sub-task 2.2:** Instrument `bundle_skills()`, `bundle_mcp()`, and `bundle_agents()` in `server.py` — call `track_install(name, type)` for each found capability after path resolution. Use type values: `"skill"`, `"mcp_server"`, `"agent"`. **[Agent: python-expert]**
- [ ] **Sub-task 2.3:** Add unit tests for `track_install()` — verify `client.capture()` is called with correct event name/properties (`capability_installed`, capability_name, capability_type). Add integration tests verifying bundle endpoints trigger telemetry calls. **[Agent: python-expert]**
- [ ] **Sub-task 2.4:** Run the full test suite (`pytest`). Verify all tests pass. **[Agent: qa-tester]**
- [ ] **Sub-task 2.5:** Git commit. **[Agent: general-purpose]**

---

## Slice 3: Production infrastructure — configure PostHog API key in AWS

After this slice, the production ECS deployment receives the PostHog API key via SSM, enabling telemetry in production.

- [ ] **Sub-task 3.1:** Add `aws_ssm_parameter` resource for PostHog API key in `infra/ssm.tf` with `type = "SecureString"`. **[Agent: devops-aws-expert]**
- [ ] **Sub-task 3.2:** Add `AWOS_POSTHOG_API_KEY` to the ECS task definition's `secrets` block in `infra/ecs.tf` (sourced from the new SSM parameter). **[Agent: devops-aws-expert]**
- [ ] **Sub-task 3.3:** Run `terraform validate` and `terraform plan` to verify the infrastructure changes are valid. **[Agent: devops-aws-expert]**
- [ ] **Sub-task 3.4:** Git commit. **[Agent: general-purpose]**

---

## Slice 4: End-to-end verification — confirm events flow in PostHog

After this slice, telemetry is confirmed working end-to-end against the real PostHog instance.

- [ ] **Sub-task 4.1:** With the server running locally (with a real PostHog API key in `.env`), perform a search query and a bundle download. Use the `posthog-telemetry-analyst` agent to query PostHog and verify that `capability_searched` and `capability_installed` events appear with the correct properties. **[Agent: posthog-telemetry-analyst]**
