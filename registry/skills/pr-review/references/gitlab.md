# GitLab operations — pr-review (public mode)

> **Part of:** [pr-review](../SKILL.md). The GitLab commands for **public mode** (reviewing a real GitLab merge request), keyed by the same operation names as [github.md](github.md) — so the SKILL workflow stays platform-agnostic and only this file changes. Local mode uses [local.md](local.md) instead and runs none of these — it never invokes `glab` or posts to the platform.

## Terminology

GitLab's model differs from GitHub's in names more than in substance. Throughout the SKILL body, read:

| SKILL says | GitLab means |
|---|---|
| PR, `<NUM>` | merge request (MR), its `iid` (the per-project number in the URL, **not** the global `id`) |
| `<OWNER>/<REPO>` | the project path, possibly nested (`group/subgroup/project`); URL-encoded as `$PROJECT` for API calls |
| pending review draft | the MR's set of **draft notes** — per-author, unpublished, published together |
| review comment thread | **discussion** (`discussion_id`); a top-level comment is a discussion with `individual_note: true` |
| summary body | the `note` passed to `bulk_publish` at submit time |
| verdict | `reviewer_state` on `bulk_publish` (`reviewed` / `requested_changes`), or a separate approve call |

Set these once and reuse them in every recipe below:

```sh
HOST=<host from the MR URL>                              # e.g. gitlab.com, or your self-managed host
export GITLAB_HOST="$HOST"                               # pins every glab call below to the MR's instance
PROJECT=$(printf %s '<GROUP>/<PROJECT>' | jq -sRr @uri)   # nested paths encode to group%2Fsub%2Fproject
IID=<MR_IID>
MR_URL="https://$HOST/<GROUP>/<PROJECT>"                  # -R accepts a full URL; use it for the porcelain
```

**Never name a shell variable `path`.** These recipes pass file paths around, and in zsh — the default shell here — `path` is the array form of `PATH`, tied to it. `local path="src/api/iso.ts"` therefore replaces the command search path with one nonexistent directory, and every external binary disappears for the rest of that function: `command not found: cat`, `: glab`. It reads as a broken environment rather than a naming collision, so the usual reflex — hardcoding `/bin/cat` — fixes the symptom and leaves `glab` still failing. Use `file_path`. Same trap for `cdpath`, `fpath`, `manpath`, and `status`.

**Pin the host explicitly — `glab` never infers it from the MR you were given.** Every `glab` command resolves its instance from the current git remote, `GITLAB_HOST`, or the saved config, so running in a directory whose remote points elsewhere (or nowhere) silently targets the wrong GitLab — and this skill's `preflight` deliberately doesn't clone, so there's often no matching remote at all. `export GITLAB_HOST="$HOST"` covers all of it: `glab api`, `glab auth status`, and the porcelain (`mr view`, `mr diff`, `mr approve`, `mr note`), which have **no `--hostname` flag** — only `-R`. Belt and braces: pass `--hostname "$HOST"` on `glab api`/`glab auth status` and `-R "$MR_URL"` on the porcelain, both shown in the recipes below.

## Transport: glab first, MCP as fallback

**Use `glab`.** Every recipe here is a `glab` command, and `glab api` covers what the porcelain doesn't. Prefer it whenever `glab auth status` succeeds.

**Fall back to a GitLab MCP server only if `glab` is missing or unauthenticated.** Do not hardcode MCP tool names — GitLab MCP servers differ widely in which operations they expose. Instead: list the connected GitLab server's tools, map them onto the operation names in this file, and use the match. Read operations (`fetch-pr-context`, `fetch-existing-comments`) are usually covered; draft notes usually are not.

**Never silently skip an operation with no MCP tool.** If the fallback can't perform an operation, say which one and stop — for `create-draft-review` specifically, that means draft delivery is unavailable and the step 5 gate must be adapted (see `preflight`). A review that posts nothing is a failure the user needs to hear about, not a quiet no-op.

## preflight

```sh
glab auth status --hostname "$HOST"                          # bail with "run glab auth login" if not authed
ME=$(glab api --hostname "$HOST" user | jq -r .username)     # to detect your own prior notes and draft notes
```

(`glab api` has no `--jq` flag — pipe through `jq`. `glab mr view` does have `--jq`.)

You're reviewing someone else's MR — never switch the user's branch or modify project files. The one write allowed in their tree is the skill's own draft artifact in `review/` — that's your output, not the project's code.

