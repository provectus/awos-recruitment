# Tasks: Capability Installation

## Slice 1: `POST /bundle/skills` endpoint

_Smallest server-side value: POST a list of skill names, get a tar.gz back._

- [x] **Add `BundleRequest` Pydantic model** in `models/bundle.py` with `names: list[str]` field (1-20 items, each matching `^[a-z0-9-]{1,64}$`). Re-export in `models/__init__.py`. **[Agent: python-expert]**
- [x] **Add `resolve_skill_paths()` function** in `registry.py`. Accepts a list of names and a registry path, returns the found directory paths and not-found names by checking `skills/<name>/` exists. **[Agent: python-expert]**
- [x] **Add `POST /bundle/skills` route** in `server.py`. Parse request with `BundleRequest` (return 400 on validation failure), call `resolve_skill_paths`, build tar.gz in memory with `tarfile` (archive layout: `<name>/SKILL.md`, `<name>/references/*.md`), return as `Response(media_type="application/gzip")`. **[Agent: python-expert]**
- [x] **Add tests** in `tests/test_bundle.py` using `httpx.ASGITransport` pattern. Cases: valid request (verify tar.gz contents), partial matches (some found, some not), empty names list (400), names exceeding limit (400), all not-found (200 with empty archive). **[Agent: python-expert]**
- [x] **Verify:** Run `cd server && uv run pytest tests/test_bundle.py -v` — all tests pass. Start server, POST with curl, verify tar.gz extracts correctly. **[Agent: qa-tester]**

- [x] **Git commit** **[Agent: general-purpose]**

---

## Slice 2: `POST /bundle/mcp` endpoint

_Second server-side piece: POST a list of MCP tool names, get a tar.gz of YAML files._

- [x] **Add `resolve_mcp_paths()` function** in `registry.py`. Accepts a list of names and a registry path, returns found YAML file paths and not-found names by checking `mcp/<name>.yaml` exists. **[Agent: python-expert]**
- [x] **Add `POST /bundle/mcp` route** in `server.py`. Same pattern as `/bundle/skills` but calls `resolve_mcp_paths` and archives individual YAML files (layout: `<name>.yaml`). **[Agent: python-expert]**
- [x] **Add tests** in `tests/test_bundle.py`. Cases: valid request (verify tar.gz contains correct YAML files), partial matches, empty names (400), all not-found (200 with empty archive). **[Agent: python-expert]**
- [x] **Verify:** Run `cd server && uv run pytest tests/test_bundle.py -v` — all tests pass. Also run `uv run pytest -v` to confirm no regressions. **[Agent: qa-tester]**

- [x] **Git commit** **[Agent: general-purpose]**

---

## Slice 3: CLI project scaffold

_Runnable CLI that parses subcommands and prints help/errors — no server calls yet._

- [x] **Initialize the `cli/` package.** Create `package.json` (name, version, `"type": "module"`, `bin` entry, scripts for build/test/lint), `tsconfig.json` (ES2022, Node16, strict), install dependencies (`tar`, `yaml`, `typescript`, `@types/node`, `vitest`). **[Agent: typescript-expert]**
- [x] **Create entry point and CLI routing.** `src/index.ts` (shebang, top-level error boundary), `src/cli.ts` (parse `process.argv`, route to `skill`/`mcp` subcommand, print usage on invalid input), `src/lib/errors.ts` (CliError hierarchy with exit codes), `src/lib/types.ts` (shared interfaces). **[Agent: typescript-expert]**
- [x] **Verify:** Run `cd cli && npm run build && node dist/index.js` — prints usage message. `node dist/index.js skill` — prints error about missing names. `node dist/index.js invalid` — prints error about unknown subcommand. **[Agent: qa-tester]**

- [x] **Git commit** **[Agent: general-purpose]**

---

## Slice 4: CLI `skill` install command (end-to-end)

_First real CLI value: `npx awos skill modern-python-development` works against a running server._

- [x] **Add `download.ts` library.** `fetch()` a bundle endpoint URL, pipe response through `zlib.createGunzip()` and `tar.extract()` to a temp directory. Handle network errors (unreachable server) and bad responses (non-200, corrupt body). Return the temp directory path. **[Agent: typescript-expert]**
- [x] **Add `commands/skill.ts`.** POST names to `{AWOS_SERVER_URL}/bundle/skills` via `download.ts`. Diff requested names against extracted directories to find not-found names. For each found skill: check `.claude/skills/<name>/` doesn't exist (conflict → skip with error), otherwise copy directory. Print per-item results (installed / not found / conflict). Exit non-zero if any failed. **[Agent: typescript-expert]**
- [x] **Add unit tests** for `download.ts` (mock `fetch`, test network errors, corrupt responses) and `commands/skill.ts` (temp dirs, mock HTTP, verify files written, conflict detection, not-found reporting). **[Agent: typescript-expert]**
- [x] **Verify end-to-end:** Start the AWOS server (`cd server && uv run python -m awos_recruitment_mcp`). In another terminal, run `cd cli && node dist/index.js skill modern-python-development`. Confirm `.claude/skills/modern-python-development/SKILL.md` exists. Run again — confirm conflict error. Run with a nonexistent name — confirm not-found error. **[Agent: qa-tester]**

- [x] **Git commit** **[Agent: general-purpose]**

---

## Slice 5: CLI `mcp` install command (end-to-end)

_Second CLI value: `npx awos mcp context7` writes to `.mcp.json`._

- [ ] **Add `json-merge.ts` library.** Read `.mcp.json` from cwd (or start with `{"mcpServers":{}}` if missing). For a given server key and config, check if key exists in `mcpServers` (conflict). If not, merge and write back. Handle malformed JSON with a clear error. **[Agent: typescript-expert]**
- [ ] **Add `commands/mcp.ts`.** POST names to `{AWOS_SERVER_URL}/bundle/mcp` via `download.ts`. For each extracted YAML file: parse with `yaml`, extract the server key and config from the `config` field, call `json-merge.ts` to write to `.mcp.json`. Print per-item results. Exit non-zero if any failed. **[Agent: typescript-expert]**
- [ ] **Add unit tests** for `json-merge.ts` (create new file, merge into existing, conflict detection, preserve unknown keys, malformed JSON) and `commands/mcp.ts` (temp dirs, mock HTTP, verify `.mcp.json` contents, conflict detection). **[Agent: typescript-expert]**
- [ ] **Verify end-to-end:** Start the AWOS server. Run `cd cli && node dist/index.js mcp context7`. Confirm `.mcp.json` exists with the `context7` server entry. Run again — confirm conflict error. Run with nonexistent name — confirm not-found error. Run `node dist/index.js mcp context7 playwright` — confirm multi-install summary. **[Agent: qa-tester]**

- [ ] **Git commit** **[Agent: general-purpose]**
