# Code Audit

Extensible, dimension-based code quality audit for Claude Code. Run `/code-audit` and get a scored report with actionable recommendations — no configuration required.

## Install

```bash
npx @provectusinc/awos-recruitment skill code-audit
```

## Usage

Once installed, invoke the skill in Claude Code:

```
/code-audit
```

The audit discovers all dimension files automatically, schedules them in dependency order, and produces a graded report at `context/audits/YYYY-MM-DD/report.md`.

## How It Works

Each **dimension** is a self-contained `.md` file in `dimensions/` with YAML frontmatter declaring its dependencies. The engine:

1. Parses all dimension files and builds a dependency DAG
2. Groups dimensions into phases — all dimensions whose dependencies are satisfied run in parallel
3. Evaluates checks per dimension
4. Scores results and writes per-dimension artifacts
5. Compiles a full report with an overall grade

### Scoring

Every check produces a status: **PASS**, **WARN**, **FAIL**, or **SKIP**. Deductions scale by severity:

| Severity | Max Points | FAIL | WARN |
|----------|-----------|------|------|
| critical | 3         | -3   | -1.5 |
| high     | 2         | -2   | -1   |
| medium   | 1         | -1   | -0.5 |
| low      | 0.5       | -0.5 | -0.25|

Dimension scores average into an overall percentage mapped to a letter grade (A: 90-100, B: 75-89, C: 60-74, D: 40-59, F: 0-39).

## Dimensions

| Dimension | Severity | Dependencies |
|-----------|----------|-------------|
| **Project Topology** | medium | — |
| **Security Guardrails** | critical | project-topology |
| **AI Development Tooling** | high | project-topology |
| **Spec-Driven Development** | critical | project-topology |
| **Documentation Quality** | critical | project-topology |
| **Code Architecture** | high | project-topology |
| **Software Best Practices** | high | project-topology |
| **End-to-End Delivery** | high | all others |

**Project Topology** runs first as a reconnaissance phase — it detects the repo structure, languages, and layers so downstream dimensions can skip irrelevant checks.

**End-to-End Delivery** runs last since it depends on every other dimension's results.

## Outputs

Each audit run writes to `context/audits/YYYY-MM-DD/`:

```
context/audits/YYYY-MM-DD/
├── project-topology.md          # per-dimension artifact
├── security.md
├── ...
├── report.md                    # full audit report
├── recommendations.md           # prioritized action items
└── report.html                  # standalone HTML report (optional)
```

When a previous audit exists, the report includes score deltas per dimension.

After presenting the markdown report, the skill offers to generate an HTML version — a single self-contained file you can open in any browser or share with the team.

## Extending

Add a new dimension by dropping a `.md` file into `dimensions/`. No code changes needed.

```markdown
---
name: my-dimension
title: My Dimension
description: What this dimension measures
severity: high
depends-on: [project-topology]
---

# My Dimension

## Checks

### CHECK-01: Descriptive check name

- **What:** What to verify
- **How:** Commands or agent instructions
- **Pass:** Criteria for PASS
- **Fail:** Criteria for FAIL
- **Severity:** critical | high | medium | low
```

See `references/dimension-format.md` for the full schema and examples.
