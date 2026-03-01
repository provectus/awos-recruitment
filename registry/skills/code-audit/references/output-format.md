# Audit Report Format

Use this template when presenting audit results. Replace placeholders with actual values.

---

## Artifact Storage

Each audit run persists results to disk for historical comparison:

```
context/audits/YYYY-MM-DD/
├── {name}.md                    ← per-dimension artifact (one per dimension)
├── report.md                    ← full audit report
├── recommendations.md           ← actionable items
└── report.html                  ← standalone HTML report (optional)
```

Example: a dimension with `name: documentation` produces `documentation.md`.

### Per-Dimension Artifact Format

Each dimension artifact (`{name}.md`) contains:

```markdown
# {Dimension Title} — Audit Results

**Date:** YYYY-MM-DD
**Score:** XX% — Grade **X**

## Results

| # | Check | Severity | Status | Evidence |
|---|-------|----------|--------|----------|
| 1 | What  | critical | PASS   | proof    |

## {Dimension-Specific Summary}

(Structured data for downstream dimensions to consume.
E.g., Topology Summary with detected layers, languages, structure type.)
```

---

## Report Template

Write the full report to `context/audits/YYYY-MM-DD/report.md` and also display it to the user.

```markdown
# Code Audit Report

**Date:** YYYY-MM-DD
**Scope:** [all dimensions | single dimension name]
**Overall Score:** XX% — Grade **X**
**Previous Audit:** [YYYY-MM-DD — XX% Grade X | none]

## Summary

| # | Dimension | Score | Grade | Delta | Critical | High | Medium | Low |
|---|-----------|-------|-------|-------|----------|------|--------|-----|
| 1 | Name      | XX%   | X     | +/-N  | 0        | 0    | 0      | 0   |
| … | …         | …     | …     | …     | …        | …    | …      | …   |


## Dimension: [Name]

**Score:** XX% — Grade **X**

| # | Check | Severity | Status | Evidence |
|---|-------|----------|--------|----------|
| 1 | What the check verifies | critical | PASS | one-line proof |
| 2 | What the check verifies | high     | FAIL | what's missing |
| 3 | What the check verifies | medium   | WARN | partial issue  |
| 4 | What the check verifies | low      | SKIP | not applicable |

(Repeat the dimension section for each dimension that was executed.)

## Top Recommendations

| # | Priority | Effort | Dimension | Recommendation |
|---|----------|--------|-----------|----------------|
| 1 | P0       | Low    | Name      | What to fix and why |
| 2 | P0       | Medium | Name      | What to fix and why |
| 3 | P1       | Low    | Name      | What to fix and why |
| 4 | P1       | High   | Name      | What to fix and why |
| 5 | P2       | Low    | Name      | What to fix and why |

Sort by priority (P0 first), then by effort (Low first).
Limit to the top 10 most impactful recommendations.
```

---

## Recommendations File

Write actionable recommendations to `context/audits/YYYY-MM-DD/recommendations.md`:

```markdown
# Audit Recommendations — YYYY-MM-DD

## P0 — Fix Immediately

### 1. [Short title]
- **Dimension:** [Name]
- **Check:** [CHECK-ID]
- **Effort:** Low | Medium | High
- **Details:** What exactly needs to be done, with file paths or commands where possible

## P1 — Fix Soon

### 2. [Short title]
…

## P2 — Improve When Possible

### 3. [Short title]
…
```

Priority mapping:
- **P0:** Critical severity FAILs
- **P1:** High severity FAILs + Critical WARNs
- **P2:** Medium/Low FAILs + High/Medium WARNs

---

## Delta Comparison

When a previous audit exists in `context/audits/`, compare scores:

1. Find the most recent prior audit directory (by date)
2. Read its `report.md` to extract per-dimension scores
3. Calculate delta for each dimension: `current_score - previous_score`
4. Show delta in the Summary table (`+5`, `-3`, `=` for no change)
5. Add a comparison note at the top if overall score changed significantly (>5 points)

---

## Status Icons (optional)

When presenting inline, you may use these markers:

| Status | Marker |
|--------|--------|
| PASS   | PASS   |
| WARN   | WARN   |
| FAIL   | FAIL   |
| SKIP   | SKIP   |

## Scoring Reference

See SKILL.md for the full scoring algorithm. Quick reference:

- **critical** checks: 3 pts max, FAIL = -3, WARN = -1.5
- **high** checks: 2 pts max, FAIL = -2, WARN = -1
- **medium** checks: 1 pt max, FAIL = -1, WARN = -0.5
- **low** checks: 0.5 pts max, FAIL = -0.5, WARN = -0.25
- PASS and SKIP incur no deductions
- Dimension % = (max - deductions) / max * 100
- Overall % = average of all dimension percentages