**A read-only checkout at MR head is allowed, and step 2 needs one.** The diff alone doesn't let the analysis engines judge a finding against its surrounding code, so put the head commit in a detached worktree outside the user's tree, hand the engines that path, and remove it when the review is delivered:

```sh
git fetch origin "refs/merge-requests/$IID/head:refs/mr/$IID"   # GitLab's MR head refspec
git worktree add --detach <scratch-dir> "refs/mr/$IID"
# … engines read from <scratch-dir> …
git worktree remove --force <scratch-dir> && git update-ref -d "refs/mr/$IID"
```

Nothing here touches the user's branch or working tree, and the worktree is read-only by convention — tell the engines not to edit inside it.

### Draft-notes capability probe — run this here, before any analysis

Unlike GitHub, draft delivery on GitLab can be unavailable on a given instance or token, and the step 5 results gate needs to know **before** it asks the user how to proceed. Probe once:

```sh
glab api "projects/$PROJECT/merge_requests/$IID/draft_notes" >/dev/null 2>&1 && DRAFTS=yes || DRAFTS=no

# The GET above proves only that you can READ. Drafting is a write:
glab api "personal_access_tokens/self" | jq -r '.scopes | join(",")'   # needs `api`; `read_api` is read-only
```

**A passing GET is not a passing POST.** GitLab's `api` scope grants read *and* write, while `read_api` grants read only — so a read-only token sails through the probe and then 403s on the first draft note, after the whole analysis pass has already run. `personal_access_tokens/self` reports the scopes without writing anything; require `api` there rather than inferring write access from the GET. Even then, treat `DRAFTS=yes` as **provisional until the first draft POST succeeds** — and if that POST fails, you're in the `DRAFTS=no` branch below, not in an error state to push past.

If the probe's exit status is ambiguous, re-run with `-i` and read the HTTP status line — a 404 and a 403 mean different things (see Failure modes) and the user can act on the difference.

The Draft Notes API is Free-tier and available on GitLab.com, Self-Managed and Dedicated, so `DRAFTS=yes` is the normal case. `DRAFTS=no` means the endpoint is absent, the token can't write, or an MCP-only fallback with no draft tool.

Carry the result into step 5:

- **`DRAFTS=yes`** — the gate's options are unchanged; delivery creates draft notes the user publishes themselves.
- **`DRAFTS=no`** — **there is no draft delivery on this MR.** Say so in the gate itself and change its options: the only ways to deliver are publishing the discussions now or writing the review to a file and posting nothing. Never present "proceed" as a draft when it would publish — the user is approving publication, and must be told that's what they're approving.

## fetch-pr-context

```sh
glab mr view $IID -R "$MR_URL" -F json --jq '{iid, title, author: .author.username, source_branch, target_branch, web_url}'
glab mr diff $IID -R "$MR_URL"              # the unified diff under review
```

The diff defines the review surface: comment only on lines this MR added or modified.

**Also capture the diff refs now** — every inline comment position needs all three SHAs, and there's no way to anchor a finding without them:

```sh
glab api "projects/$PROJECT/merge_requests/$IID" | jq '.diff_refs'   # {base_sha, start_sha, head_sha}
```

```sh
# Fallback if diff_refs is absent: the newest MR version carries the same three SHAs under different names.
glab api "projects/$PROJECT/merge_requests/$IID/versions" | jq '.[0] | {base_commit_sha, start_commit_sha, head_commit_sha}'
```

Bind them as `BASE_SHA`, `START_SHA`, `HEAD_SHA`. They must come from the MR's **current** head — refetch after any push, or positions will be rejected.

## fetch-existing-comments

Run **before** drafting, so you engage prior threads and never repeat a point someone already made. One paginated call returns every discussion, resolved or not, with the position that anchors it:

```sh
glab api --paginate "projects/$PROJECT/merge_requests/$IID/discussions" | jq -r '
  .[] | . as $d | .notes[0] as $first |
  "\($first.position.new_path // "(no position)"):\($first.position.new_line // "-")  discussion=\($d.id)  resolved=\($first.resolved // false)  \($first.author.username): \($first.body[0:120])"'
```

Each discussion carries `id` (the `<DISCUSSION_ID>` used by `reply-to-thread`), `individual_note`, and `notes[]` with `author.username`, `body`, `created_at`, `resolvable`, `resolved`, and `position`.

Use it to skip points already raised, decide which open threads to agree with or push back on, and detect a re-review. GitLab has **no review object** with a `submittedAt` — a re-review is instead detected from the timestamp of your own most recent published note:

