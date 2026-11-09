# gh CLI Commands Reference

Exact commands for each PR lifecycle operation. All commands assume `gh` is authenticated and the current directory is within the repo.

## Repo & Branch Info

```bash
# Get owner/repo
gh repo view --json nameWithOwner -q .nameWithOwner

# Current branch
git branch --show-current

# Commits ahead of base
git log {base}..HEAD --oneline
```

## PR Detection & Creation

```bash
# Check if PR exists for current branch
gh pr view --json number -q .number 2>/dev/null

# Create PR
gh pr create --base {base} --title "{title}" --body "{body}"

# View PR details
gh pr view {pr_number} --json number,title,state,url,headRefName,baseRefName
```

## CI Checks

```bash
# List check status for a PR
gh pr checks {pr_number}

# List recent workflow runs on the branch
gh run list --branch {branch} -L 5 --json databaseId,status,conclusion,name

# Read failed run logs
gh run view {run_id} --log-failed
```

## Review Comments (Inline Code Comments)

```bash
# Fetch all inline review comments (paginated)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate

# Reply to a review comment thread
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
  -f body="{message}"
```

Response fields of interest:
- `id` — comment ID (for replies)
- `user.login` — author (check for `coderabbitai[bot]`)
- `body` — comment text
- `path` — file path
- `line` / `original_line` — line number
- `diff_hunk` — surrounding diff context
- `in_reply_to_id` — parent comment ID (if this is a reply)

## General PR Comments (Issue-Level)

```bash
# Fetch all general comments (paginated)
gh api repos/{owner}/{repo}/issues/{pr_number}/comments --paginate

# Post a general comment
gh api repos/{owner}/{repo}/issues/{pr_number}/comments \
  -f body="{message}"
```

Response fields of interest:
- `id` — comment ID
- `user.login` — author
- `body` — comment text

## Reviews (Approve/Request Changes Verdicts)

```bash
# Fetch all reviews
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews --paginate
```

Response fields of interest:
- `user.login` — reviewer
- `state` — `APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`, `DISMISSED`
- `body` — review summary text

## Resolving Review Threads (GraphQL)

```bash
# Resolve a review thread by thread ID
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "{thread_id}"}) {
      thread { isResolved }
    }
  }
'
```

To get thread IDs, query via GraphQL:
```bash
gh api graphql -f query='
  query {
    repository(owner: "{owner}", name: "{repo}") {
      pullRequest(number: {pr_number}) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            comments(first: 1) {
              nodes { body author { login } }
            }
          }
        }
      }
    }
  }
'
```

## Polling for New Feedback (Cycle Mode)

After creating a PR or pushing fixes, poll for new CodeRabbit review comments.

```bash
# Get current UTC timestamp (use as "since" filter)
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Check for new inline review comments since timestamp
gh api "repos/{owner}/{repo}/pulls/{pr_number}/comments?since=${SINCE}" -q 'length'

# Check for new general comments from CodeRabbit since timestamp
gh api "repos/{owner}/{repo}/issues/{pr_number}/comments?since=${SINCE}" \
  -q '[.[] | select(.user.login == "coderabbitai[bot]")] | length'

# Check CodeRabbit check status
gh pr checks {pr_number} 2>&1 | grep -i "CodeRabbit" | awk '{print $2}'
```

## Useful Filters

```bash
# Filter review comments to only unresolved (not part of a resolved thread)
# There is no direct REST filter — use GraphQL reviewThreads above

# Filter comments by author
# Post-process JSON: jq '.[] | select(.user.login == "coderabbitai[bot]")'
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate \
  -q '.[] | select(.user.login == "coderabbitai[bot]")'
```
