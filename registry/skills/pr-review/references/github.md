# GitHub operations — pr-review (public mode)

> **Part of:** [pr-review](../SKILL.md). Operations for **public mode** on GitHub, implemented by the scripts in `../scripts/` (node ≥ 18, `gh` authenticated). Local mode uses [local.md](local.md) and runs none of these. [gitlab.md](gitlab.md) implements the same operation names for GitLab.

You're reviewing someone else's PR — don't check out the branch or modify project files; read the diff through the API. The one write allowed is the skill's own draft artifact in `review/`.

## preflight

```sh
node <skill-dir>/scripts/preflight.js "<pr-ref>"
```

Resolves platform, host, repo, PR number, and `me`. `{ask: true, reason}` (exit 2) means the resolution ladder failed — ask the user, never guess.

## fetch-context

One call replaces `fetch-pr-context` + `fetch-existing-comments`:

```sh
node <skill-dir>/scripts/fetch-context.js --platform github --host <HOST> --repo <OWNER>/<REPO> --pr <NUM> --me <ME> --out <scratch-dir>
```

Writes `context.json` (meta, normalized threads with `resolved`/`mineLast`/`replyTargetId`, top-level comments, `myPriorInline`, `myLastActivityAt`, pending review, policy sections + `prModifiesPolicy`, `draftCapable`) and `diff.patch` — hand agents the diff **path**, not inline text. Read `context.json` selectively; don't re-fetch by hand.

What the data means is still yours to apply:

- **Your own prior comments are part of the conversation — surface `myPriorInline` first.** A finding on a `path:line` you already commented on becomes a reply to that thread, even if the thread is resolved — resolved still means "already raised".
- **`myLastActivityAt` non-null means re-review:** diff against what changed since it; don't re-flag addressed points.
- The diff defines the review surface: comment only on lines this PR added or modified.

## find-pending-review

```sh
node <skill-dir>/scripts/deliver.js find-pending --context <scratch-dir>/context.json
```

**Never-destroy rule.** `pending` non-null means a draft exists and may hold the user's own hand-written comments. REST cannot merge into it, and the only programmatic "replace" is delete-then-recreate — **do neither; stop and ask the user.**

## create-draft-review

Default delivery: one *pending* review (summary + all inline comments, no `event`), which the user submits in the GitHub UI.

```sh
node <skill-dir>/scripts/deliver.js create-draft --context <ctx> --body-file <summary.md> --comments-file <comments.json>
# comments.json: [{"path":"src/foo.py","line":42,"body":"…"}, {"path":"src/bar.py","startLine":10,"line":14,"body":"…"}]
```

The script refuses if a pending review exists (never-destroy), retries nothing silently, and reports `bodyEmpty` — a pending review's summary is invisible in the UI until submit and **cannot be edited in place** if it landed empty; deliver the summary at submit time and always print it verbatim in step 7. A `retryable` error names an out-of-diff comment: move it into the summary body and re-run.

## reply-to-thread

```sh
node <skill-dir>/scripts/deliver.js reply --context <ctx> --thread <id> --body-file <reply.md>
```

While a pending review exists the script routes the reply through it (GraphQL — publishes atomically on submit; a plain REST reply would 422). `--thread` is the thread node id when pending, else the first comment's `replyTargetId` from `context.json`. Don't resolve other people's threads — you're the reviewer, not the author.

## reply-to-top-level / submit-review

```sh
node <skill-dir>/scripts/deliver.js reply-top --context <ctx> --body-file <comment.md>
node <skill-dir>/scripts/deliver.js submit --context <ctx> --event approve|request_changes|comment [--body-file <summary.md>]
```

`submit` only when the user explicitly chose to submit now; the event is the verdict **the user picked**. "Can not approve your own pull request" → switch the verdict to comment.

## Failure modes the scripts hand back to you

| Script result | Handling |
|---|---|
| `neverDestroy: true` | Stop and ask the user — typically they submit or clear their draft first. |
| `retryable` out-of-diff comment | Move that finding into the summary body, re-run create-draft. |
| `bodyEmpty: true` | Deliver the summary via `submit --body-file` or the user pastes it at submit; print it verbatim in step 7 either way. |
| `{ok:false}` anything else | Report it and stop — never improvise past a failed delivery op. |
