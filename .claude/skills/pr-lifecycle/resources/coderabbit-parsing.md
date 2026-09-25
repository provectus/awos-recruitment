# CodeRabbit Comment Parsing

How to identify, parse, and extract actionable content from CodeRabbit review comments.

## Identifying CodeRabbit Comments

Filter by user login: `coderabbitai[bot]`

CodeRabbit posts two types of comments:
1. **General comment** (issue-level) — the walkthrough summary posted once per review
2. **Inline review comments** — file-specific feedback on individual lines

## General Comment Structure (Walkthrough)

The walkthrough comment is posted as an issue comment. It contains:

- **Walkthrough**: High-level summary of all changes — not actionable, skip
- **Changes**: Table of files and their change summaries — not actionable, skip
- **Sequence Diagram** (optional): Visual flow — not actionable, skip
- **Assessment against linked issues** (optional): How changes map to issue requirements — informational, skip

**These general walkthrough comments are never actionable.** Do not attempt to "fix" anything from them.

## Inline Review Comment Structure

Inline comments are posted as pull request review comments on specific files/lines. These are the actionable items.

Each inline comment may contain:

### 1. Prompt for AI Agents (Primary — highest value)

Look for an HTML `<details>` block with this pattern:

```
<details>
<summary>Prompt for AI Agents</summary>

{actionable instructions here}

</details>
```

The content between `</summary>` and `</details>` contains precise, machine-readable instructions. **Use this as the primary fix instruction** — it is specifically written for AI agents and contains exact file paths, line numbers, and what to change.

### 2. Suggestion Blocks

Look for fenced code blocks with the `suggestion` language tag:

````
```suggestion
{replacement code}
```
````

These are exact code replacements. Apply them to the file and line range specified in the comment's `path` and `line`/`original_line` fields.

### 3. Plain Text Feedback

The comment body outside of the above blocks contains human-readable explanation. Use this for context but prefer the "Prompt for AI Agents" block when available.

## Extraction Algorithm

For each CodeRabbit inline comment:

1. **Check for "Prompt for AI Agents"**:
   - Search for `Prompt for AI Agents` in the body
   - If found, extract content between `</summary>` and `</details>`
   - Classify as `ai-prompt` type
   - Use extracted content as fix instructions

2. **Check for suggestion blocks**:
   - Search for `` ```suggestion `` in the body
   - If found, extract the code between the fences
   - Classify as `ai-suggestion` type
   - Apply as direct code replacement at the specified file:line

3. **Plain feedback**:
   - If neither of the above, treat as a general comment
   - Classify based on content (bug report, style suggestion, question, etc.)
   - Analyze the comment text + referenced code to determine the fix

## Filtering Non-Actionable Content

Skip these CodeRabbit outputs entirely:
- The walkthrough summary comment (general issue comment with "Walkthrough" heading)
- Lines that are purely praise ("Great job", "LGTM", "Looks good")
- Status update comments ("Finished review", "Review complete")
- Comments that are replies/acknowledgments to human responses

## Example: Extracting from a Real Comment

Given a comment body like:
```text
There's a potential `None` reference on line 42. The `user` variable
could be `None` if the query returns no results.

<details>
<summary>Prompt for AI Agents</summary>

In `app/services/user_service.py` at line 42, add a None check for the
`user` variable before accessing its attributes. Replace:
  result = user.name
With:
  result = user.name if user else "Unknown"

</details>
```

Extract:
- **Type**: `ai-prompt`
- **File**: `app/services/user_service.py`
- **Line**: 42
- **Instructions**: The full content from the Prompt for AI Agents block
