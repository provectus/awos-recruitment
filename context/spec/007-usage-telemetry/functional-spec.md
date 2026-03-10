# Functional Specification: Usage Telemetry

- **Roadmap Item:** Usage Telemetry — add visibility into real-world usage patterns.
- **Status:** Draft
- **Author:** AI-assisted

---

## 1. Overview and Rationale (The "Why")

The AWOS Recruitment server currently has no visibility into how its capabilities are being used in the real world. Team leads like Alex the Tech Lead have no data to answer basic questions: Which skills are developers actually searching for? Which capabilities get installed after discovery? Are certain capabilities consistently discovered but never adopted?

**Usage Telemetry** addresses this by instrumenting the two most important moments in the user journey — **search** and **installation** — and forwarding those events to PostHog for storage, analysis, and dashboarding. This gives stakeholders the data they need to make informed decisions about which capabilities to invest in, promote, or deprecate.

**Success looks like:** Telemetry events flow reliably to PostHog for every search and install action, enabling dashboards that show search volume, popular queries, top-installed capabilities, and search-to-install conversion patterns.

---

## 2. Functional Requirements (The "What")

### 2.1. Event: Capability Appeared in Search Results

When a user performs a search and the server returns results, the system must emit a telemetry event to PostHog.

- **Event name:** `capability_searched` (or equivalent PostHog event name)
- **Event data:**
  - The search query text submitted by the client.
  - The list of capability identifiers (IDs or names) returned in the results.
- **Acceptance Criteria:**
  - [ ] Every successful search that returns one or more results emits a `capability_searched` event to PostHog.
  - [ ] The event payload contains the exact query text and the full list of returned capability identifiers.
  - [ ] Searches that return zero results still emit the event (with an empty results list) so that "no results" queries are visible.
  - [ ] The event is sent asynchronously — it must not add latency to the search response returned to the client.

### 2.2. Event: Capability Installed

When a user installs a capability, the system must emit a telemetry event to PostHog.

- **Event name:** `capability_installed` (or equivalent PostHog event name)
- **Event data:**
  - The capability identifier (ID or name) that was installed.
- **Acceptance Criteria:**
  - [ ] Every successful installation emits a `capability_installed` event to PostHog.
  - [ ] The event payload contains the identifier of the installed capability.
  - [ ] The event is sent asynchronously — it must not add latency to the install response returned to the client.

### 2.3. Failure Handling

Telemetry must never degrade the core search and install experience.

- **Acceptance Criteria:**
  - [ ] If sending an event to PostHog fails (network error, service unavailable, timeout), the failure is logged for ops visibility and the event is discarded.
  - [ ] A telemetry failure never causes the search or install request to fail, slow down, or return an error to the client.

### 2.4. Anonymity

All telemetry events are fully anonymous.

- **Acceptance Criteria:**
  - [ ] No user identifier, team identifier, IP address, or any other personally identifiable information is included in any telemetry event.
  - [ ] There is no opt-out mechanism — all events are always sent.

---

## 3. Scope and Boundaries

### In-Scope

- Emitting `capability_searched` events to PostHog on every search.
- Emitting `capability_installed` events to PostHog on every install.
- Asynchronous, non-blocking event delivery.
- Logging telemetry delivery failures for ops visibility.

### Out-of-Scope

- **Dashboards and analytics views** — PostHog handles all visualization and querying; no custom UI is built.
- **Telemetry storage** — PostHog is the sole data store; no local/custom persistence layer.
- **Post-install usage tracking** — tracking whether a capability is actually invoked after install is not included.
- **Uninstall tracking** — no event is emitted when a capability is removed.
- **User/team identity or opt-out mechanisms** — events are anonymous with no opt-out.
- **MCP Server & Protocol Integration** — separate, already completed roadmap item.
- **Capability Registry & Indexing** — separate, already completed roadmap item.
- **Semantic Capability Search** — separate, already completed roadmap item.
- **Capability Installation** — separate, already completed roadmap item.
- **Agent Support** — separate, already completed roadmap item.
- **MCP Deployment on AWS** — separate, already completed roadmap item.
