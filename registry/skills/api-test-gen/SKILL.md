---
name: api-test-gen
description: >
  Generate automated API test suites with typed models from OpenAPI/Swagger specs,
  Postman collections, GraphQL schemas, or plain API descriptions. Produces
  TypeScript/Playwright or Python/pytest test files, typed request/response models,
  full project scaffolding, and an HTML report. Trigger for: "generate tests from swagger",
  "create API tests from OpenAPI", "generate playwright tests from spec", "generate typed
  models from spec", "create test project from postman collection", "test this API spec",
  "generate API test project", "show API test report", "write API tests for this endpoint",
  "generate tests for my REST API". Also trigger if the user uploads or pastes a spec,
  describes API endpoints, or mentions testing or models in an API context.
---

# API Test Generator

Full test lifecycle from spec to HTML report — runs entirely inside Claude Code with no external dependencies beyond Node.js/Python.

**Workflow (always follow in order):**
1. [Ingest spec](#step-1--ingest-spec) — parse and model the API
2. [Configure env](#step-2--configure-env) — set base URL, auth, output dir
3. [Generate scenarios](#step-3--generate-scenarios) — happy path + negative + edge cases
4. [Generate models](#step-3b--generate-models) — typed request/response objects per schema
5. [Generate test cases](#step-4--generate-test-cases) — write runnable code files using models
6. [Generate project scaffold](#step-5--generate-project-scaffold) — dependencies, config, runner
7. [Run tests](#step-6--run-tests) — execute and capture results
8. [Generate HTML report](#step-7--generate-html-report) — human-readable results

Skip steps 7–8 if the user only wants the generated files, not execution.

---

## Step 1 — Ingest Spec

**Supported input types:**
- OpenAPI 3.x (JSON or YAML)
- Swagger 2.0 (JSON or YAML)
- Postman Collection v2.1 (JSON)
- GraphQL schema (SDL or introspection JSON) — see `references/graphql.md`

**How to receive the spec:**
- File path provided → read from filesystem
- URL provided → fetch with `curl` or Python `requests`
- Pasted inline → write to temp file first
- No spec provided → ask the user to describe endpoints (method, path, request/response shape); construct the endpoint model manually from their description

**Parse and extract this model per endpoint:**
```
{
  method, path, operationId, tag, summary,
  parameters: [{ name, in, required, schema, example }],
  requestBody: { required, mediaType, schema, example },
  responses: { "200": { schema }, "400": { schema }, ... },
  security: [{ type: bearer|apikey|basic|oauth2, name }],
  deprecated: bool
}
```

**$ref resolution:** fully resolve all `$ref` chains before modelling. Handle
`allOf`/`oneOf`/`anyOf` by flattening to the most concrete representative variant.

**Postman → endpoint model:** map each `request` item in the collection to the same
endpoint model above. Infer schema from example bodies.

After parsing, print a **summary table:**
```
Spec loaded: <title> v<version>
Endpoints: <N>  |  Tags: <list>  |  Auth schemes: <list>
Frameworks available: typescript/playwright, python/pytest
```

---

## Step 2 — Configure Env

Ask the user (or infer from context) for:

| Variable | Purpose | Default |
|---|---|---|
| `BASE_URL` | API base URL | prompt user |
| `auth_bearer` | Bearer token | env var `API_TOKEN` |
| `auth_apikey` | API key value | env var `API_KEY` |
| `auth_apikey_header` | API key header name | `X-API-Key` |
| `auth_basic` | base64 user:pass | env var `API_BASIC` |
| `OUTPUT_DIR` | where to write files | `./api-tests` |
| `LANGUAGE` | target framework | ask user |
| `RUN_LOAD_TESTS` | include load tests | false |

**Never hardcode secrets.** Write a `.env.example` with placeholder values.

---

## Step 3 — Generate Scenarios

For each endpoint, generate scenario objects (not code yet — just structured data):

```json
{
  "operationId": "createUser",
  "method": "POST",
  "path": "/users",
  "scenarios": [
    { "id": "happy_valid_body", "type": "happy", "description": "valid body → 201" },
    { "id": "neg_missing_email", "type": "negative", "description": "missing required email → 422" },
    { "id": "neg_wrong_type_age", "type": "negative", "description": "age is string not int → 422" },
    { "id": "neg_no_auth", "type": "negative", "description": "no auth token → 401" },
    { "id": "edge_max_name", "type": "edge", "description": "name at maxLength boundary" },
    { "id": "edge_min_name", "type": "edge", "description": "name at minLength boundary" }
  ]
}
```

**Scenario types to always include:**
- `happy` — one per endpoint with valid data from spec examples (or synthesized)
- `negative` — one per required field (missing), one for wrong type, one for no-auth
- `edge` — one per constraint (`minimum`, `maximum`, `minLength`, `maxLength`, `enum` invalid)

**CRUD workflow detection:** if endpoints match `POST /resource` + `GET /resource/{id}` +
`PUT|PATCH /resource/{id}` + `DELETE /resource/{id}`, add a `workflow` scenario that chains them.

**Print scenario summary:**
```
Scenarios generated: <N total>
  happy: <N>  |  negative: <N>  |  edge: <N>  |  workflow: <N>
```

If `include_negative_tests=false` was requested, skip negative/edge scenarios.

---

## Step 3b — Generate Models

Generate typed model classes/interfaces from all schemas in the spec. Models are used
in test files instead of inline raw dicts — improving readability, reuse, and type safety.

**File location:**
```
api-tests/models/          ← one file per OpenAPI tag or schema group
  user.ts / user.py
  pet.ts  / pet.py
  store.ts / store.py
```

**TypeScript — interfaces:**
```typescript
// models/user.ts
export interface CreateUserRequest {
  name: string;
  email: string;
  age?: number;
}

export interface CreateUserResponse {
  id: string;
  name: string;
  email: string;
  createdAt: string;
}

export interface UserListResponse {
  items: CreateUserResponse[];
  total: number;
}
```

**Python — dataclasses:**
```python
# models/user.py
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class CreateUserRequest:
    name: str
    email: str
    age: Optional[int] = None

@dataclass
class CreateUserResponse:
    id: str
    name: str
    email: str
    created_at: str

@dataclass
class UserListResponse:
    items: List[CreateUserResponse] = field(default_factory=list)
    total: int = 0
```

**Naming rules:**
- Request body schema → `<OperationId>Request`
- Response body schema → `<OperationId>Response` (per status code if multiple)
- Reusable component schema → use its `$components/schemas/<Name>` name as-is
- Path/query parameter objects → `<OperationId>Params`

**Type mapping (OpenAPI → TypeScript / Python):**

| OpenAPI type | TypeScript | Python |
|---|---|---|
| `string` | `string` | `str` |
| `string/date-time` | `string` | `str` |
| `string/uuid` | `string` | `str` |
| `integer` | `number` | `int` |
| `number` | `number` | `float` |
| `boolean` | `boolean` | `bool` |
| `array` | `T[]` | `List[T]` |
| `object` (inline) | nested `interface` | nested `@dataclass` |
| optional field | `field?: T` | `Optional[T] = None` |

**Models are imported in test files:**
```typescript
// TypeScript — import and use in test
import { CreateUserRequest, CreateUserResponse } from '../models/user';

const payload: CreateUserRequest = { name: 'test-string-name', email: 'test@example.com' };
const res = await api.post('/users', { data: payload });
const body = await res.json() as CreateUserResponse;
expect(body.id).toBeTruthy();
```

```python
# Python — import and use in test
from models.user import CreateUserRequest, CreateUserResponse
import dacite

payload = CreateUserRequest(name='test-string-name', email='test@example.com')
res = api.post('/users', json=asdict(payload))
body = dacite.from_dict(CreateUserResponse, res.json())
assert body.id
```

**Edge cases:**
- `allOf` → merge all fields into one interface/dataclass
- `oneOf` / `anyOf` → generate a `Union` type (Python) or type alias (TypeScript)
- Circular references → use `interface` forward reference or `Optional` with string annotation
- Schema with no properties → generate empty interface/dataclass with a TODO comment

---

## Step 4 — Generate Test Cases

Read the appropriate reference file for the chosen framework:
- TypeScript + Playwright → `references/playwright-ts.md`
- Python + pytest → `references/pytest.md`

Then write the actual test files following that reference's conventions exactly.

**File naming:** one file per OpenAPI tag (or `general` if no tags). Example:
```
api-tests/tests/users.spec.ts
api-tests/tests/pets.spec.ts
```

**Test naming convention (always):**
`test_<method>_<path_slug>_<scenario_id>`
Example: `test_post_users_happy_valid_body`

**Data synthesis rules (when no example in spec):**
- `string` → `"test-string-<field-name>"`
- `string/email` → `"test@example.com"`
- `string/uuid` → `"00000000-0000-0000-0000-000000000001"`
- `integer` → midpoint of min/max range, or `1`
- `boolean` → `true`
- `array` → one-element array of the item type
- `object` → synthesize all required fields recursively

---

## Step 5 — Generate Project Scaffold

Generate a complete runnable project. Read `references/scaffold.md` for the exact file
structure and templates per framework.

Always include:
- `package.json` / `requirements.txt` with all dependencies
- Framework config file (`playwright.config.ts`, `pytest.ini`)
- `.env.example` with all required variables
- `README.md` with install + run instructions
- `models/` directory with generated model files
- `reports/` directory (empty, for HTML output)

---

## Step 6 — Run Tests

Only run if the user explicitly asks to execute tests AND a `BASE_URL` is configured.

```bash
cd $OUTPUT_DIR

# TypeScript/Playwright
npm install
npx playwright test --reporter=html

# Python/pytest
pip install -r requirements.txt --break-system-packages
pytest tests/ -v --json-report --json-report-file=reports/results.json
```

Capture stdout/stderr. Parse results to extract:
- total, passed, failed, skipped
- per-test: name, status, duration, error message if failed

---

## Step 7 — Generate HTML Report

Always generate an HTML report — even if tests weren't run (show "generated, not executed").

Read `references/report-template.md` for the exact HTML template.

The report must include:
- Summary bar: total / passed / failed / skipped + pass rate %
- Per-tag sections with expandable test rows
- Status badges (green/red/grey)
- Error details inline for failures
- Timestamp and spec metadata in the header
- Coverage table: endpoint × scenario type matrix

Write to `$OUTPUT_DIR/reports/index.html` and present it to the user.

---

## Load Testing (optional)

If `RUN_LOAD_TESTS=true` or user asks for load/performance tests, read `references/load-tests.md`.
Uses `autocannon` (Node) or `locust` (Python) depending on framework choice.

Default load profile: 10 virtual users, 30 seconds, ramp-up 5s.

---

## Edge Cases

| Situation | Handling |
|---|---|
| No examples in spec | Synthesize from type + format + constraints |
| Circular `$ref` | Detect and break; use `{}` placeholder with TODO comment |
| `oneOf`/`anyOf` request body | Generate one test variant per branch |
| File upload (`multipart/form-data`) | Generate with mock file path; flag for manual review |
| OAuth2 flows | Generate token-fetch helper using env vars; note manual step |
| Deprecated endpoints | Generate tests but mark `@deprecated` in comment |
| Missing `responses` in spec | Assert only 2xx; add TODO comment |
| GraphQL | See `references/graphql.md` |

---

## Quality Rules (always apply)

- No hardcoded secrets — all credentials via env vars
- Test isolation — each test cleans up its own created resources
- Descriptive names — `test_post_users_neg_missing_email` not `test3`
- Typed models — always import from `models/` instead of using inline dicts
- Single assertion focus — one logical assertion per test where possible
- Idempotent — tests can re-run without side effects
- Imports only from generated project, no ad-hoc dependencies