```sh
glab api --paginate "projects/$PROJECT/merge_requests/$IID/notes" \
  | jq -sr --arg me "$ME" 'add | [.[] | select(.author.username==$me)] | max_by(.created_at) | .created_at // "none"'
```

The `jq -s | add` matters: **`glab api --paginate` emits one JSON array per page, not one merged array.** A bare `max_by` therefore reports a "most recent" per page rather than overall — slurp and concatenate before any aggregate.

If that returns a timestamp, diff against what changed since it.

**Your own prior comments are part of this conversation — surface them first.** A pass you (or the user) already made on this MR is the set most easily duplicated, and "existing comments" reads too easily as "other people's / the bot's". Before scanning what anyone else said, list `$ME`'s own notes explicitly:

```sh
glab api --paginate "projects/$PROJECT/merge_requests/$IID/discussions" | jq -r --arg me "$ME" '
  .[] | . as $d | .notes[] | select(.author.username==$me and (.system | not))
  | "\(.position.new_path // "(no position)"):\(.position.new_line // "-")  discussion=\($d.id)  note=\(.id)  \(.body[0:100])"'
```

List these from `/discussions`, not `/notes`. Both return the same notes, but a note object from `/notes` carries **no `discussion_id`** — so a `note=<id>` from there can't be turned into the `<DISCUSSION_ID>` that `reply-to-thread` needs, which is exactly what the next paragraph tells you to do with it.

Treat each as a thread to build on, not a line to re-open: if a finding lands on a `path:line` you already commented on, plan a `reply-to-thread` on that existing discussion rather than a second thread. A prior comment may sit in a **resolved** discussion (the author already fixed it) — resolved still means "already raised", so don't re-flag it; at most acknowledge the fix or add a genuinely new angle as a reply.

Who has already approved is separate from the notes, and worth knowing before you draft a verdict:

```sh
glab api "projects/$PROJECT/merge_requests/$IID/approvals" | jq '{approved: .approved, by: [.approved_by[].user.username]}'
```

## find-pending-review

Draft notes are **per-author** — this returns only your own, and they may be the **user's own hand-written drafts**. Always look before delivering:

```sh
glab api "projects/$PROJECT/merge_requests/$IID/draft_notes" | jq -r '
  .[] | "\(.id)  \(.position.new_path // "(no position)"):\(.position.new_line // "-")  \(.note[0:100])"'
```

**Record the count this returns as `BASELINE`** — `create-draft-review` verifies against it, since your notes are added to whatever is already there.

**Never-destroy rule.** If this returns rows, drafts already exist. Unlike GitHub, GitLab needs no delete-then-recreate — each draft note is created independently, so `create-draft-review` **appends** to the existing set, and an individual note can be revised in place with `update-draft-note` below. That makes destruction unnecessary, and therefore forbidden: never call `DELETE .../draft_notes/<id>` without explicit approval.

Do still tell the user what's already there before appending, and confirm — publishing is all-or-nothing (`bulk_publish` publishes *every* pending draft note, including theirs), so your review can't be submitted without carrying their drafts along with it. If they'd rather not mix the two, let them publish or delete their own drafts first.

## create-draft-review

**Default delivery in public mode** when `DRAFTS=yes`. Each finding is one draft note, unpublished until the user publishes them. Post them one call at a time; GitLab's own docs pass the position as bracketed form fields, which is what `glab api --form` sends:

```sh
glab api -X POST "projects/$PROJECT/merge_requests/$IID/draft_notes" \
  --form 'note=<finding, in house style>' \
  --form 'position[position_type]=text' \
  --form "position[base_sha]=$BASE_SHA" \
  --form "position[start_sha]=$START_SHA" \
  --form "position[head_sha]=$HEAD_SHA" \
  --form 'position[old_path]=src/foo.py' \
  --form 'position[new_path]=src/foo.py' \
  --form 'position[new_line]=42' | jq .id
```

Collect each returned `.id` as you post (`POSTED_IDS="${POSTED_IDS:+$POSTED_IDS,}$NOTE_ID"`) — inline notes only, not the summary note below. The anchoring check scopes to these, so the user's own pre-existing drafts never enter it.

