#!/bin/sh
# PreToolUse hook for the qa-tester agent: block Bash commands that print implementation source.
# Reads the hook JSON on stdin, inspects each sub-command, exits 2 (block) with a reason on stderr.
# Tests: .claude/hooks/qa-tester-no-source_test.sh
set -f
input=$(cat)
[ -z "$input" ] && exit 0
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
else # conservative fallback: everything after "command":" up to the next unescaped quote, JSON escapes unfolded
  cmd=$(printf '%s' "$input" | tr '\n' ' ' | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"//p' | sed 's/\\"/_/g; s/".*//' | awk '{gsub(/\\n/, "\n"); gsub(/\\t/, " "); print}')
fi
[ -z "$cmd" ] && exit 0

block() { printf 'Blocked: qa-tester tests behavior and does not read source code (%s). Run the feature or its tests instead.\n' "$1" >&2; exit 2; }

clean() { # strip quotes, shell punctuation and dd-style prefixes from a token
  t=$1; t=${t#\"}; t=${t#\'}; t=${t%\"}; t=${t%\'}; t=${t%\)}; t=${t%\}}; t=${t#if=}; t=${t#./}; printf '%s' "$t"
}
is_testpath() { case "/$1/" in */tests/*|*/test/*|*/__tests__/*|*/spec/*|*/e2e/*) return 0;; esac; return 1; }
# Is this token a path to implementation source? Test files and operational/config/log files are not.
is_source() {
  t=$(clean "$1"); b=${t##*/}
  is_testpath "$t" && return 1
  case "$b" in *.test.*|*.spec.*|test_*.py|*_test.go|conftest.py) return 1;; esac
  case "$b" in package.json|package-lock.json|tsconfig*.json|pyproject.toml|Makefile|justfile|README*|docker-compose*|Dockerfile*|*.md|*.yaml|*.yml|*.config.*|.env*|*.log|*.txt|*.out) return 1;; esac
  case "/$t/" in */src/*|*/lib/*|*/app/*|*/server/*|*/pkg/*|*/internal/*|*/cmd/*|*/services/*|*/core/*) return 0;; esac
  case "$b" in *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.py|*.pyi|*.go|*.rs|*.java|*.kt|*.kts|*.swift|*.rb|*.php|*.cs|*.c|*.cc|*.cpp|*.h|*.hpp|*.tf|*.sql|*.sh|*.bash|*.zsh|*.scala|*.vue|*.svelte|*.ex|*.exs) return 0;; esac
  return 1
}
any_source() { for a in "$@"; do is_source "$a" && return 0; done; return 1; }
# A directory, or a non-existent extensionless path (a directory as far as a recursive search is concerned).
is_dirlike() { t=$(clean "$1"); [ -d "$t" ] && return 0; [ -f "$t" ] && return 1; case "${t##*/}" in *.*) return 1;; esac; return 0; }
is_viewer() {
  case "$1" in cat|zcat|head|tail|less|more|sed|awk|grep|egrep|fgrep|rg|ag|ack|diff|sdiff|cp|base64|od|xxd|hexdump|strings|bat|nl|tac|sort|cut|paste|rev|fold|fmt|pr|expand|unexpand|uniq|comm|join|column|dd|vi|vim|nvim|nano|emacs|code|open) return 0;; esac
  return 1
}
is_shell() { case "$1" in sh|bash|zsh|dash|ksh|python*|node|bun|deno|perl|ruby) return 0;; esac; return 1; }

# Input redirection from a source path: cat<src/x, <src/x cat, while ...; done < src/x, $(<src/x)
for tgt in $(printf '%s' "$cmd" | grep -oE '(^|[^<>])<[[:space:]]*[^[:space:]<>&|;()]+' | sed 's/^[^<]*<[[:space:]]*//'); do
  is_source "$tgt" && block "input redirection from a source path"
done

# Inline interpreters: block when an eval string names a source path or reads files.
if printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_./-])((node|bun)[[:space:]]+(-e|-p|--eval|--print)|deno[[:space:]]+eval|python[0-9.]*[[:space:]]+-[A-Za-z]*c|(ruby|perl)[[:space:]]+-[A-Za-z]*e)([[:space:]]|$)'; then
  if printf '%s' "$cmd" | grep -qE 'readFileSync|readFile|open\(|(^|[^[:alnum:]_])(src|lib|app|server|pkg|internal|cmd|services|core)/|\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|kt|swift|rb|php|cs|c|cc|cpp|h|hpp|tf|sql|sh)([^[:alnum:]_.]|$)'; then
    block "inline interpreter reading source"
  fi
fi

