---
name: pr-lifecycle
description: >
  Full PR lifecycle: create PRs, monitor review feedback, fix issues, push updates.
  Handles CodeRabbit AI "Prompt for AI Agents" blocks, human reviewer comments,
  and CI check failures. Use when user says "pr review", "create pr", "fix pr",
  "check pr feedback", "address review comments", "pr-lifecycle", or wants to
  manage the PR review cycle.
allowed-tools: Bash, Read, Grep, Glob, Agent, Edit, Write
---

# PR Lifecycle — Create, Fix, Cycle

You manage the full pull request lifecycle: creating PRs, collecting review feedback, fixing issues, and pushing updates. All GitHub operations use the `gh` CLI.

## Arguments

Parse from user message. Three modes:

- **Create**: `/pr-lifecycle create` — create a PR from the current branch
- **Fix**: `/pr-lifecycle fix` or `/pr-lifecycle` (default) — fetch all feedback, evaluate, fix valid items, commit & push
- **Cycle**: `/pr-lifecycle cycle` — create PR if needed, then fix in a loop until clean

Optional flags:
- `--base <branch>` — override base branch (default: `develop`)
- `<PR number>` — target a specific PR (otherwise auto-detect from current branch)

If no mode is recognized, default to **Fix**.

## Setup

Before any mode, resolve these values:

1. **Repo**: `gh repo view --json nameWithOwner -q .nameWithOwner` → `{owner}/{repo}`
2. **Current branch**: `git branch --show-current`
3. **Base branch**: from `--base` flag or default `develop`
4. **PR number** (if needed): from args or `gh pr view --json number -q .number`

---

## Mode: Create

Create a PR from the current branch against the base branch.

### Steps

1. **Verify branch differs from base**
   ```bash
   git log {base}..HEAD --oneline
   ```
   If empty, stop: "No commits ahead of `{base}`. Nothing to create a PR for."

2. **Gather commit info**
   Collect commit subjects from `git log {base}..HEAD --oneline` for the PR description.

3. **Generate PR title**
   Derive a concise PR title from the branch name and commit subjects. Keep it under 70 characters.

4. **Build PR body**
   Check if the repo has a PR template (e.g. `.github/pull_request_template.md`). If found, fill it in using context from the commits. If no template exists, generate a concise body summarizing what changed and why.

5. **Create the PR**
   ```bash
   gh pr create --base {base} --title "{title}" --body "{body}"
   ```

6. **Report** the PR URL to the user.

---

## Mode: Fix (default)

Fetch all feedback, evaluate each item, fix valid issues, commit, and push. This is the default mode.

### Step 1: Gather Feedback

1. **Resolve PR number** (from args or auto-detect)

2. **Check CI status**
   ```bash
   gh pr checks {pr_number}
   ```

3. **Fetch review comments** (inline code comments)
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate
   ```

4. **Fetch general comments** (conversation-level)
   ```bash
   gh api repos/{owner}/{repo}/issues/{pr_number}/comments --paginate
   ```

5. **Fetch review verdicts**
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews --paginate
   ```

6. **Parse CodeRabbit comments**
   Filter comments by user login `coderabbitai[bot]`. Extract actionable items per [resources/coderabbit-parsing.md](resources/coderabbit-parsing.md).

7. **Classify all feedback** per [resources/feedback-types.md](resources/feedback-types.md).

8. **Present summary table**
   ```text
   | # | Source | Type | File:Line | Status | Summary |
   |---|--------|------|-----------|--------|---------|
   | 1 | coderabbit | ai-prompt | app/db.py:15 | pending | Add error handling |
   | 2 | @reviewer | human-comment | app/main.py:42 | pending | Use comprehension |
   | 3 | CI | ci-failure | — | failed | ruff check failed |
   ```
   Group by status: failed CI first, then pending items, then resolved.

If no actionable feedback exists, report "No pending feedback" and stop.

### Step 2: Evaluate and Fix

Process items in priority order (see [resources/feedback-types.md](resources/feedback-types.md)):

**CI failures** (Critical — process first):
- Identify the failed workflow run: `gh run list --branch {branch} -L 5 --json databaseId,status,conclusion`
- Read failed logs: `gh run view {run_id} --log-failed`
- Diagnose the failure from log output
- Fix the code

**CodeRabbit AI prompts** (High):
- Extract "Prompt for AI Agents" content from the comment (see [resources/coderabbit-parsing.md](resources/coderabbit-parsing.md))
- Read the referenced code and evaluate whether the feedback is valid
- If the issue is real, use the extracted content as guidance for the fix
- If the feedback is incorrect, a false positive, or conflicts with project intent, skip it

