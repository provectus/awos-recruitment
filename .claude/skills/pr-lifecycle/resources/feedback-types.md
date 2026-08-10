# Feedback Classification & Handling Rules

How to classify PR feedback items and determine handling priority.

## Classification Matrix

| Type | Source | Priority | Identifier | Handling |
|------|--------|----------|------------|----------|
| `ci-failure` | CI checks | Critical | `gh pr checks` shows failure | Read logs, diagnose, fix code |
| `ai-prompt` | CodeRabbit | High | Comment contains `Prompt for AI Agents` | Use extracted prompt as fix instructions |
| `ai-suggestion` | CodeRabbit | High | Comment contains `` ```suggestion `` block | Apply exact code replacement |
| `human-suggestion` | Reviewer | High | Comment contains `` ```suggestion `` block | Apply exact code replacement |
| `human-comment` | Reviewer | High | Inline review comment on specific code | Analyze comment + code, apply fix |
| `human-general` | Reviewer | Medium | General PR comment (not inline) | Assess if code change needed |

## Priority Order for Fix Mode

Process feedback in this order:

1. **CI failures** — fix these first since broken CI blocks everything
2. **CodeRabbit AI prompts** — precise instructions, quick to apply
3. **Suggestion blocks** (CodeRabbit or human) — exact replacements, apply directly
4. **Human inline comments** — require analysis but are on specific code
5. **Human general comments** — may or may not require code changes

## Handling Rules by Type

### `ci-failure` (Critical)

1. Get the failed run ID from `gh run list`
2. Read logs: `gh run view {run_id} --log-failed`
3. Common failure categories:
   - **Lint/format**: Run the project's linter and formatter to fix style issues
   - **Tests**: Read test output, fix failing test or underlying code
   - **Build/deploy**: Check build config files for syntax errors or misconfigurations
4. Fix the root cause, not just the symptom

### `ai-prompt` (High)

1. Extract the "Prompt for AI Agents" content (see [coderabbit-parsing.md](coderabbit-parsing.md))
2. Read the referenced code and understand the current implementation
3. Evaluate whether the feedback identifies a real issue — the prompt is high-signal guidance but not infallible
4. If valid: apply the fix, using the prompt as guidance
5. If invalid (false positive, conflicts with project intent, or already handled): skip and note why

### `ai-suggestion` / `human-suggestion` (High)

1. Extract code from the `` ```suggestion `` block
2. Identify the target file and line range from the comment metadata
3. Read the current code at that location
4. Evaluate whether the suggestion is correct and improves the code
5. If valid: apply the replacement
6. If the suggestion would break functionality, misunderstands intent, or is unnecessary: skip or adapt

### `human-comment` (High)

1. Read the full comment text
2. Read the referenced code (file + line from the comment metadata)
3. Understand what the reviewer is asking for:
   - **Style change**: Refactor as requested (rename, restructure, simplify)
   - **Bug report**: Fix the identified issue
   - **Missing handling**: Add the requested error handling, edge case, etc.
   - **Question**: If purely a question with no implied change, skip (reply only)
4. Apply the appropriate code modification

### `human-general` (Medium)

1. Read the comment in the context of the overall PR
2. Determine if it implies a code change:
   - **Yes**: Identify what needs to change and apply
   - **No**: Skip (it's conversational — praise, acknowledgment, discussion)
3. Comments like "Can you also add..." or "What about..." typically need action
4. Comments like "LGTM", "Looks good", "Thanks" do not need action

## Skipping Rules

Do NOT attempt to fix:
- Resolved review threads (already addressed)
- Bot status comments ("Review complete", "CI passed")
- Purely conversational comments (praise, acknowledgments)
- Comments that are your own replies from previous fix rounds
- CodeRabbit walkthrough summary (the general issue comment with file tables)

## Status Tracking

When presenting feedback in the summary table, use these statuses:
- `pending` — actionable item not yet addressed
- `fixed` — addressed in the current or a previous fix round
- `skipped` — non-actionable (conversational, resolved, or bot status)
- `failed` — CI check is failing