# Recursive search (grep -r, rg, ag, ack): block a search with no path (defaults to the tree) or over a non-test directory.
search_check() {
  c=$1; shift
  recursive=1; case "$c" in grep|egrep|fgrep) recursive=0;; esac
  pattern_given=0; npaths=0; dd=0
  while [ $# -gt 0 ]; do
    if [ $dd -eq 0 ]; then
      case "$1" in
        --) dd=1; shift; continue;;
        -e|-f|--regexp|--file) pattern_given=1; shift; [ $# -gt 0 ] && shift; continue;;
        --regexp=*|--file=*) pattern_given=1; shift; continue;;
        -m|-A|-B|-C|-g|-t|-T|-E|-M|-j|--max-count|--include|--exclude|--exclude-dir|--glob|--iglob|--type|--type-not|--max-depth|--context|--after-context|--before-context|--color|--colour|--encoding|--threads) shift; [ $# -gt 0 ] && shift; continue;;
        --recursive|--dereference-recursive) recursive=1; shift; continue;;
        --*) shift; continue;;
        -[rR]*|-[!-]*[rR]*) case "$c" in grep|egrep|fgrep) recursive=1;; esac; shift; continue;;
        -*) shift; continue;;
      esac
    fi
    if [ $pattern_given -eq 0 ]; then pattern_given=1
    else
      npaths=$((npaths+1))
      is_dirlike "$1" && ! is_testpath "$(clean "$1")" && block "$c recursing into $1"
    fi
    shift
  done
  [ $recursive -eq 1 ] && [ $npaths -eq 0 ] && [ $piped -eq 0 ] && block "$c with no path searches the whole tree"
  return 0
}

# Split on ; && || | & newline $( <( `, then inspect each sub-command. @P@ marks "reads from a pipe".
piped=0
printf '%s\n' "$cmd" | tr '\n`' ';;' | sed 's/&&/;/g; s/||/;/g; s/|&/;@P@;/g; s/|/;@P@;/g; s/\$(/;/g; s/<(/;/g; s/>(/;/g; s/>&/>/g; s/&>/>/g; s/&/;/g' | tr ';' '\n' | while IFS= read -r sub; do
  set -- $sub
  [ "${1:-}" = "@P@" ] && { piped=1; continue; }
  while [ $# -gt 0 ]; do # skip env assignments, wrappers, keywords and grouping punctuation
    case "$1" in
      *=*|sudo|env|command|exec|time|nice|nohup|builtin|then|do|else|elif|if|while|until|\{|\(|\!) shift;;
      \\*) t=${1#\\}; shift; set -- "$t" "$@";;
      \(*|\{*|\!*) t=${1#?}; shift; set -- "$t" "$@";;
      *) break;;
    esac
  done
  if [ $# -eq 0 ]; then piped=0; continue; fi
  c=${1##*/}; shift
  if is_viewer "$c" && any_source "$@"; then block "$c on a source path"; fi
  case "$c" in grep|egrep|fgrep|rg|ag|ack) search_check "$c" "$@";; esac
  if [ "$c" = for ]; then any_source "$@" && block "for loop over source paths"; fi
  if [ "$c" = xargs ]; then for a in "$@"; do is_viewer "${a##*/}" && block "xargs $a"; done; fi
  if [ "$c" = find ]; then
    while [ $# -gt 0 ]; do
      case "$1" in -exec|-execdir|-ok|-okdir) e=${2:-}; e=${e##*/}; if is_viewer "$e" || is_shell "$e"; then block "find $1 $e"; fi;; esac; shift
    done
  fi
  if [ "$c" = git ]; then
    while [ $# -gt 0 ]; do case "$1" in -C|-c) shift; [ $# -gt 0 ] && shift;; -*) shift;; *) break;; esac; done
    sub=${1:-}; [ $# -gt 0 ] && shift
    [ "$sub" = stash ] && [ "${1:-}" = show ] && { sub=show; shift; }
    case "$sub" in
      show|diff|blame|cat-file|grep)
        statonly=0; blob=0; patch=0
        for a in "$@"; do case "$a" in --stat|--shortstat|--name-only|--name-status|--numstat|--dirstat*|--summary|-s|--no-patch) statonly=1;; -p|-u|--patch*) patch=1;; *:*) blob=1;; esac; done
        [ $statonly -eq 1 ] && [ $blob -eq 0 ] && [ $patch -eq 0 ] || block "git $sub prints file content";;
      log) for a in "$@"; do case "$a" in --patch*|--full-diff|-L*|-G*|-S*|-p*|-u*|-[!-]*p*|-[!-]*u*) block "git log with a patch";; esac; is_source "$a" && block "git log on a source path"; done;;
    esac
  fi
  piped=0
done
[ $? -eq 2 ] && exit 2
exit 0
