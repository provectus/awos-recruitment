# Purpose

Hook definitions distributed via the AWOS registry — installed into user projects as `.claude/hooks/<name>/` plus a derived entry in `.claude/settings.json`.

# Non-Obvious Context

- The triple identity rule: front matter `name` == directory name == entrypoint filename `<name>.sh`. The injected command is always derived from the name — a `command` field in front matter is forbidden by design (settled decision; no sidecar yaml/json config either).
- Entrypoints must be pure POSIX sh (+ git and POSIX userland — grep, sed, cksum, etc.). Never python or node — hooks install into arbitrary user projects and must add zero runtime dependencies.
- Exit-code contract: `2` blocks the tool call and feeds stderr back to the model — that stderr text is the *only* channel to steer the agent (hooks cannot invoke skills; write the message as imperative instructions). `0` allows. Fail open (`exit 0`) on anything unexpected — malformed stdin, missing git, wrong environment.
- The executable bit is part of the artifact: git tracks the file mode, and validation, bundling, and install all depend on it. A `Write`-created script needs `chmod +x` before committing.
- The registry currently ships no hooks. Server and CLI tests pin the hook contract against a synthetic `sample-gate` hook staged in a tmp registry (`server/tests/conftest.py::hook_registry`), so adding or removing a real hook does not require touching them — but a hook name referenced from `README.md` or install docs is still a repo-wide rename.
- `description` is the semantic-search surface — keep the trigger phrases users would type ("block", "commit", "docs", event names) in it.
- Every hook script gets a behavior test suite at `server/tests/test_<name>_hook.py` executing the real script via subprocess; scenario setup (e.g. scratch git repos) lives there, not in the hook directory.