**Suggestion blocks** (High — both CodeRabbit and human):
- Extract the suggestion content from ` ```suggestion ` blocks
- Review the suggestion against the current code and project context
- Apply only if the suggestion is correct and improves the code
- Skip or adapt if the suggestion would break functionality or misunderstands intent

**Human comments** (High):
- Read the comment and the referenced code
- Evaluate what change is requested and whether it makes sense
- Apply the appropriate code modification if the feedback is valid

**General comments** (Medium):
- Assess whether a code change is needed
- If yes and the feedback is valid, apply the fix
- If purely conversational (praise, acknowledgment) or not applicable, skip

### Step 3: Cleanup, Commit, Push

1. **Post-fix cleanup**
   Run the project's configured linter and formatter (check the project's package manager and tooling config files to determine the correct commands).

2. **Commit and push**
   - Stage only changed files by name (never `git add -A` or `git add .`)
   - Commit with descriptive message:
     ```text
     Address PR review feedback

     - Fix: {description of fix 1}
     - Fix: {description of fix 2}
     - Skip: {description of skipped item} — {reason}
     ```
   - Push to the current branch:
     ```bash
     git push
     ```

3. **Reply to addressed comments**
   For each addressed review comment thread, post a reply:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
     -f body="Fixed in $(git rev-parse --short HEAD)."
   ```
   For general issue comments, reply:
   ```bash
   gh api repos/{owner}/{repo}/issues/{pr_number}/comments \
     -f body="Addressed in $(git rev-parse --short HEAD)."
   ```

4. **Report** what was fixed, what was skipped (with reasoning), and remind the user to re-invoke for the next review round.

---

## Mode: Cycle

Fully automated end-to-end loop: create PR if needed, wait for reviews, fix, push, repeat. No user interaction required after invocation.

### Steps

1. **Check for existing PR** on current branch
   ```bash
   gh pr view --json number 2>/dev/null
   ```
   If no PR exists → run **Create** mode first.

2. **Wait for CodeRabbit review**
   After PR creation or a push, CodeRabbit takes 1-3 minutes to post its review.
   Launch a background poll using Bash with `run_in_background: true`:
   ```bash
   OWNER_REPO="{owner}/{repo}"
   PR={pr_number}
   SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   for i in $(seq 1 20); do
     sleep 30
     # Check for new review comments since our last push
     COUNT=$(gh api "repos/${OWNER_REPO}/pulls/${PR}/comments?since=${SINCE}" -q 'length')
     ISSUE_COUNT=$(gh api "repos/${OWNER_REPO}/issues/${PR}/comments?since=${SINCE}" -q '[.[] | select(.user.login == "coderabbitai[bot]")] | length')
     if [ "$COUNT" -gt 0 ] || [ "$ISSUE_COUNT" -gt 0 ]; then
       echo "NEW_FEEDBACK_DETECTED"
       exit 0
     fi
     # Also check if CodeRabbit check has completed with no inline comments
     CR_STATUS=$(gh pr checks ${PR} 2>&1 | grep -i "CodeRabbit" | awk '{print $2}')
     if [ "$CR_STATUS" = "pass" ]; then
       echo "CODERABBIT_COMPLETE_NO_NEW_COMMENTS"
       exit 0
     fi
   done
   echo "POLL_TIMEOUT"
   exit 1
   ```
   This polls every 30 seconds for up to 10 minutes.
   - Do NOT sleep or poll manually — use `run_in_background` and you will be automatically notified when the task completes.
   - While waiting, do nothing. You will be notified.

3. **Process poll result**
   When the background task completes:
   - `NEW_FEEDBACK_DETECTED` → proceed to Fix mode
   - `CODERABBIT_COMPLETE_NO_NEW_COMMENTS` → report "No new feedback from CodeRabbit" and stop
   - `POLL_TIMEOUT` → report "Timed out waiting for review" and stop

4. **Fix loop**
   a. Run **Fix** mode (gather feedback, evaluate, fix valid items, push)
   b. After push → go back to step 2 (wait for new review on the updated code)
   c. Repeat until no new actionable feedback appears

5. **Report** the final state: PR URL, all feedback addressed, CI status.

### Loop guard
- Maximum 5 fix iterations to prevent infinite loops
- Poll timeout: 10 minutes per wait cycle
- If feedback persists after 5 fix rounds, report remaining items and stop

---

## Constraints

- **Never force-push** — always use regular `git push`
- **Never dismiss reviews** without fixing the underlying issue
- **Always run the project's linter and formatter** before committing
- **Default base branch**: `develop` (override with `--base`)
- **Evaluate before fixing** — never blindly apply feedback. Read the referenced code, assess whether the feedback is valid, and skip items that are false positives or conflict with project intent. Report skipped items with reasoning.
- **Fully automated**: evaluate, fix valid feedback, commit and push without stopping for confirmation
- **Stage specific files** — never use `git add -A` or `git add .`
- **Auto-detect repo** from `gh repo view`
- **Respect PR template** if the repo has one; otherwise generate a concise PR body
