#!/bin/sh
# docs-that-work-gate.sh — Claude Code PreToolUse hook entrypoint.
#
# Gates `git commit` on documentation freshness. When the pending changes
# touch directories owned by a CLAUDE.md or README.md that was NOT itself
# updated, the commit is blocked (exit 2) and the stderr message instructs
# Claude to refresh those docs with the docs-that-work skill, stage them,
# and retry. Hooks cannot invoke skills directly — the block reason fed back
# to Claude is the trigger; Claude does the documentation work. When the
# skill is not installed in the project, the message instructs installing it
# first (the reference would otherwise be a dead pointer).
#
# Ownership rule: each changed file belongs to the NEAREST ancestor directory
# containing CLAUDE.md or README.md. Repo-root docs only own files that sit
# at the root itself, so a root README does not tax every commit.
#
# Loop prevention (worst case two blocks per commit, never a deadlock):
#   1. A doc file with pending changes counts as fresh — once Claude updates
#      it, the retried commit passes.
#   2. On block, a checksum of `git status --porcelain` is stored in
#      .git/docs-that-work-gate.ok. A retry with an unchanged tree passes —
#      this is how "the docs are already accurate" is acknowledged.
#   3. Change sets consisting only of CLAUDE.md/README.md files always pass.
#
# Pure POSIX sh + git. Anything unexpected (not a repo, no pending changes,
# non-commit command, unreadable payload) fails open with exit 0.

set -eu

input=$(cat)

# Only gate commit commands. The payload is the raw tool-call JSON; a
# substring scan is enough here (a command merely mentioning "git commit"
# false-positives into the precise checks below, which is harmless).
printf '%s' "$input" | grep -qE 'git([[:space:]]+-[^[:space:]]+)*[[:space:]]+commit' || exit 0

top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$top" || exit 0
git_dir=$(git rev-parse --git-dir 2>/dev/null) || exit 0

# Pending changes: staged + unstaged + untracked. The hook fires BEFORE the
# whole Bash command runs, so in `git add -A && git commit` nothing is staged
# yet — the index alone cannot be trusted. Porcelain paths are repo-root
# relative; rename entries take the new path; surrounding quotes stripped.
status=$(git status --porcelain 2>/dev/null) || exit 0
[ -n "$status" ] || exit 0

changed=$(printf '%s\n' "$status" \
    | sed -e 's/^...//' -e 's/^.* -> //' -e 's/^"\(.*\)"$/\1/')

# Change sets that are purely documentation always pass (loop-breaker 3).
non_doc=$(printf '%s\n' "$changed" | grep -vE '(^|/)(CLAUDE|README)\.md$' || true)
[ -n "$non_doc" ] || exit 0

# Loop-breaker 2: an unchanged retry after a block passes. The checksum
# covers the porcelain status AND the tracked-content diff, so editing any
# file between attempts invalidates the acknowledgement.
marker="$git_dir/docs-that-work-gate.ok"
checksum=$({ printf '%s' "$status"; git diff HEAD --no-color 2>/dev/null || true; } | cksum)
if [ -f "$marker" ] && [ "$(cat "$marker")" = "$checksum" ]; then
    rm -f "$marker"
    exit 0
fi

fresh_docs=$(printf '%s\n' "$changed" | grep -E '(^|/)(CLAUDE|README)\.md$' || true)

is_fresh() {
    printf '%s\n' "$fresh_docs" | grep -qFx "$1"
}

stale=""
old_ifs=$IFS
IFS='
'
for f in $non_doc; do
    dir=$(dirname "$f")
    while :; do
        if [ "$dir" = "." ]; then
            # Root docs only own files that sit at the root itself.
            case "$f" in */*) break ;; esac
        fi
        owner_found=""
        for doc in CLAUDE.md README.md; do
            if [ "$dir" = "." ]; then p="$doc"; else p="$dir/$doc"; fi
            if [ -f "$p" ]; then
                owner_found="yes"
                if ! is_fresh "$p" && ! printf '%s\n' "$stale" | grep -qFx "$p"; then
                    stale="$stale$p
"
                fi
            fi
        done
        [ -z "$owner_found" ] || break
        [ "$dir" != "." ] || break
        dir=$(dirname "$dir")
    done
done
IFS=$old_ifs

if [ -z "$stale" ]; then
    rm -f "$marker"
    exit 0
fi

printf '%s' "$checksum" > "$marker"

{
    echo "docs-that-work-gate: commit blocked — documentation may be stale."
    echo "The pending changes touch directories whose documentation was not updated:"
    printf '%s' "$stale" | sed 's/^/  - /'
    if [ -d ".claude/skills/docs-that-work" ]; then
        echo "You MUST invoke the docs-that-work skill (Skill tool) to review these files against the pending changes — do not update them from memory. Update what is stale, stage the doc updates, and re-run the commit."
    else
        echo "Install the paired docs-that-work skill first: npx @provectusinc/awos-recruitment skill docs-that-work"
        echo "Then invoke it (Skill tool) to review these files against the pending changes — do not update them from memory. Update what is stale, stage the doc updates, and re-run the commit."
    fi
    echo "If the documentation is already accurate, re-run the same commit unchanged — the gate remembers this review and will let it pass."
} >&2
exit 2
