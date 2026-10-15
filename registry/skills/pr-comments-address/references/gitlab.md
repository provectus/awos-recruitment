# GitLab operations — pr-comments-address

> **Part of:** [pr-comments-address](../SKILL.md). The GitLab commands for the receiving workflow in **public mode**, keyed by the same operation names as [github.md](github.md) — so the SKILL workflow stays platform-agnostic and only this file changes. Local mode never runs any of these — it stays on the working tree and never invokes `glab` or posts to the platform.

## Contents

- [Terminology](#terminology) — MR/iid/discussion vocabulary, shell setup, the `path` variable trap, host pinning
- [Transport: glab first, MCP as fallback](#transport-glab-first-mcp-as-fallback)
- [preflight](#preflight)
- [checkout-pr](#checkout-pr)
- [fetch-working-set](#fetch-working-set)
- [reply-to-thread](#reply-to-thread)
- [reply-to-top-level](#reply-to-top-level)
- [resolve-thread](#resolve-thread)
- [Failure modes](#failure-modes)

## Terminology

| SKILL says | GitLab means |
|---|---|
| PR, `<NUM>` | merge request (MR), its `iid` (the number in the URL, **not** the global `id`) |
| `<OWNER>/<REPO>` | the project path, possibly nested (`group/subgroup/project`); URL-encoded as `$PROJECT` for API calls |
| review thread | **discussion** (`discussion_id`) |
| top-level comment | a discussion with `individual_note: true` |
| thread is outdated | the note's `position.head_sha` no longer matches the MR head |

```sh
HOST=<host from the MR URL>                              # e.g. gitlab.com, or your self-managed host
export GITLAB_HOST="$HOST"                               # pins every glab call below to the MR's instance
PROJECT=$(printf %s '<GROUP>/<PROJECT>' | jq -sRr @uri)   # nested paths encode to group%2Fsub%2Fproject
IID=<MR_IID>
MR_URL="https://$HOST/<GROUP>/<PROJECT>"                  # -R accepts a full URL; use it for the porcelain
```

**Never name a shell variable `path`.** In zsh — the default shell here — `path` is the array form of `PATH`, tied to it, so `local path="src/api/iso.ts"` wipes out the command search path and every external binary vanishes for the rest of that function (`command not found: cat`, `: glab`). It reads as a broken environment rather than a naming collision. Use `file_path`. Same trap for `cdpath`, `fpath`, `manpath`, and `status`.

**Pin the host explicitly — `glab` never infers it from the MR you were given.** Every `glab` command resolves its instance from the current git remote, `GITLAB_HOST`, or the saved config, so a worktree whose remote points elsewhere silently targets the wrong GitLab. `export GITLAB_HOST="$HOST"` covers `glab api`, `glab auth status`, and the porcelain (`mr checkout`, `mr note`), which have **no `--hostname` flag** — only `-R`.

## Transport: glab first, MCP as fallback

**Use `glab`.** Every recipe here is a `glab` command, and `glab api` covers what the porcelain doesn't. Prefer it whenever `glab auth status` succeeds.

**Fall back to a GitLab MCP server only if `glab` is missing or unauthenticated.** Do not hardcode MCP tool names — GitLab MCP servers differ widely in coverage. List the connected server's tools, map them onto this file's operation names, and use the match. Fetching discussions is usually covered; replying and resolving often are not.

**Never silently skip an operation with no MCP tool.** Say which operation can't run and stop. Half-applied feedback — fixes committed but replies never posted — is worse than not starting, because the reviewer sees silence on threads you actually addressed.

## preflight

```sh
glab auth status --hostname "$HOST"                        # bail with "run glab auth login" if not authed
ME=$(glab api --hostname "$HOST" user | jq -r .username)   # filters "comments not yet replied to by me"
git rev-parse --is-inside-work-tree >/dev/null             # confirm we're in a git repo
glab repo view -F json --jq .web_url                       # host AND path must both match the MR's
```

(`glab api` has no `--jq` flag — pipe through `jq`. `glab repo view` and `glab mr view` do have it.)

Compare `web_url`, not `path_with_namespace`: the path alone is not an identity. `gitlab.com/acme/api` and `gitlab.internal/acme/api` share it, and since the auth check above resolves whatever host `glab` is configured for, a path-only comparison can pass while you're pointed at an entirely different instance's project of the same name. The full URL settles host and path in one check.

If the repo identity doesn't match the MR's project, warn and ask whether to `cd` into the clone or clone fresh. Don't silently `glab repo clone` — it may land in the wrong place.

## checkout-pr

**Already on the MR's source branch?** Then don't create anything — `git pull --ff-only` to the tip and work in place. A worktree only earns its cost when a checkout would otherwise disturb a *different* branch; when you're already on the right one it's just clutter.

**Otherwise, default to an isolated worktree.** Don't switch the current branch in place — the user may have work in progress there. Add a detached worktree, then let `glab mr checkout` set up the MR's source branch inside it (this handles fork remotes and sets tracking, so step 5's `git push` still targets the MR source branch):

```sh
git worktree add --detach <dir>   # <dir> defaults to the sibling ../<repo>-mr-<IID>
cd <dir>
glab mr checkout $IID -R "$MR_URL"   # MR source branch, fork-aware
git pull --ff-only                # move to the tip
```

`<dir>` defaults to the sibling `../<repo>-mr-<IID>`; if the user names a target directory, use that instead. Tell the user the worktree path. Remove it when done (`git worktree remove <path>`) unless they want to keep it.

**In place — only if the user asked** (e.g. they want to review or run it in their main working tree):

```sh
glab mr checkout $IID -R "$MR_URL"
git pull --ff-only
```

If an in-place checkout reports uncommitted changes, stop and tell the user. Don't stash automatically, and never reach for `glab mr checkout --force` — it resets the local branch and discards exactly the work-in-progress you were protecting. Their work outranks this workflow.

## fetch-working-set

One paginated call returns every discussion — diff threads and top-level notes alike:

```sh
glab api --paginate "projects/$PROJECT/merge_requests/$IID/discussions"
```

Each discussion has `id`, `individual_note`, and `notes[]` carrying `id`, `author.username`, `body`, `created_at`, `resolvable`, `resolved`, `system`, and `position` (with `new_path`, `new_line`, `old_line`, and the `head_sha` the note was written against).

A scannable digest of what's still open:

```sh
glab api --paginate "projects/$PROJECT/merge_requests/$IID/discussions" | jq -r --arg me "$ME" '
  .[] | (.notes | map(select(.system != true))) as $notes
  | select($notes | length > 0) | . as $d
  | ($notes | last) as $last | $notes[0] as $first
  | select($last.author.username != $me)
  | "discussion=\($d.id)  \($first.position.new_path // "(top-level)"):\($first.position.new_line // "-")  resolved=\($first.resolved // false)  last=\($last.author.username): \($last.body[0:140])"'
```

Build the working set:

- **Discussions with a position (review threads):** any whose latest note author is not `$ME` — **don't filter on `resolved` alone.** A resolved discussion can mean "fixed" or just "someone replied and closed it without a code change"; the latter still needs handling. Keep the unresolved ones, and also surface resolved ones whose last word isn't yours for a quick judgment — keep the ones you never actually acted on, drop the genuinely handled.
- **Top-level comments** (`individual_note: true`, no position) where the latest author isn't `$ME` and `$ME` hasn't already replied below.
- **Skip system notes** (`system: true`) — those are GitLab's own activity entries ("changed target branch", "added 1 commit"), not feedback. **Filter them out of `notes[]`; never discard a discussion because it contains one.** GitLab appends a system note *inside* a human diff thread whenever the anchored line moves ("changed this line in version N of the diff"), so a whole-discussion test like `select(all(.notes[]; .system | not))` drops exactly the threads that have been through review churn — measured on a real MR, that test kept 11 of 44 live threads and silently lost 33, several with the reviewer's reply as the last word. Filter the notes, then judge the discussion by what remains, as the recipe above does.

**Outdated threads count too** — they still need a reply or resolution. GitLab has no `isOutdated` flag: compare a thread's `position.head_sha` against the MR's current head (`glab api "projects/$PROJECT/merge_requests/$IID" | jq -r .diff_refs.head_sha`). When they differ, the anchored line has moved or vanished — the note's `position` (`old_line` / `new_line` / paths) plus reading the file at `path` is what locates the code the reviewer meant. There is no stored diff hunk to fall back on.

`<DISCUSSION_ID>` for `reply-to-thread` and `resolve-thread` is the discussion's `id` — a hex string, not a number.

## reply-to-thread

```sh
BODY=$(cat <reply-file>)
glab api -X POST "projects/$PROJECT/merge_requests/$IID/discussions/<DISCUSSION_ID>/notes" -f body="$BODY"
```

**Build the body in a variable; don't inline it.** Replies are prose, prose contains apostrophes, and a single `'` inside `-f body='…'` closes the quote and mangles the command. Write the approved reply to a file (or a heredoc) and pass it by variable.

`glab`'s field flags are the **inverse of `gh`'s**: `-F/--field` expands a leading `@` as a filename, `-f/--raw-field` sends the value literally. So `-f body=@reply.md` posts the string `@reply.md`, and `-F body=@reply.md` is what reads the file.

## reply-to-top-level

GitLab models top-level comments as discussions too, so the same endpoint threads a reply underneath one — no quoting workaround needed:

```sh
BODY=$(cat <reply-file>)
glab api -X POST "projects/$PROJECT/merge_requests/$IID/discussions/<DISCUSSION_ID>/notes" -f body="$BODY"
```

To add a fresh top-level comment that isn't a reply to anything:

```sh
BODY=$(cat <comment-file>)
glab mr note create $IID -R "$MR_URL" -m "$BODY"
```

## resolve-thread

```sh
glab api -X PUT "projects/$PROJECT/merge_requests/$IID/discussions/<DISCUSSION_ID>" -F resolved=true
```

Only `resolvable` discussions can be resolved — diff threads are, plain top-level comments are not. If a `dismiss-resolve` item turns out to be an unresolvable top-level note, post the short reply and note in the summary that GitLab has nothing to resolve there.

## Failure modes

| Symptom | Handling |
|---|---|
| `glab auth status` fails | Bail with "run `glab auth login`" — or `glab auth login --hostname <host>` for self-managed. |
| `glab mr checkout` → "would overwrite local changes" | Stop, surface the conflict, let the user decide. Never `--force`. |
| `PUT .../discussions/<id>` → "Discussion cannot be resolved" | Not resolvable (top-level note). Reply only; say so in the summary. |
| `PUT .../discussions/<id>` → already resolved | Fine, continue. |
| Reply → 404 "Discussion Not Found" | Deleted upstream, or an `id` from a different MR. Skip and note it in the summary. |
| Every discussion looks like noise | You're reading system notes — filter `system: true` out. |
| `command not found` for a binary that plainly exists (`cat`, `glab`) | A shell variable named `path` clobbered `PATH` (zsh ties them). Rename it to `file_path` — don't paper over it with absolute binary paths, which leaves every unqualified command still broken. |
| `git push` rejected (non-fast-forward) | Fetch and integrate (rebase or merge, per the project's convention), ask before re-pushing. Never force-push. |
| Push rejected by a protected-branch rule | The MR source branch is protected for your role. Stop and tell the user; don't retry with `--force`. |
| MR `iid` vs `id` confusion (404 on a number that exists) | Every endpoint here takes the **iid** — the number in the MR's URL. |
