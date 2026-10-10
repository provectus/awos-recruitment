#!/bin/sh
# PreToolUse hook for the qa-tester agent: block Bash commands that print implementation source.
# Reads the hook JSON on stdin, inspects each sub-command, exits 2 (block) with a reason on stderr.
set -f
input=$(cat)
[ -z "$input" ] && exit 0
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
else # conservative fallback: everything after "command":" up to the next unescaped quote
  cmd=$(printf '%s' "$input" | tr '\n' ' ' | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"//p' | sed 's/\\"/_/g; s/".*//')
fi
[ -z "$cmd" ] && exit 0

block() { printf 'Blocked: qa-tester tests behavior and does not read source code (%s). Run the feature or its tests instead.\n' "$1" >&2; exit 2; }

# Is this token a path to implementation source? Test files and operational/config files are not.
is_source() {
  t=$1; t=${t#\"}; t=${t#\'}; t=${t%\"}; t=${t%\'}; t=${t#./}; b=${t##*/}
  case "/$t/" in */tests/*|*/test/*|*/__tests__/*|*/spec/*|*/e2e/*) return 1;; esac
  case "$b" in *.test.*|*.spec.*|test_*.py|*_test.go|conftest.py) return 1;; esac
  case "$b" in package.json|package-lock.json|tsconfig*.json|pyproject.toml|Makefile|justfile|README*|.env.example|docker-compose*|Dockerfile*|*.md|*.yaml|*.yml) return 1;; esac
  case "/$t/" in */src/*|*/lib/*|*/app/*|*/server/*|*/pkg/*|*/internal/*|*/cmd/*|*/services/*|*/core/*) return 0;; esac
  case "$b" in *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.py|*.pyi|*.go|*.rs|*.java|*.kt|*.kts|*.swift|*.rb|*.php|*.cs|*.c|*.cc|*.cpp|*.h|*.hpp|*.tf|*.sql|*.sh|*.bash|*.zsh|*.scala|*.vue|*.svelte|*.ex|*.exs) return 0;; esac
  return 1
}
any_source() { for a in "$@"; do is_source "$a" && return 0; done; return 1; }
is_viewer() {
  case "$1" in cat|zcat|head|tail|less|more|sed|awk|grep|egrep|fgrep|rg|ag|ack|find|diff|cp|base64|od|xxd|strings|bat|nl|tac|vi|vim|nvim|nano|emacs|code|open) return 0;; esac
  return 1
}

# Inline interpreters: block when an eval string names a source path or reads files.
if printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_./-])((node|bun)[[:space:]]+(-e|-p|--eval|--print)|deno[[:space:]]+eval|python[0-9.]*[[:space:]]+-[A-Za-z]*c|(ruby|perl)[[:space:]]+-[A-Za-z]*e)([[:space:]]|$)'; then
  if printf '%s' "$cmd" | grep -qE 'readFileSync|readFile|open\(|(^|[^[:alnum:]_])(src|lib|app|server|pkg|internal|cmd|services|core)/|\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|swift|rb|php|cs|c|cc|cpp|h|hpp|tf|sql|sh)([^[:alnum:]_.]|$)'; then
    block "inline interpreter reading source"
  fi
fi

# Split on ; && || | newline $( and backticks, then inspect each sub-command.
printf '%s\n' "$cmd" | tr '\n`' ';;' | sed 's/&&/;/g; s/||/;/g; s/|/;/g; s/\$(/;/g' | tr ';' '\n' | while IFS= read -r sub; do
  set -- $sub
  while [ $# -gt 0 ]; do # skip env assignments and wrappers
    case "$1" in *=*|sudo|env|command|exec|time|nice|nohup|builtin|\\*) shift;; *) break;; esac
  done
  [ $# -eq 0 ] && continue
  c=${1##*/}; shift
  if is_viewer "$c" && any_source "$@"; then block "$c on a source path"; fi
  if [ "$c" = xargs ]; then for a in "$@"; do is_viewer "${a##*/}" && block "xargs $a"; done; fi
  if [ "$c" = git ]; then
    while [ $# -gt 0 ]; do case "$1" in -C|-c) shift; [ $# -gt 0 ] && shift;; -*) shift;; *) break;; esac; done
    sub=${1:-}; [ $# -gt 0 ] && shift
    case "$sub" in
      show|diff|blame|cat-file|grep)
        for a in "$@"; do case "$a" in --stat|--shortstat|--name-only|--name-status|--numstat) continue 2;; esac; done
        block "git $sub prints file content";;
      log) for a in "$@"; do case "$a" in -p|-u|--patch|--full-diff|-L*|-G*|-S*|-[a-zA-Z]*p*) block "git log with a patch";; esac; is_source "$a" && block "git log on a source path"; done;;
    esac
  fi
done
[ $? -eq 2 ] && exit 2
exit 0
