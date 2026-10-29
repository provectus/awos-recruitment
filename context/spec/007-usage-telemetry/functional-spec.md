# Functional Specification: Usage Telemetry

- **Roadmap Item:** Usage Telemetry — add visibility into real-world usage patterns.
- **Status:** Completed
- **Author:** AI-assisted

---

## 1. Overview and Rationale (The "Why")

The AWOS Recruitment server currently has no visibility into how its capabilities are being used in the real world. Team leads like Alex the Tech Lead have no data to answer basic questions: Which skills are developers actually searching for? Which capabilities get installed after discovery? Are certain capabilities consistently discovered but never adopted?

**Usage Telemetry** addresses this by instrumenting the two most important moments in the user journey — **search** and **installation** — plus the caller's report that a search did not help (**gap report**), and forwarding those events to PostHog for storage, analysis, and dashboarding. This gives stakeholders the data they need to make informed decisions about which capabilities to invest in, promote, or deprecate.

**Success looks like:** Telemetry events flow reliably to PostHog for every search and install action, enabling dashboards that show search volume, popular queries, top-installed capabilities, and search-to-install conversion patterns.

---

## 2. Functional Requirements (The "What")

### 2.1. Event: Capability Appeared in Search Results

When a user performs a search and the server returns results, the system must emit a telemetry event to PostHog.

- **Event name:** `capability_searched` (or equivalent PostHog event name)
- **Event data:**
  - The search query text submitted by the client.
  - The list of capability identifiers (IDs or names) returned in the results.
  - The number of results (`result_count`), the best similarity score in the list (`top_score`, `null` when the list is empty), and the capability type the search was restricted to (`type_filter`, `null` when unrestricted). These flat fields let analysts find gaps without parsing the results list: a zero `result_count` is a hard gap, a low `top_score` is a weak match.
- **Acceptance Criteria:**
  - [x] Every successful search that returns one or more results emits a `capability_searched` event to PostHog.
  - [x] The event payload contains the exact query text and the full list of returned capability identifiers.
  - [x] Searches that return zero results still emit the event (with an empty results list) so that "no results" queries are visible.
  - [x] The event payload carries `result_count`, `top_score`, and `type_filter` as flat properties.
  - [x] The event is sent asynchronously — it must not add latency to the search response returned to the client.

### 2.2. Event: Capability Installed

When a user installs a capability, the system must emit a telemetry event to PostHog.

- **Event name:** `capability_installed` (or equivalent PostHog event name)
- **Event data:**
  - The capability identifier (ID or name) that was installed.
- **Acceptance Criteria:**
  - [x] Every successful installation emits a `capability_installed` event to PostHog.
  - [x] The event payload contains the identifier of the installed capability.
  - [x] The event is sent asynchronously — it must not add latency to the install response returned to the client.

### 2.3. Event: Search Did Not Help (Gap Report)

A search event records what the registry returned; it cannot record whether the caller could use it. A result with a high similarity score may still be the wrong capability for the need. The `report_gap` MCP tool lets the caller say so, and the server records it.

- **Event name:** `capability_gap`
- **Event data:**
  - The search text the caller used (`query`).
  - The capability names the search returned (`offered`, possibly empty) and their count (`offered_count`).
  - The caller's reason (`reason`): `no_results`, `not_relevant`, or `wrong_type`.
  - Optionally the role or agent the capability was needed for (`needed_for`) and a one-sentence explanation (`note`). Both are free text from the caller and are sent as written; the tool description tells the caller not to put names of people, companies, clients or repositories in them.
- **Acceptance Criteria:**
  - [x] The `report_gap` tool is listed next to `search_capabilities` and accepts `query`, `reason`, and optional `offered`, `needed_for`, `note`.
  - [x] The tool's input schema lists the allowed `reason` values; a call with any other value fails schema validation and emits nothing.
  - [x] A valid call emits one `capability_gap` event; an empty `query`, or `no_results` with a non-empty `offered` list, returns an error string and emits nothing.
  - [x] The tool changes nothing in the registry and never fails the caller because of a telemetry error.

### 2.4. Failure Handling

Telemetry must never degrade the core search and install experience.

- **Acceptance Criteria:**
  - [x] If sending an event to PostHog fails (network error, service unavailable, timeout), the failure is logged for ops visibility and the event is discarded.
  - [x] A telemetry failure never causes the search or install request to fail, slow down, or return an error to the client.

### 2.5. Anonymity

All telemetry events are fully anonymous.

- **Acceptance Criteria:**
  - [x] No user identifier, team identifier, IP address, or any other personally identifiable information is included in any telemetry event.
  - The free-text fields (the search `query`, and `needed_for` and `note` of a gap report) are sent as the caller wrote them. The server does not filter them; the tool descriptions tell the caller what not to put in them.
  - [x] There is no opt-out mechanism — all events are always sent.

---

## 3. Scope and Boundaries

### In-Scope

- Emitting `capability_searched` events to PostHog on every search.
- Emitting `capability_installed` events to PostHog on every install.
- Emitting `capability_gap` events to PostHog when a caller reports through `report_gap` that a search did not help.
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