- **`position[...]` must go via `--form`. Sending it with `-f` silently discards it.** `-f/--raw-field` builds a JSON body, and GitLab only reads the bracketed position params form-encoded — so with `-f` the call returns **HTTP 201, exit 0**, and the note lands **unanchored at MR level with `position: null`**. There is no error to catch: it looks like a clean success, and the author sees a top-level comment with no idea which line it refers to. The only way back is deleting and reposting every affected note.
- `new_line` is the line in the MR's head version. For a line that only exists before the change (a deletion), send `position[old_line]` instead; for a line present in both, sending both is safest.
- `old_path` is required even when the file wasn't renamed — set it equal to `new_path`.
- **Multi-line findings degrade to single-line.** GitLab anchors ranges with `position[line_range][start|end][line_code]`, where a line code is a per-file hash the API doesn't hand you directly. Don't fabricate one: anchor the comment at the range's most relevant line and describe the span in the comment text ("lines 10–14 …").

**The summary has no home on a GitLab draft note.** GitHub's pending review carries a `body`; GitLab's draft notes don't. Post the summary as its own **positionless** draft note so the user can see it alongside the inline drafts:

```sh
glab api -X POST "projects/$PROJECT/merge_requests/$IID/draft_notes" \
  --form 'note=<summary + architectural notes, in house style>'
```

`bulk_publish` also accepts a summary at submit time (see below) — but the user, not you, runs the submit, so the positionless draft note is what actually guarantees the summary reaches the MR. Post it here, and still print the verbatim summary in step 7. **Once it exists, don't also pass `note=` to `bulk_publish`** — that would post the same text a second time as a separate summary note.

**Verify anchoring, not just arrival.** A count check can't see the failure above, because the mis-delivered notes are still *there* — just detached. Re-read the notes this run created and assert each has a path and a line anchor — `new_line`, or `old_line` for a comment on a deleted line:

```sh
glab api "projects/$PROJECT/merge_requests/$IID/draft_notes" | jq -r --argjson ids "[$POSTED_IDS]" '
  .[] | select(.id as $id | $ids | index($id))
  | "\(if .position.new_path == null or (.position.new_line == null and .position.old_line == null)
       then "UNANCHORED" else "ok" end)  \(.position.new_path // "-"):\(.position.new_line // .position.old_line // "-")  \(.id)"'
```

Every row must read `ok` — the summary note isn't in `$POSTED_IDS`, so there is no expected `UNANCHORED`. Any `UNANCHORED` row was mis-delivered, and delivery hasn't succeeded until this check is clean: fix it before telling the user anything landed.

After creating, confirm the drafts landed — re-run `find-pending-review` and check the count is `BASELINE + <findings> + 1` for the summary note. It is not equal to what you posted: pre-existing drafts are appended to, never replaced, so comparing against the posted count alone reports a phantom failure for any user who had drafts of their own. Report the count to the user with the MR URL; GitLab shows pending drafts in the MR's **Changes** tab, and publishing is a button there ("Submit review"), or:

```sh
glab api -X POST "projects/$PROJECT/merge_requests/$IID/draft_notes/bulk_publish"
```

## update-draft-note

Revising a draft note you already posted — the user reworded a finding at the gate, or a later round changes the summary. Edit it in place; this is the sanctioned alternative to the delete-and-recreate the never-destroy rule forbids:

```sh
BODY=$(cat <revised-note-file>)
glab api -X PUT "projects/$PROJECT/merge_requests/$IID/draft_notes/<DRAFT_NOTE_ID>" --form "note=$BODY"
```

Ids come from `find-pending-review`. The position is preserved — you're replacing the text, not re-anchoring it. Build the body in a variable rather than inlining it: review prose contains apostrophes, and one of them inside `--form 'note=…'` truncates the note at the quote.

**Amending after delivery still requires the gate.** A user asking for a change approves the *action*, not the wording — print the revised text and get approval before the `PUT`, exactly as at first delivery.

## submit-review

Only when the user explicitly chooses to submit now instead of leaving drafts. `bulk_publish` publishes every pending draft note **and** carries the summary and the verdict:

```sh
glab api -X POST "projects/$PROJECT/merge_requests/$IID/draft_notes/bulk_publish" \
  --form 'reviewer_state=requested_changes'
  # --form 'note=<summary>'   ← ONLY if no positionless summary draft exists; otherwise it double-posts
```

`note=` here creates a summary note *in addition to* publishing the drafts. `create-draft-review` normally already posted the summary as a positionless draft, so passing it again lands the same text twice — include it only when there's no summary draft to publish (the user is submitting their own hand-written drafts, or the summary POST failed).

`reviewer_state` is `reviewed` or `requested_changes` — the sample above is not a fixed verdict; the user picks it, per the SKILL's step 6. Per GitLab's docs it "does not record a formal approval" — approving is a separate call, and it's the one verdict the user must choose explicitly:

```sh
glab mr approve $IID -R "$MR_URL"
```

### The `DRAFTS=no` publish-now path

