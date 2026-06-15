# Local operations — pr-review (local mode)

> **Part of:** [pr-review](../SKILL.md). **Local mode** reviews your own working branch for yourself and writes the review to a file — it posts nothing to GitHub, GitLab, or any review platform. Use this when the request says "locally", "for myself", "just my branch", "don't post", or otherwise targets your own in-progress work rather than someone else's PR.

## resolve-base

Determine what to diff against. Prefer an explicit base from the user; otherwise default to the repo's default branch.

```sh
git rev-parse --abbrev-ref HEAD                                   # BRANCH
git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p' # default branch, e.g. main
```

Use `origin/<default>` as `BASE` if it exists, else the local default branch. Confirm `BASE` with the user if it's ambiguous (e.g. no remote, detached HEAD).

## get-local-diff

The review surface is the local change set — committed and, if the user wants, uncommitted:

```sh
git diff <BASE>...HEAD --stat     # changed files overview
git diff <BASE>...HEAD            # committed diff under review
git log <BASE>..HEAD --oneline    # commit history for context
git diff                          # add uncommitted changes if the user is mid-work
```

Read the changed files for full context as needed. This is the same surface the analysis engines consume — they review a diff regardless of whether it came from a PR or a local branch.

## write-review-file

Local mode produces a durable artifact, not a platform post. After the user approves at the results gate, write the review to a file and print a short summary pointing to it.

```sh
date -u +%Y-%m-%dT%H:%M:%SZ       # TIMESTAMP
mkdir -p review                   # gitignored or committed per the user's preference
```

Write to `review/<TIMESTAMP>_<BRANCH>.md` (replace any `/` in `BRANCH` with `-`). Use the same house style as a posted review — summary, architectural notes, then findings as `-` bullets or prose with `path:line` references. Avoid numbered lists so the user can delete items without renumbering.

```markdown
# Review: <BRANCH>  (base: <BASE>)

## Summary
<one or two paragraphs: what changed, overall read, headline concerns>

## Architectural notes
- <cross-cutting observations not tied to a single line>

## Findings
- `src/foo.py:42` — <finding in house voice>
- `src/bar.py:10-14` — <finding>
```

Print the file path and the headline counts. The file is the deliverable; the user edits it, hands it to `pr-comments-address` (local mode) to apply fixes, or pushes and opens a PR themselves. Nothing is sent anywhere.
