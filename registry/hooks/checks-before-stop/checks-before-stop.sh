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

# Prints "name<TAB>command" for each entry of the top-level "scripts" object
# of package.json. Reads only that object: keys with the same names in other
# objects ("directories": {"test": ...}, Nx targets, tool settings) do not
# count. Tracks strings and escapes, so a brace inside a command such as
# "eslint 'src/**/*.{ts,tsx}'" does not end the object early.
package_scripts() {
  awk '
    { buf = buf $0 "\n" }
    END {
      n = length(buf); depth = 0; ins = 0; esc = 0; want = 0; inscripts = 0; havekey = 0
      for (i = 1; i <= n; i++) {
        c = substr(buf, i, 1)
        if (ins) {
          if (esc) { esc = 0; s = s c; continue }
          if (c == "\\") { esc = 1; s = s c; continue }
          if (c != "\"") { s = s c; continue }
          ins = 0; last = s
          if (inscripts && depth == 2) {
            if (havekey) { print key "\t" s; havekey = 0 } else { key = s; havekey = 1 }
          }
          continue
        }
        if (c == "\"") { ins = 1; s = ""; want = 0; continue }
        if (c == ":") { want = (depth == 1 && last == "scripts"); continue }
        if (c == "{") { depth++; if (want && depth == 2) inscripts = 1; want = 0; continue }
        if (c == "}") { if (inscripts && depth == 2) exit; depth--; continue }
        if (c != " " && c != "\t" && c != "\n" && c != "\r") want = 0
      }
    }
  ' package.json 2>/dev/null
}

if [ -n "${AWOS_STOP_CHECKS_CMD:-}" ]; then
  add "$AWOS_STOP_CHECKS_CMD"
elif [ -f package.json ]; then
  pm=npm
  [ -f pnpm-lock.yaml ] && pm=pnpm
  [ -f yarn.lock ] && pm=yarn
  { [ -f bun.lockb ] || [ -f bun.lock ]; } && pm=bun
  # The lock file names a package manager that is not installed (pnpm
  # without corepack, for example): Claude cannot fix that, so let it stop.
  command -v "$pm" >/dev/null 2>&1 || exit 0
  scripts=$(package_scripts)
  tab=$(printf '\t')
  for script in lint typecheck type-check test; do
    line=$(printf '%s\n' "$scripts" | grep -m 1 "^$script$tab") || continue
    # npm init writes a placeholder test script that always fails.
    case "$line" in *"no test specified"*) continue ;; esac
    add "$pm run $script"
  done
elif [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; then
  if [ -x .venv/bin/ruff ] && { [ -f ruff.toml ] || [ -f .ruff.toml ] || grep -q '^\[tool\.ruff' pyproject.toml 2>/dev/null; }; then
    add ".venv/bin/ruff check ."
  fi
  if [ -x .venv/bin/pytest ]; then
    # Exit 5 means "no tests collected": a new project, not a failure.
    add ".venv/bin/pytest -q || [ \$? -eq 5 ]"
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
