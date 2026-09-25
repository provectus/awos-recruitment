# GitLab operations — pr-review (public mode)

> **Part of:** [pr-review](../SKILL.md). The same operation names as [github.md](github.md), implemented for GitLab by the scripts in `../scripts/` (node ≥ 18, `glab` authenticated). The scripts pin the host (`GITLAB_HOST` + `--hostname`) on every call, send positions form-encoded, and slurp paginated pages — the historical failure classes of hand-written `glab` choreography. Local mode uses [local.md](local.md) and runs none of these.

## Terminology

Read the SKILL's "PR"/`<NUM>` as merge request / its **iid** (the number in the URL, never the global `id`); a review thread is a **discussion**; the pending review draft is the MR's set of **draft notes** — per-author, unpublished, published together.

## preflight

```sh
node <skill-dir>/scripts/preflight.js "<mr-url>"
```

`{ask: true}` → ask the user; never guess the instance.

**A read-only checkout at MR head is allowed, and step 2 needs one** — the diff alone doesn't let engines judge findings against surrounding code:

```sh
git fetch origin "refs/merge-requests/$IID/head:refs/mr/$IID"
git worktree add --detach <scratch-dir> "refs/mr/$IID"
# … engines read from <scratch-dir>; remove it after delivery:
git worktree remove --force <scratch-dir> && git update-ref -d "refs/mr/$IID"
```

Never switch the user's branch or modify project files; tell the engines the worktree is read-only.

## fetch-context

```sh
node <skill-dir>/scripts/fetch-context.js --platform gitlab --host <HOST> --repo <GROUP>/<PROJECT> --pr <IID> --me <ME> --out <scratch-dir>
```

Same normalized `context.json` + `diff.patch` as GitHub, plus GitLab-specific fields: `diffRefs` (the three SHAs every inline position needs — from the MR's **current** head; re-run after any push or positions get rejected) and the draft-notes capability probe.

- **`draftCapable` is provisional until the first draft POST succeeds** — the GET proves read, and only the `api` token scope writes (`read_api` sails through the probe and 403s on the first note). `draftCapabilityNote` says which case you're in. A first-POST 403 puts you on the Delivery paths no-draft rows, not in an error to push past.
- `myPriorInline` / `myLastActivityAt` / re-review semantics: exactly as in [github.md](github.md).

## find-pending-review

```sh
node <skill-dir>/scripts/deliver.js find-pending --context <ctx>
```

Draft notes are per-author; rows may be the **user's own hand-written drafts**. **Never-destroy:** GitLab appends — new notes join the existing set, and a note is revised in place with `update-draft-note`, so deletion is never needed and therefore forbidden. Before appending, tell the user what's already there and confirm: publishing is all-or-nothing (`bulk_publish` publishes **their** drafts too).

## create-draft-review

```sh
node <skill-dir>/scripts/deliver.js create-draft --context <ctx> --body-file <summary.md> --comments-file <comments.json>
# comments.json: [{"path":"src/foo.py","line":42,"body":"…"}]  — oldLine instead of line for a deleted-line comment
```

The script posts one draft note per finding (positions form-encoded with the `diffRefs` SHAs), tracks every returned id, posts the summary as a **positionless** draft note (GitLab drafts have no review body — this is what guarantees the summary reaches the MR), and then **verifies anchoring**: every posted id must come back with a path and a line. `ok: false` on the anchoring report means delivery has NOT succeeded — fix before telling the user anything landed. Multi-line findings anchor at the most relevant single line; describe the span in the text.

Because the summary already exists as a draft note, **never also pass a summary to `submit`** — it would double-post.

## update-draft-note

```sh
node <skill-dir>/scripts/deliver.js update-draft-note --context <ctx> --id <DRAFT_NOTE_ID> --body-file <revised.md>
```

The sanctioned alternative to delete-and-recreate; position is preserved. Amending after delivery still re-enters the step 5 gate first.

## submit-review

```sh
node <skill-dir>/scripts/deliver.js submit --context <ctx> --event approve|request_changes|comment
```

Only when the user explicitly chose to submit now. `bulk_publish` publishes every pending draft note; `request_changes`/`comment` map to `reviewer_state` (with a plain-publish retry where the instance rejects it), and `approve` additionally runs the separate approval call — the one verdict the user must choose explicitly.

## The no-draft publish-now path

When the user picked **Publish now** at the gate (Delivery paths):

```sh
node <skill-dir>/scripts/deliver.js publish-now --context <ctx> --body-file <summary.md> --comments-file <comments.json>
```

Each finding goes up as a real, immediately visible discussion; the script **stops at the first failure** and returns `posted`/`remaining`. On an abort, fold every `remaining` finding **verbatim** into the summary, then post it with `reply-top` — on both paths the summary posts, and on the abort path it's what tells the author the review is incomplete and why. Verify the posted count against the approved set and report any shortfall.

## reply-to-thread / reply-to-top-level

```sh
node <skill-dir>/scripts/deliver.js reply --context <ctx> --thread <DISCUSSION_ID> --body-file <reply.md>          # joins the draft set
node <skill-dir>/scripts/deliver.js reply --context <ctx> --thread <DISCUSSION_ID> --body-file <reply.md> --immediate
node <skill-dir>/scripts/deliver.js reply-top --context <ctx> --body-file <comment.md>
```

Default keeps replies in the draft set so they publish atomically with the review. Don't resolve other people's discussions.

## Failure modes the scripts hand back to you

| Script result | Handling |
|---|---|
| Draft probe unreadable (404) | Endpoint absent, wrong project/iid, or invisible to this token — GitLab 404s instead of 403 to avoid leaking existence. Only the first is genuinely no-draft; check before adapting the gate. |
| `read_api` scope in `draftCapabilityNote` | Say so — the user can fix the token and retry rather than losing the draft path silently. |
| First draft POST 403 after a passing probe | You're on the no-draft Delivery paths rows now; don't retry drafts. |
| "Note position is invalid" (400) | Stale SHAs or a line outside the diff — re-run fetch-context, retry once; then move the finding into the summary rather than dropping it. |
| Anchoring report not all `ok` | Delivery failed; a detached note has to be deleted, so ask the user first. |
| `bulk_publish` rejects `reviewer_state` | The script retries plain publish; put the verdict in the summary text. |
| "cannot approve your own merge request" | Drop the approve; publish with the reviewed state. |
| 404 on a number that plainly exists | You used the global `id`; every endpoint takes the **iid**. |
