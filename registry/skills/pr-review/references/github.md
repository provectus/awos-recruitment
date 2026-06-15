# GitHub operations — pr-review (public mode)

> **Part of:** [pr-review](../SKILL.md). The GitHub commands for **public mode** (reviewing a real GitHub PR), keyed by operation name. Local mode uses [local.md](local.md) instead and runs none of these — it never invokes `gh` or posts to the platform. Keying by operation name keeps the SKILL workflow platform-agnostic, so similar reference files could be added for other review platforms (GitLab, Azure DevOps, …) and selected by the PR URL host if that's ever needed.

## preflight

```sh
gh auth status              # bail with "run gh auth login" if not authed
ME=$(gh api user -q .login) # to detect your own prior review/comments/draft
```

You're reviewing someone else's PR — don't check out the branch or modify project files. Read the diff through the API. (The one write allowed is the skill's own draft artifact in `review/` — that's your output, not the project's code.)

## fetch-pr-context

```sh
gh pr view <NUM> --repo <OWNER>/<REPO> --json number,title,author,body,headRefName,baseRefName,additions,deletions,changedFiles,url
gh pr diff <NUM> --repo <OWNER>/<REPO>     # the unified diff under review
```

The diff defines the review surface: comment only on lines this PR added or modified.

## fetch-existing-comments

Run **before** drafting, so you engage prior threads and never repeat a point someone already made. Reviewer-oriented — pulls `reviews` plus threads and top-level comments:

```sh
gh api graphql -F owner=<OWNER> -F repo=<REPO> -F n=<NUM> -f query='
  query($owner:String!,$repo:String!,$n:Int!){
    repository(owner:$owner,name:$repo){
      pullRequest(number:$n){
        url
        reviews(first:50){ nodes{ author{login} state submittedAt body } }
        reviewThreads(first:100){
          nodes{
            id isResolved path line
            comments(first:50){ nodes{ databaseId author{login} body createdAt url } }
          }
        }
        comments(first:100){ nodes{ databaseId author{login} body createdAt url } }
      }
    }
  }'
```

Use it to skip points already raised, decide which open threads to agree with or push back on, and detect a re-review (a recent submitted review by `$ME` means diff against what changed since `submittedAt`).

**Your own prior comments are part of this conversation — surface them first.** A pass you (or the user) already submitted on this PR is the set most easily duplicated, and "existing comments" reads too easily as "other people's / the bot's". Before scanning what anyone else said, list `$ME`'s own inline review comments explicitly:

```sh
# Your prior inline review comments on this PR — path, line, which review, and a snippet.
gh api repos/<OWNER>/<REPO>/pulls/<NUM>/comments --paginate \
  -q '.[] | select(.user.login=="'"$ME"'") | "\(.path):\(.original_line // .line)  review=\(.pull_request_review_id)  \(.body[0:100])"'
```

Treat each as a thread to build on, not a line to re-open: if a finding lands on a `path:line` you already commented on, plan a `reply-to-thread` on that existing thread rather than a second top-level comment. A prior comment may sit in a **resolved** thread (the author already fixed it) — resolved still means "already raised", so don't re-flag it; at most acknowledge the fix or add a genuinely new angle as a reply. The GraphQL `reviews` nodes carry only each review's summary body; the inline comments live in `reviewThreads` and in the REST listing above — read both.

## find-pending-review

A **pending review** is a draft visible only to its author until submitted. It may contain the **user's own hand-written comments**. Always look for one before delivering:

```sh
gh api repos/<OWNER>/<REPO>/pulls/<NUM>/reviews -q '.[] | select(.user.login=="'"$ME"'" and .state=="PENDING") | .id'
```

**Never-destroy rule.** If this returns a review id, a draft already exists. REST cannot merge new comments into an existing pending review, and the only programmatic "replace" would be delete-then-recreate. **Do not delete it and do not recreate it. Stop and ask the user** how to proceed — typically they submit or clear their draft first, or they approve posting your findings as standalone published review comments instead. Never call `DELETE .../reviews/<id>` without explicit approval.

If it returns nothing, there's no draft and `create-draft-review` is safe.

## create-draft-review

