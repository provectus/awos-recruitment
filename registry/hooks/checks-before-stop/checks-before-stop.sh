#!/bin/sh
# checks-before-stop — Stop hook.
# Before Claude finishes, runs the project's lint, type check and tests.
# If one fails, exits 2 so Claude keeps working and gets the tail of the
# output. Runs only when the git working tree changed since the last green
# run, and blocks at most once per turn (stop_hook_active). Fails open on
# anything unexpected: no git, no checks found, malformed input.

[ "${AWOS_STOP_CHECKS:-1}" = "0" ] && exit 0

project="${CLAUDE_PROJECT_DIR:-.}"
input=$(cat 2>/dev/null) || exit 0

# Claude is already continuing because of this hook: let it stop.
printf '%s' "$input" | grep -q '"stop_hook_active" *: *true' && exit 0

cd "$project" 2>/dev/null || exit 0
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# --- fingerprint of the working tree -----------------------------------------
fingerprint() {
  {
    git status --porcelain=v1 --untracked-files=all 2>/dev/null
    git diff HEAD 2>/dev/null || git diff 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null \
      | while IFS= read -r f; do cksum "$f" 2>/dev/null; done
  } | cksum | cut -d' ' -f1
}

# Clean tree: nothing changed, nothing to check.
[ -n "$(git status --porcelain 2>/dev/null)" ] || exit 0

cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/awos-recruitment"
key=$(pwd | cksum | cut -d' ' -f1)
stamp="$cache_dir/$key.checks"
before=$(fingerprint)
[ "$(cat "$stamp" 2>/dev/null)" = "$before" ] && exit 0

# --- find the checks ----------------------------------------------------------
# One command per line. AWOS_STOP_CHECKS_CMD wins over detection.
checks=""
add() { checks="${checks}${checks:+
}$1"; }

if [ -n "${AWOS_STOP_CHECKS_CMD:-}" ]; then
  add "$AWOS_STOP_CHECKS_CMD"
elif [ -f package.json ]; then
  pm=npm
  [ -f pnpm-lock.yaml ] && pm=pnpm
  [ -f yarn.lock ] && pm=yarn
  { [ -f bun.lockb ] || [ -f bun.lock ]; } && pm=bun
  for script in lint typecheck type-check test; do
    line=$(grep -m 1 "\"$script\" *:" package.json) || continue
    # npm init writes a placeholder test script that always fails.
    case "$line" in *"no test specified"*) continue ;; esac
    add "$pm run $script"
  done
elif [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; then
  if [ -x .venv/bin/ruff ] && { [ -f ruff.toml ] || [ -f .ruff.toml ] || grep -q '^\[tool\.ruff' pyproject.toml 2>/dev/null; }; then
    add ".venv/bin/ruff check ."
  fi
  if [ -x .venv/bin/pytest ]; then
    add ".venv/bin/pytest -q"
  fi
fi

[ -n "$checks" ] || exit 0

# --- run them -----------------------------------------------------------------
out=$(mktemp 2>/dev/null) || exit 0
trap 'rm -f "$out"' EXIT
lines="${AWOS_STOP_CHECKS_LINES:-60}"

printf '%s\n' "$checks" | while IFS= read -r cmd; do
  [ -n "$cmd" ] || continue
  if ! CI=1 sh -c "$cmd" > "$out" 2>&1 < /dev/null; then
    {
      echo "Checks failed before finishing: \`$cmd\` exited with an error."
      echo "Fix the problems below, run \`$cmd\` again until it passes, then finish."
      echo "If the failure is not caused by your changes, tell the user instead of changing unrelated code."
      echo "--- last $lines lines of output ---"
      tail -n "$lines" "$out"
    } >&2
    exit 2
  fi
done
status=$?
[ "$status" -eq 2 ] && exit 2

# Green: remember this tree so the next stop does not re-run the checks.
mkdir -p "$cache_dir" 2>/dev/null && fingerprint > "$stamp" 2>/dev/null
exit 0
