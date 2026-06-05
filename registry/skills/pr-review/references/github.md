# GitHub operations — pr-review

> **Part of:** [pr-review](../SKILL.md). The platform-specific commands for authoring a review, keyed by operation name. A GitLab or Azure DevOps port implements the same operations in a sibling reference and dispatches on the PR URL host. (On those platforms the inline-comment posting is typically a small script that maps a findings list to comments on the right file and line.)

## Contents

- [preflight](#preflight)
- [fetch-pr-context](#fetch-pr-context)
- [fetch-existing-comments](#fetch-existing-comments)
- [post-review](#post-review)
- [reply-to-thread](#reply-to-thread)
- [Failure modes](#failure-modes)

## preflight

```sh
gh auth status              # bail with "run gh auth login" if not authed
ME=$(gh api user -q .login) # to detect your own prior review/comments
```

You're reviewing someone else's PR — don't check out the branch or modify files. Read the diff through the API. Clone only if the user explicitly wants something run locally.

## fetch-pr-context

```sh
gh pr view <NUM> --repo <OWNER>/<REPO> --json number,title,author,body,headRefName,baseRefName,additions,deletions,changedFiles,url
gh pr diff <NUM> --repo <OWNER>/<REPO>     # the unified diff under review
```

The diff defines the review surface: comment only on lines this PR added or modified.

## fetch-existing-comments

Run **before** drafting, so you engage prior threads and never repeat a point someone already made. Similar to the pr-comments-address working-set query, but reviewer-oriented — it also pulls `reviews` and omits the author-side `diffHunk`/`originalLine` fields:

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

Use it to skip points already raised, decide which open threads to agree with or push back on, and detect a re-review (a recent review by `$ME` means diff against what changed since `submittedAt`).

## post-review

Post the whole review as **one** PR review — a summary body, inline comments, and a verdict. Build a JSON file from the approved findings, then:

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/reviews --input /tmp/pr-review-<NUM>.json
```

`/tmp/pr-review-<NUM>.json`:

```json
{
  "event": "REQUEST_CHANGES",
  "body": "<summary in house style>",
  "comments": [
    { "path": "src/foo.py", "line": 42, "side": "RIGHT", "body": "<finding>" },
    { "path": "src/bar.py", "start_line": 10, "line": 14, "side": "RIGHT", "body": "<multi-line finding>" }
  ]
}
```

- `event` is the verdict: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT` — the user picks it.
- `line` is the line in the PR's head version (the `RIGHT` side). For a range, set `start_line` and `line`; `start_side` defaults to `side`.
- Posting is atomic: one approved bundle, one call. No drip-posting individual comments.

## reply-to-thread

When your review engages an existing open thread (agree, build on, or push back):

```sh
gh api -X POST repos/<OWNER>/<REPO>/pulls/<NUM>/comments/<FIRST_COMMENT_DB_ID>/replies -f body='<reply>'
```

Don't resolve other people's threads — you're the reviewer, not the author.

## Failure modes

| Symptom | Handling |
|---|---|
| `POST /reviews` 422 "line must be part of the diff" | A comment targets an out-of-range line; move it into the summary body and retry. |
| `POST /reviews` 422 "Can not approve your own pull request" | You're the author; switch the verdict to `COMMENT`. |
| Re-review (a prior review by `$ME` exists) | Comment only on what changed since `submittedAt`; don't re-flag addressed points. |
