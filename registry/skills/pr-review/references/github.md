# GitHub operations — pr-review (public mode)

> **Part of:** [pr-review](../SKILL.md). Platform-specific commands for **public mode** (reviewing a real GitHub PR), keyed by operation name. Local mode uses [local.md](local.md) instead and touches none of this. A GitLab or Azure DevOps port implements the same operations in a sibling reference and dispatches on the PR URL host.

## Contents

- [preflight](#preflight)
- [fetch-pr-context](#fetch-pr-context)
- [fetch-existing-comments](#fetch-existing-comments)
- [find-pending-review](#find-pending-review) — and the never-destroy rule
- [create-draft-review](#create-draft-review) — default delivery
- [submit-review](#submit-review)
- [reply-to-thread](#reply-to-thread)
- [Failure modes](#failure-modes)

## preflight

```sh
gh auth status              # bail with "run gh auth login" if not authed
ME=$(gh api user -q .login) # to detect your own prior review/comments/draft
```

You're reviewing someone else's PR — don't check out the branch or modify files. Read the diff through the API.

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
- After creating, confirm the draft exists and its `body` is non-empty (`find-pending-review` returns an id; GET that review and check `.body`). A silently empty summary is a known failure — verify, don't assume.

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

Don't resolve other people's threads — you're the reviewer, not the author.

## Failure modes

| Symptom | Handling |
|---|---|
| `find-pending-review` returns an id | A draft exists — apply the never-destroy rule above; stop and ask. |
| `POST /reviews` 422 "A review is already pending" | Same — a draft exists; don't force it. Ask the user. |
| `POST /reviews` 422 "line must be part of the diff" | A comment targets an out-of-range line; move it into the summary body and retry. |
| `POST .../events` 422 "Can not approve your own pull request" | You're the author; switch the verdict to `COMMENT`. |
| Re-review (a prior submitted review by `$ME` exists) | Comment only on what changed since `submittedAt`; don't re-flag addressed points. |
