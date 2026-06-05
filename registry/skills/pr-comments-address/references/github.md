# GitHub operations — pr-comments-address

> **Part of:** [pr-comments-address](../SKILL.md). The platform-specific commands for the receiving workflow, keyed by operation name. A GitLab or Azure DevOps port implements the same operations in a sibling reference and dispatches on the PR URL host.

## Contents

- [preflight](#preflight)
- [checkout-pr](#checkout-pr)
- [fetch-working-set](#fetch-working-set)
- [reply-to-thread](#reply-to-thread)
- [reply-to-top-level](#reply-to-top-level)
- [resolve-thread](#resolve-thread)
- [Failure modes](#failure-modes)

## preflight

```sh
gh auth status                                  # bail with "run gh auth login" if not authed
ME=$(gh api user -q .login)                     # filters "comments not yet replied to by me"
git rev-parse --is-inside-work-tree >/dev/null  # confirm we're in a git repo
gh repo view --json nameWithOwner -q .nameWithOwner   # must equal OWNER/REPO
```

If the repo identity doesn't match `OWNER/REPO`, warn and ask whether to `cd` into the clone or clone fresh. Don't silently `gh repo clone` — it may land in the wrong place.

## checkout-pr

```sh
gh pr checkout <NUM>     # creates/switches to the PR's head branch
git pull --ff-only       # move to the tip
```

If checkout reports uncommitted changes, stop and tell the user. Don't stash automatically — their work-in-progress outranks this workflow.

## fetch-working-set

One GraphQL call returns unresolved review threads and top-level comments:

```sh
gh api graphql -F owner=<OWNER> -F repo=<REPO> -F n=<NUM> -f query='
  query($owner:String!,$repo:String!,$n:Int!){
    repository(owner:$owner,name:$repo){
      pullRequest(number:$n){
        url headRefName
        reviewThreads(first:100){
          nodes{
            id isResolved isOutdated path line
            comments(first:50){ nodes{ databaseId author{login} body createdAt url diffHunk originalLine } }
          }
        }
        comments(first:100){ nodes{ databaseId author{login} body createdAt url } }
      }
    }
  }'
```

Build the working set:

- **Review threads** where `isResolved == false` and the latest comment author is not `$ME`. Outdated threads count too — they still need a reply or resolution.
- **Top-level comments** where the latest author in the conversation is not `$ME` and `$ME` hasn't already replied below. GitHub doesn't thread these; group by author block and consecutive timestamps.

`<THREAD_NODE_ID>` for `resolve-thread` is the thread `id`. `<COMMENT_DB_ID>` for `reply-to-thread` is the `databaseId` of the thread's **first** comment.

## reply-to-thread

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/comments/<COMMENT_DB_ID>/replies -f body='<reply>'
```

## reply-to-top-level

Top-level comments have no reply API — post a new top-level comment that quotes or links the original:

```sh
gh pr comment <NUM> --body '<reply including a link to the original comment>'
```

## resolve-thread

```sh
gh api graphql -F id=<THREAD_NODE_ID> -f query='
  mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{ isResolved } } }'
```

## Failure modes

| Symptom | Handling |
|---|---|
| `gh pr checkout` → "checkout would overwrite local changes" | Stop, surface the conflict, let the user decide. |
| `resolveReviewThread` → "thread already resolved" | Fine, continue. |
| Reply API → 422 "review thread not found" | The comment was deleted upstream; skip and note it in the summary. |
| `git push` rejected (non-fast-forward) | Fetch, rebase, ask before re-pushing. Never force-push. |