If `DRAFTS=no` there is nothing to publish, so this operation doesn't apply: the user chose publish-now at the adapted gate and each finding goes up as a **real, immediately visible discussion** (same `--form position[...]` fields as `create-draft-review`, against `.../discussions`, with `body=` in place of `note=`).

That difference matters. Drafts are atomic — the user submits them as one review — but this path is N separate live posts, so a failure halfway leaves the author looking at inline criticism with no summary and no verdict. Run it as a procedure, not a loop:

1. Keep a **posted / remaining** list as you go, and post the findings before the summary.
2. **Stop at the first failure** — don't continue down the list. A partial review is a state to escape, not to extend.
3. Fold every unposted finding **verbatim** into the summary note, so nothing approved at the gate is silently dropped.
4. Post the summary on **both** paths, success and abort, with `BODY=$(cat <summary-file>)` and `glab mr note create $IID -R "$MR_URL" -m "$BODY"` — on the abort path it's what tells the author the review is incomplete and why.
5. Verify the count of posted discussions against the approved set, the same check `create-draft-review` does, and report any shortfall to the user explicitly.

## reply-to-thread

When your review engages an existing discussion (agree, build on, or push back), keep the reply **in the draft set** so it publishes atomically with the rest of the review:

```sh
glab api -X POST "projects/$PROJECT/merge_requests/$IID/draft_notes" \
  --form 'note=<reply>' \
  --form 'in_reply_to_discussion_id=<DISCUSSION_ID>'
```

To reply immediately instead (when there are no drafts to keep it with):

```sh
BODY=$(cat <reply-file>)
glab api -X POST "projects/$PROJECT/merge_requests/$IID/discussions/<DISCUSSION_ID>/notes" -f body="$BODY"
```

Build the body in a variable rather than inlining it — an apostrophe in review prose closes `-f body='…'` early and mangles the call. Note `glab`'s flags are the inverse of `gh`'s here: `-F/--field` expands a leading `@` as a filename, `-f/--raw-field` sends it literally, so `-f body=@file` posts the string `@file`.

Don't resolve other people's discussions — you're the reviewer, not the author. (A draft note can carry `resolve_discussion=true`; don't use it here.)

## Failure modes

| Symptom | Handling |
|---|---|
| `glab auth status` fails | Bail with "run `glab auth login`" — or, for a self-managed host, `glab auth login --hostname <host>`. |
| Draft-notes probe returns 404 | Endpoint absent, wrong project/iid, or a project this token can't see — GitLab returns 404 rather than 403 to avoid leaking existence. Check which before concluding; only the first is genuinely `DRAFTS=no`. Adapt the step 5 gate; never call a publish a draft. |
| Draft-notes probe returns 401/403 | Likely a token without `api` scope (`read_api` reads but cannot write) — confirm with `personal_access_tokens/self` rather than assuming. Say which, so the user can fix it and retry rather than losing the draft path silently. |
| First draft POST 403s after a passing probe | The probe only proved read access. Treat it as `DRAFTS=no`, return to the gate with the publish-now / file-only choice, and don't retry the drafts. |
| `find-pending-review` returns rows | Drafts already exist and may be the user's. Append, never delete — and tell them first, since `bulk_publish` will publish theirs too. |
| Draft/discussion POST 400 "Note position is invalid" | The SHAs are stale or the line isn't in the diff. Refetch `diff_refs` and retry once; if it still fails, move the finding into the summary rather than dropping it. |
| POST returned 201 but the note has `position: null` | The position went out via `-f` instead of `--form` and was discarded — no error is raised. Repost with `--form`; the detached note has to be deleted, so ask the user first. |
| `command not found` for a binary that plainly exists (`cat`, `glab`) | A shell variable named `path` clobbered `PATH` (zsh ties them). Rename it to `file_path` — don't paper over it with absolute binary paths, which leaves every unqualified command still broken. |
| Draft/discussion POST 400 on `line_range` | Multi-line anchoring — degrade to a single-line comment and describe the span in the text. |
| `bulk_publish` rejects `reviewer_state=requested_changes` | Not available on this tier or version. Retry with `reviewed` and put the verdict in the summary text. |
| `glab mr approve` → "cannot approve your own merge request" | You're the author; drop the approve and publish with `reviewer_state=reviewed`. |
| A prior published note by `$ME` exists | Re-review: comment only on what changed since its `created_at`; don't re-flag addressed points. |
| MR `iid` vs `id` confusion (404 on a number that exists) | Every endpoint here takes the **iid** — the number in the MR's URL. |