**Default delivery in public mode.** Post the whole review as one *pending* review — a summary body plus all inline comments, **no `event`** so it stays a draft the user finalizes and submits in the GitHub UI. All comments must be included at creation (REST has no add-to-pending endpoint), so build the full approved set first.

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/reviews --input /tmp/pr-review-<NUM>.json
```

`/tmp/pr-review-<NUM>.json` (note: **no `event` key** = pending):

```json
{
  "body": "<summary + architectural notes, in house style>",
  "comments": [
    { "path": "src/foo.py", "line": 42, "side": "RIGHT", "body": "<finding>" },
    { "path": "src/bar.py", "start_line": 10, "line": 14, "side": "RIGHT", "body": "<multi-line finding>" }
  ]
}
```

- `line` is the line in the PR's head version (the `RIGHT` side). For a range, set `start_line` and `line`; `start_side` defaults to `side`.
- **Use this `gh api` recipe, not an MCP github review tool, to create the draft.** The MCP create-pending-review tool has been observed silently dropping the `body` — the draft lands with all inline comments but no summary, and no error.
- After creating, confirm the draft exists and its `body` is non-empty (`find-pending-review` returns an id; GET that review and check `.body`). A silently empty summary is a known failure — verify, don't assume.
- **An empty body cannot be fixed in place.** Both REST and GraphQL refuse to edit a pending review with a missing body ("Could not edit a review with a missing body"). The summary can then only ride along at submit time — via `submit-review`'s `body` field, or pasted by the user into the UI's "Finish your review" box. Don't delete-and-recreate to fix it (never-destroy rule).
- **A pending review's summary body is not shown anywhere in the GitHub UI until the review is submitted** — only the inline draft comments appear (in the Files-changed tab, marked pending). The summary is invisible to everyone, including the user, while the review stays a draft. This is expected GitHub behavior, not a bug; print the verbatim body in the final summary (step 7) so the user can paste it at submit if needed.

## submit-review

Only when the user explicitly chooses to submit now instead of leaving a draft. Submit the pending review (from `create-draft-review` or the user's own) with the verdict:

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/reviews/<REVIEW_ID>/events -f event=REQUEST_CHANGES -f body='<summary>'
```

`event` is the verdict the user picks: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`. To create-and-submit in one call instead, use the `create-draft-review` payload with an added `"event"` field.

## reply-to-thread

When your review engages an existing open thread (agree, build on, or push back):

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/comments/<FIRST_COMMENT_DB_ID>/replies -f body='<reply>'
```

**While your pending review exists, this REST call fails** (422 "user_id can only have one pending review per pull request" — GitHub wraps each standalone reply in its own mini-review). Attach replies to the pending review via GraphQL instead, which also publishes them atomically with the review on submit:

```sh
gh api graphql -f query='mutation { addPullRequestReviewThreadReply(input:{ pullRequestReviewId:"<PENDING_REVIEW_NODE_ID>", pullRequestReviewThreadId:"<THREAD_NODE_ID>", body:"<reply>" }) { comment { url } } }'
```

(Thread node ids come from `fetch-existing-comments`; the pending review's node id from `gh api repos/<OWNER>/<REPO>/pulls/<NUM>/reviews -q '.[] | select(.state=="PENDING") | .node_id'`.)

Don't resolve other people's threads — you're the reviewer, not the author.

## Failure modes

| Symptom | Handling |
|---|---|
| `find-pending-review` returns an id | A draft exists — apply the never-destroy rule above; stop and ask. |
| `POST /reviews` 422 "A review is already pending" | Same — a draft exists; don't force it. Ask the user. |
| `POST /reviews` 422 "line must be part of the diff" | A comment targets an out-of-range line; move it into the summary body and retry. |
| `POST .../events` 422 "Can not approve your own pull request" | You're the author; switch the verdict to `COMMENT`. |
| Pending review exists but its `.body` is empty | Can't be edited in place (REST and GraphQL both refuse). Deliver the summary at submit time instead — `submit-review` with `body`, or the user pastes it in the UI — and always print the verbatim summary in the final message (step 7). |
| Re-review (a prior submitted review by `$ME` exists) | Comment only on what changed since `submittedAt`; don't re-flag addressed points. |
