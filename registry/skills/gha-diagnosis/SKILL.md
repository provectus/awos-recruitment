---
name: gha-diagnosis
context: fork
argument-hint: "<run URL, job ID, or leave empty to auto-detect>"
description: Use when GitHub Actions checks fail, workflow runs are red, or user asks to fix CI. Triggers on "fix CI", "actions failing", "checks are red", "pipeline broke", "workflow failed". User may provide a run URL, job ID, or just ask to fix.
---

# GitHub Actions — Autonomous Failure Fix Loop

Fetch failed workflow logs via `gh`, diagnose root causes, fix, verify locally, commit. All failures in one pass.

## Input

User may provide:
- **Nothing** — find failures via `gh run list --status failure --limit 5`
- **Run URL** — e.g. `https://github.com/org/repo/actions/runs/123` → extract run ID
- **Run/Job ID** — use directly with `gh run view <id> --log-failed`

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

## Phase 3: Push and Confirm

1. Push all fix commits
2. `gh run list --limit 1 --json status,conclusion,url`
3. If new failures appear, loop back to Phase 1

## Rules

- Batch all failures — don't fix one and stop
- Read the actual log — don't guess from job names
- Verify locally before committing
- One commit per fix
- Revert failed attempts — don't stack patches
- Don't diagnose CI from unpushed local code — push first

## Common Pitfalls

| Pitfall | Instead |
|---------|---------|
| Guess fix from job name | Read `gh run view <id> --log-failed` |
| Blanket dep override | Scope to specific dependency paths |
| Update action SHA blindly | Check release notes for breaking changes |
| Fix warnings not in the error | Only fix what CI flagged |
| `--no-verify` to bypass hooks | Fix the hook issue |
