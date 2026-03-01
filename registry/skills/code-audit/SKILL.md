---
name: code-audit
description: >-
  Audit the codebase across extensible quality dimensions. Use when asked to
  "audit the code", "run a code audit", "check code quality", "audit this
  project", or when the /code-audit command is invoked. Discovers dimension files
  automatically — drop a new .md in the dimensions/ folder to extend.
---

# Code Audit

Extensible, dimension-based code quality audit. Each dimension is a self-contained markdown file with checks and pass/fail criteria.

## How Discovery Works

1. Glob `dimensions/*.md` relative to this SKILL.md
2. Parse YAML frontmatter from each file to get `name`, `title`, `severity`, and `depends-on`
3. Build a dependency DAG from the `depends-on` fields — this determines execution scheduling

No code changes are needed to add a new dimension. Drop a `.md` file in `dimensions/` and it is automatically picked up on the next audit run.

## Execution Model

Dimensions run in a **dependency-aware DAG**. Each dimension declares which other dimensions it `depends-on`. The engine groups dimensions into phases: all dimensions whose dependencies are satisfied run in parallel within a phase.

### Artifact Directory

Before execution begins, create the artifact directory:

```
context/audits/YYYY-MM-DD/
```

If a directory for today already exists, reuse it (results will be overwritten).

### Scheduling Algorithm

1. Parse `depends-on` from every dimension's frontmatter
2. Group into execution phases:
   - **Phase 1:** Dimensions with no `depends-on` (roots of the DAG)
   - **Phase N:** Dimensions whose `depends-on` are all completed in prior phases
3. Within each phase, evaluate all dimensions in parallel

Phases are computed dynamically from the `depends-on` fields declared in each dimension's frontmatter. Adding or removing dimension files automatically updates the execution DAG — no manual phase configuration is needed.

### Per-Dimension Execution

For each dimension in the current phase:

1. Read the dimension file fully
2. Evaluate every check following the **How** instructions and return results in the format: `check-id | PASS / WARN / FAIL / SKIP | one-line evidence`
   - If a check has a **Skip-When** condition, evaluate the condition against available artifacts first
3. Collect results per check
4. **Write the dimension artifact** to `context/audits/YYYY-MM-DD/{name}.md` using the per-dimension artifact format from `references/output-format.md`
5. Once all dimensions in the phase complete, proceed to the next phase

## Scoring Algorithm

Each check produces a status:

| Status | Meaning                           |
| ------ | --------------------------------- |
| PASS   | Check satisfied                   |
| WARN   | Partial compliance or minor issue |
| FAIL   | Check not satisfied               |
| SKIP   | Not applicable to this project    |

Deductions are based on check severity (defined in each dimension file):

| Check Severity | FAIL deduction | WARN deduction |
| -------------- | -------------- | -------------- |
| critical       | 3 pts          | 1.5 pts        |
| high           | 2 pts          | 1 pt           |
| medium         | 1 pt           | 0.5 pts        |
| low            | 0.5 pts        | 0.25 pts       |

### Per-Dimension Score

```
max_points = sum of each check's severity weight (critical=3, high=2, medium=1, low=0.5)
deductions  = sum of FAIL and WARN deductions
raw_score   = max_points - deductions
pct         = (raw_score / max_points) * 100   (clamped to 0–100)
```

Dimensions with `scored: false` do not produce a percentage score — they produce artifacts only.

### Overall Score

```
overall_pct = average of all scored dimension percentages (exclude scored: false)
```

### Grade Scale

| Grade | Range    |
| ----- | -------- |
| A     | 90 – 100 |
| B     | 75 – 89  |
| C     | 60 – 74  |
| D     | 40 – 59  |
| F     | 0 – 39   |

## Previous-Audit Comparison

Before starting execution:

1. Scan `context/audits/` for previous audit directories (date-named folders)
2. If a previous audit exists, read its `report.md` to extract per-dimension scores
3. After scoring the current audit, compute deltas per dimension
4. Include delta column in the summary table and note significant changes

## Output

After all dimensions complete:

1. Compile the full report using `references/output-format.md` as the template
2. **Write the report** to `context/audits/YYYY-MM-DD/report.md`
3. **Write recommendations** to `context/audits/YYYY-MM-DD/recommendations.md`
4. Present the full report to the user
5. **Ask the user** whether they would like an HTML version of the report. If yes, generate `context/audits/YYYY-MM-DD/report.html` — a single self-contained HTML file (inline CSS, no external dependencies) that renders the full audit results: overall score and grade, per-dimension summary table, detailed checklists, and recommendations. Use the `references/report-template.md` specification for structure and styling.

The report includes:

1. Overall score and grade (with delta if previous audit exists)
2. Per-dimension summary table (with deltas)
3. Per-dimension detailed checklists
4. Top recommendations sorted by priority and effort

## Adding New Dimensions

See `references/dimension-format.md` for the schema and examples. Requirements:
- A `.md` file in `dimensions/` with valid YAML frontmatter
- A `depends-on` field listing dimension names that must complete first (omit if no dependencies)
