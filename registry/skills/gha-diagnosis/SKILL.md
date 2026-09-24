---
name: gha-diagnosis
context: fork
disable-model-invocation: true
argument-hint: "[run URL or job ID] [--push]"
description: Use when GitHub Actions checks fail, workflow runs are red, or user asks to fix CI. Triggers on "fix CI", "actions failing", "checks are red", "pipeline broke", "workflow failed". User may provide a run URL, job ID, or just ask to fix. Commits fixes locally and stops; pass --push to let it push and re-check CI.
---

# GitHub Actions — Autonomous Failure Fix Loop

Fetch failed workflow logs via `gh`, diagnose root causes, fix, verify locally, commit. All failures in one pass. Fixes stay local unless the user passed `--push`.

## Input

Arguments: `$ARGUMENTS`

This skill runs in its own subagent context with no conversation history, so everything you know about the request is in the line above. It may contain:

- **Nothing** — find failures on the current branch via `gh run list --branch "$(git branch --show-current)" --status failure --limit 5`. Scope to the branch: in a repo with several active branches or scheduled workflows, the newest failure in the repo is often someone else's
- **Run URL** — e.g. `https://github.com/org/repo/actions/runs/123` → extract run ID
- **Run/Job ID** — use directly with `gh run view <id> --log-failed`
- **`--push`** — the user's permission to push the fix commits and confirm the result (Phase 3). Without it, stop after committing and report.

## Context Loading

Read `.github/workflows/*.yml` to understand the exact commands each job runs. These are your local verify commands.

## Phase 1: Fetch and Triage

```bash
gh run view <run-id> --log-failed
```

Group failures by root cause:

| Category | Signals | Typical Fix |
|----------|---------|-------------|
| **Lint/Format** | linter, formatter errors | Auto-fix or targeted edit |
| **Test** | assertion errors, crashes | Fix code or test |
| **Security** | vulnerability flags | Upgrade dep, scoped override |
| **Stale workflow** | action SHA mismatch, deprecated syntax | Update workflow YAML |
| **Env/secrets** | missing var, auth failure | Fix workflow env block |
| **Build** | type errors, import failures | Fix source or dependency |
| **Spec drift** | generated code stale | Regenerate artifacts |

## Phase 2: Fix Loop

Process in dependency order: workflow config → lint → tests → build.

1. **Diagnose** — exact file(s) and line(s) from the log
2. **Fix** — minimal change
3. **Verify** — run the same command from the workflow YAML locally
4. **If fails** — revert, re-read error, try different approach (max 3 attempts)
5. **Commit** — one per logical fix, conventional commit format

## Phase 3: Report — or push, if asked

CI only re-runs against the remote, so the loop can only be confirmed by pushing. Pushing to a shared remote is a side effect the user controls, not this skill — and the branch may carry unpushed work of theirs that is not ready to leave the machine.

**Without `--push`** (default): stop here. Report each fix commit (hash, subject, which failure it addresses), anything you could not fix within three attempts, and how to continue: `git push`, then `/gha-diagnosis <run URL>` once the new run finishes — or `/gha-diagnosis --push` to let the skill do both.

**With `--push`**:

1. Push the fix commits
2. Find the run for the commit you pushed: `gh run list --commit "$(git rev-parse HEAD)" --limit 1 --json databaseId,status,conclusion,url`. Scope to the commit — a bare `--limit 1` returns the newest run in the repo, which may be another branch's and report green or red for the wrong push. The run can take a few seconds to appear; retry briefly if the list is empty
3. Wait for it: `gh run watch <databaseId> --exit-status`
4. If new failures appear, loop back to Phase 1

## Rules

- Batch all failures — don't fix one and stop
- Read the actual log — don't guess from job names
- Verify locally before committing
- One commit per fix
- Revert failed attempts — don't stack patches
- Never push without `--push` in the arguments
- If HEAD is ahead of its upstream (`git log --oneline @{u}..HEAD`), the CI log describes older code than the tree you are reading. Check whether those unpushed commits already touch the failing area and say so in the report — don't push to close the gap; those are the user's commits

## Common Pitfalls

| Pitfall | Instead |
|---------|---------|
| Guess fix from job name | Read `gh run view <id> --log-failed` |
| Blanket dep override | Scope to specific dependency paths |
| Update action SHA blindly | Check release notes for breaking changes |
| Fix warnings not in the error | Only fix what CI flagged |
| `--no-verify` to bypass hooks | Fix the hook issue |
| Trust the newest run in the repo | Scope `gh run list` with `--branch` or `--commit` |
