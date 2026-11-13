#!/bin/sh
# PreToolUse hook for Bash, Read and Grep, declared in this skill's front matter.
# An allow-list: a command passes only if every part of it is a listed local
# read tool or a read verb of a cloud, cluster, infrastructure-as-code or git
# CLI, and is not one of the reads that print secrets. Everything else is
# refused. It is a guardrail behind references/rules.md, not a sandbox: it
# reads the command text, so it cannot follow everything a program does at run
# time. Exit 2 blocks the call and shows stderr to Claude. Exit 0 allows it.
#
# Two modes. DRP_MODE=skill (the front matter): Claude Code runs a skill's hook
# in the main session only. On every Bash or Agent call it marks the session as
# a DR run, then checks Bash, Read and Grep calls. DRP_MODE=gate (an optional
# project settings hook, see README.md): settings hooks also run in subagents,
# which share the session id. It checks a subagent's Bash, Read or Grep call
# only while the session carries the mark, so it does nothing outside DR runs.
#
# Internal use: DRP_RAW=1 makes stdin the raw text to check (a script file or
# the string of a `sh -c`), DRP_CODE=1 marks that text as program code, DRP_CWD
# is the folder its relative paths start from, DRP_DEPTH counts nesting.
# Tests: python3 scripts/block-writes_test.py

self_dir=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || self_dir=.
self="$self_dir/$(basename "$0")"
depth=${DRP_DEPTH:-0}
input=$(cat)

# json <jq filter> <python expression on d> <key>: a string field of the hook
# input, read with jq, else python3, else cut out with sed (escapes expanded).
json() {
  out=$(printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null) && [ -n "$out" ] &&
    { printf '%s' "$out"; return; }
  out=$(printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print($2 or '')" 2>/dev/null) &&
    [ -n "$out" ] && { printf '%s' "$out"; return; }
  out=$(printf '%s' "$input" | tr '\n' ' ' |
    sed -nE 's/.*"'"$3"'"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')
  # Undo the JSON escapes. \\ is set aside first, so that \\" stays a backslash and a quote.
  [ -n "$out" ] && printf '%s\n' "$out" | awk '{
    gsub(/\\\\/, "\001"); gsub(/\\"/, "\""); gsub(/\\n/, "\n"); gsub(/\\t/, "\t")
    gsub(/\\\//, "/"); gsub(/\001/, "\\"); print }'
}

if [ "${DRP_RAW:-0}" = 1 ]; then
  cmd=$input
  cwd=${DRP_CWD:-$(pwd)}
else
  # The short fields in one jq call, else one by one. The separator is the
  # unit separator (\037): a blank one such as a tab would merge empty fields.
  if meta=$(printf '%s' "$input" | jq -r '[.tool_name, .session_id, .agent_id, .cwd] | map(. // "" | tostring | gsub("[\u001f\n]"; " ")) | join("\u001f")' 2>/dev/null) && [ -n "$meta" ]; then
    us=$(printf '\037')
    IFS=$us read -r tool sid aid cwd <<EOF_META
$meta
EOF_META
  else
    tool=$(json '.tool_name' 'd.get("tool_name")' tool_name)
    sid=$(json '.session_id' 'd.get("session_id")' session_id)
    aid=$(json '.agent_id' 'd.get("agent_id")' agent_id)
    cwd=$(json '.cwd' 'd.get("cwd")' cwd)
  fi
  case $sid in *[!A-Za-z0-9_-]*) sid= ;; esac
  mark="${TMPDIR:-/tmp}/drp-active/$sid"
  case ${DRP_MODE:-skill} in
    gate)
      # Only a subagent's Bash call in a marked session; the skill hook
      # itself checks the main session.
      { [ -n "$sid" ] && [ -f "$mark" ] && [ -n "$aid" ]; } || exit 0 ;;
    *)
      [ -n "$sid" ] && { [ -f "$mark" ] || { mkdir -p "${mark%/*}" 2>/dev/null && : > "$mark"; }; }
      case $tool in ''|Bash|Read|Grep) ;; *) exit 0 ;; esac ;;
  esac
  # Read and Grep are checked as the shell command they stand for, so the same
  # secret-file and secret-word rules apply. Values are only checked, never run:
  # quotes are removed, and the pattern keeps only the characters the
  # secret-word rule looks at.
  arg() { printf "'%s'" "$(printf '%s' "$1" | tr "'\n" '_ ')"; }
  case $tool in
    Read)
      fp=$(json '.tool_input.file_path' 'd.get("tool_input",{}).get("file_path")' file_path)
      cmd="cat $(arg "${fp:-.}")" ;;
    Grep)
      pat=$(json '.tool_input.pattern' 'd.get("tool_input",{}).get("pattern")' pattern | tr -c 'A-Za-z0-9_.|-' ' ')
      gp=$(json '.tool_input.path' 'd.get("tool_input",{}).get("path")' path)
      gg=$(json '.tool_input.glob' 'd.get("tool_input",{}).get("glob")' glob)
      case $(json '.tool_input.output_mode' 'd.get("tool_input",{}).get("output_mode")' output_mode) in
        content) gf=-n ;; count) gf=-c ;; *) gf=-l ;;
      esac
      cmd="grep $gf -e $(arg "$pat") $(arg "${gp:-.}")"
      [ -z "$gg" ] || cmd="$cmd $(arg "$gg")" ;;
    *)
      cmd=$(json '.tool_input.command' 'd.get("tool_input",{}).get("command")' command) ;;
  esac
  # Failing all three, scan the whole input: that can block more, never less.
  [ -n "$cmd" ] || cmd=$input
fi
[ -n "$cwd" ] && [ -d "$cwd" ] || cwd=$(pwd)

block() {
  echo "Blocked by the disaster-recovery-plan skill: $1. This run is read-only (references/rules.md). Write the command into the document for a human to run instead. To edit files, use the Edit or Write tool." >&2
  exit 2
}

# One awk pass does the work. It splits the command into simple commands on
# ; & | and newlines outside quotes, joins backslash-newline continuations,
# treats a heredoc body as commands only when it feeds a shell, then
# drops quotes and backslashes (so 'delete-table' and de\lete-table match) and
# checks each simple command against the allow-list. It prints "BLOCK<tab>reason" and exits 2, or
# prints "SCAN0|SCAN1<tab>path" and "SHC|SHCB<tab>text" for scripts, `sh -c` and backticks
# strings that this shell script then checks the same way.
# The program sits in a function body: a heredoc written directly inside $(...)
# is misparsed by some shells when it holds unbalanced quotes or brackets.
awkprog() {
  cat <<'AWK'
# emit(segment, segment without its single-quoted text): single-quoted text is
# never expanded, so $( and backticks in it do not run anything. Blanks inside
# quotes arrive as \002, so that a quoted value stays one word.
function emit(x, y) {
  gsub(/["'\\]/, "", x)
  if (x ~ /[^[:space:]]/) { segs[++ns] = x; lits[ns] = y }
}
function blk(m) { print "BLOCK\t" m; exit 2 }
{
  line = $0
  full = full "\n" line
  if (inhd) {
    chk = line
    if (hstrip) sub(/^\t+/, "", chk)
    if (chk == hdelim) { inhd = 0; next }
    if (!hkeep) next
    q = ""
  }
  n = length(line); i = 1; hd = ""
  while (i <= n) {
    c = substr(line, i, 1)
    if (q == "'") { cur = cur (c ~ /[ \t]/ ? "\002" : c); if (c == "'") q = ""; i++; continue }
    if (c == "\\") {
      if (i == n && q == "") { cont = 1; i++; continue }
      cur = cur substr(line, i, 2); lit = lit substr(line, i, 2); i += 2; continue
    }
    if (q == "\"") { cur = cur (c ~ /[ \t]/ ? "\002" : c); lit = lit c; if (c == "\"") q = ""; i++; continue }
    if (c == "'" || c == "\"") { q = c; cur = cur c; if (c == "\"") lit = lit c; i++; continue }
    if (c == "<" && substr(line, i, 2) == "<<" && substr(line, i + 2, 1) != "<") {
      rest = substr(line, i + 2); hs = 0
      if (substr(rest, 1, 1) == "-") { hs = 1; rest = substr(rest, 2) }
      sub(/^[[:space:]]*/, "", rest)
      if (match(rest, /^["']?[A-Za-z_][A-Za-z0-9_]*/)) {
        hd = substr(rest, RSTART, RLENGTH); gsub(/["']/, "", hd); hdstrip = hs
      }
      cur = cur "<<"; lit = lit "<<"; i += 2; continue
    }
    # & in a redirection (2>&1, &>file, <&3) does not end a command.
    if (c == "&" && (substr(line, i - 1, 1) ~ /[<>]/ || substr(line, i + 1, 1) == ">")) { cur = cur c; lit = lit c; i++; continue }
    if (c == ";" || c == "&" || c == "|") { emit(cur, lit); cur = lit = ""; i++; continue }
    cur = cur c; lit = lit c; i++
  }
  if (cont) { cont = 0; cur = cur " "; lit = lit " " }
  else if (q == "") { emit(cur, lit); cur = lit = "" }
  else { cur = cur "\002"; lit = lit " " }
  if (hd != "" && !inhd) {
    inhd = 1; hdelim = hd; hstrip = hdstrip
    r = line; gsub(/[0-9]*>&[0-9]|[0-9]*>[[:space:]]*\/dev\/null/, "", r)
    hkeep = (r ~ /(^|[^[:alnum:]_.-])(bash|sh|zsh|dash|ksh|source)([[:space:]]|$)/)
    if (!hkeep && r ~ />/) hfile = 1
  }
}
# pos(from, value-flag regex): the positional words from T[from] on, in P[],
# past flags and the values of the flags that take one, and past redirections.
function pos(from, vf,   i, x, n) {
  n = 0; split("", P)
  for (i = from; i <= NT; i++) {
    x = T[i]
    if (x == "") continue
    if (x ~ /^#/) break
    if (x ~ /^[0-9]*[<>]/) { if (x ~ /^[0-9]*[<>]+&?$/) i++; continue }
    if (x ~ /^-/) { if (x !~ /=/ && x ~ vf) i++; continue }
    P[++n] = x
  }
  return n
}
# path(from): the words from T[from] up to the first flag (az and gcloud
# command paths).
function path(from,   i, n) {
  n = 0; split("", P)
  for (i = from; i <= NT; i++) {
    if (T[i] == "") continue
    if (T[i] ~ /^(-|#|[0-9]*[<>])/) break
    P[++n] = T[i]
  }
  return n
}
# subs(text): print each $(...), <(...), >(...) and `...` body as a command to
# check. The split above has already cut a body at | ; &, so an open body
# runs to the end of the part.
function subs(q,   i, n, c, d, j, body) {
  n = length(q)
  for (i = 1; i <= n; i++) {
    c = substr(q, i, 1)
    if (c == "\\") { i++; continue }
    if (c == "`") {
      j = index(substr(q, i + 1), "`")
      body = j ? substr(q, i + 1, j - 1) : substr(q, i + 1)
      if (body ~ /[^[:space:]]/) print "SHCB\t" body
      i += j ? j : n; continue
    }
    if ((c == "$" || c == "<" || c == ">") && substr(q, i + 1, 1) == "(") {
      if (c == "$" && substr(q, i + 2, 1) == "(") { i += 2; continue }
      d = 1; j = i + 2
      while (j <= n && d > 0) { c = substr(q, j, 1); if (c == "(") d++; else if (c == ")") d--; j++ }
      body = substr(q, i + 2, j - i - 3 + (d > 0))
      if (body ~ /[^[:space:]]/) print "SHC\t" body
      i = j - 1
    }
  }
}
function no(m) { blk(m " is not a read") }
BEGIN { TMPRE = "^(/tmp/|/private/tmp/|/var/folders/|/private/var/folders/|\\$TMPDIR|\\$\\{TMPDIR)"
  BLINDMSG = "a command that runs on file names it gets from input (xargs, parallel, find -exec); only ls, stat, wc, checksums and grep -l or -c may run so; write the file names out" }
# namesonly(text): the --query or --format filter shows no environment values:
# it takes names only (keys(@), [].name), or never touches the environment, and
# on Google Cloud it is a projection, not json or yaml.
function namesonly(x,   q) {
  if (!match(x, /--(query|format)[= ]/)) return 0
  q = substr(x, RSTART + RLENGTH)
  if (q ~ /keys\(|\[\]\.name|\.name\)/) return 1
  if (x ~ /--format/ && q !~ /^(value|table|csv|get|list|flattened)\(/) return 0
  return q !~ /environ|variables|env/
}
function cnt(x, re) { return gsub(re, "", x) }
# filt(x): the field filter of a command, lowercased, from its first filter
# flag to the end; "" when there is none.
function filt(x) {
  if (!match(x, /[[:space:]](--query|--format|--jq|-q|--template|(-o|--output)[[:space:]=]*(jsonpath|go-template|custom-columns|template))([[:space:]=]|$)/)) return ""
  return tolower(substr(x, RSTART))
}
# secretfield(q): the filter selects a field that holds a secret value. Names
# in literals (name=='github-token') do not count: a field name has no hyphen
# before it. Compound names that only describe a secret are removed first.
function secretfield(q) {
  gsub(/password(authentication|policy|profile|lastused|lastchanged|lastset|expir[a-z]*|reset[a-z]*|reuse[a-z]*|length|enabled|required|count)/, "", q)
  gsub(/accesskey(id|ids|metadata|lastused|status)/, "", q)
  gsub(/(secret|token)(name|names|id|ids|arn|ref|refs|uri|url|count|expir[a-z]*|list|type|version[a-z]*|rotation[a-z]*|createddate|lastchangeddate)/, "", q)
  return q ~ /(^|[^-[:alnum:]_])[[:alnum:]_]*(password|passwd|secretstring|secretbinary|secretvalue|clientsecret|connectionstring|(primary|secondary)(readonly)?(master)?key|accesskey|privatekey|accesstoken|authtoken|sastoken|refreshtoken|bearertoken|apikeyvalue)[[:alnum:]_]*/ ||
    q ~ /(^|[.:])(token|secret|password|value)([^-[:alnum:]_]|$)/ && q ~ /(secret|token|password|credential)/
}

# A command that gets its file names from input the hook cannot see (xargs,
# parallel, find -exec) may only print names, counts or checksums.
function blindok(b, r) {
  if (b ~ /^(ls|stat|file|wc|du|basename|dirname|realpath|echo|printf|test|\[|shasum|sha1sum|sha256sum|md5|md5sum|cksum)$/) return 1
  return b ~ /^(grep|egrep|fgrep|rg|ag|ack)$/ && r ~ /(^|[[:space:]])(-[[:alnum:]]*[lLc][[:alnum:]]*|--files-with-matches|--files-without-match|--count)([[:space:]]|$)/
}

# unq(text): the text as the shell passes it on: quotes removed, and inside
# double quotes \" \\ \$ \` turned into the character. The awk program's
# own "..." strings stay, so they can be emptied.
function unq(t,   i, n, c, q, r, d) {
  n = length(t); q = ""; r = ""
  for (i = 1; i <= n; i++) {
    c = substr(t, i, 1)
    if (q == "'") { if (c == "'") q = ""; else r = r c; continue }
    if (c == "\\") { d = substr(t, i + 1, 1); if (q == "" || d ~ /["\\$`]/) { r = r d; i++ } else r = r c; continue }
    if (q == "\"") { if (c == "\"") q = ""; else r = r c; continue }
    if (c == "'" || c == "\"") { q = c; continue }
    r = r c
  }
  return r
}
function check(s, sq,   sl, i, x, y, w, wi, pre, envp, xa, base, a1, np, v, g, d) {
  NT = split(s, T, /[[:space:]]+/)
  for (i = 1; i <= NT; i++) gsub(/\002/, " ", T[i])
  gsub(/\002/, " ", s)
  sl = tolower(s)
  subs(sq)

  # The command word: past prefixes (sudo, env, xargs, do, then...), their
  # flags, variable assignments, case labels and opening brackets.
  w = ""; wi = 0; pre = 0; envp = 0; xa = 0
  for (i = 1; i <= NT; i++) {
    x = T[i]; sub(/^[({!]+/, "", x)
    if (x == "") continue
    if (x ~ /^#/) break
    if (x ~ /^(do|then|else|elif|if|while|until|time|exec|command|builtin|nohup|sudo|doas|env|nice|ionice|timeout|stdbuf|xargs|parallel|watch|caffeinate)$/) { pre = 1; if (x == "env") envp = 1; if (x ~ /^(xargs|parallel)$/) xa = 1; continue }
    # An assignment, with its $(...) or `...` value: subs() checks that value.
    if (x ~ /^[A-Za-z_][A-Za-z0-9_]*=/) {
      d = cnt(x, "\\(") - cnt(x, "\\)"); g = cnt(x, "`") % 2
      while ((d > 0 || g) && i < NT) { i++; d += cnt(T[i], "\\(") - cnt(T[i], "\\)"); if (cnt(T[i], "`") % 2) g = !g }
      continue
    }
    if (pre && (x ~ /^-/ || x == "{}" || x ~ /^[0-9]+[smhd]?$/)) continue
    # A shell function: its body is the command; later calls to it pass.
    if (x ~ /^[A-Za-z_][A-Za-z0-9_]*\(\)\{?$/) { sub(/\(.*/, "", x); fn[x] = 1; continue }
    if (x == "function" && T[i + 1] ~ /^[A-Za-z_][A-Za-z0-9_]*(\(\))?$/) { x = T[++i]; sub(/\(.*/, "", x); fn[x] = 1; continue }
    if (x ~ /^[^()]*\)$/ && x !~ /^[0-9]*[<>]/) continue
    w = x; wi = i; break
  }
  if (w == "") { if (envp) blk("env without a command prints the environment, which can hold credentials"); return }
  base = w; sub(/.*\//, "", base)
  if (base in fn) return
  if (base == "drp-hook-selftest") blk("self-test; the hook is active")
  # Variables that make a tool run a command or load code: git (GIT_*), pagers,
  # editors, less, shell start-up files, the loader, node and perl.
  for (i = 1; i <= NT; i++)
    if (T[i] ~ /^(GIT_[A-Z0-9_]*|PAGER|MANPAGER|EDITOR|VISUAL|LESSOPEN|LESSCLOSE|BASH_ENV|ENV|PROMPT_COMMAND|LD_[A-Z_]+|DYLD_[A-Z_]+|NODE_OPTIONS|PERL5OPT|PYTHONSTARTUP)=/)
      blk("a variable (" substr(T[i], 1, index(T[i], "=") - 1) ") that can make a tool run a command; leave it unset")
  if (xa) { x = s; sub(/^.*(^|[[:space:]])(xargs|parallel)[[:space:]]/, "", x); if (!blindok(base, x)) blk(BLINDMSG) }
  a1 = ""
  for (i = wi + 1; i <= NT; i++) {
    if (T[i] ~ /^#/) break
    if (T[i] == "" || T[i] ~ /^-/ || T[i] ~ /^[0-9]*[<>]/) continue
    a1 = T[i]; break
  }

  # Commands the text does not show.
  if (w ~ /^[$`]/) blk("a command name taken from a variable or a substitution; write the command out")
  if (base == "eval") blk("eval; write the command out")
  if (base ~ /^(bash|sh|zsh|dash|ksh|mksh|fish|source|\.)$/) {
    if (s ~ /[[:space:]]-[[:alnum:]]*c([[:space:]]|$)/) {
      if (s ~ /[[:space:]]-[[:alnum:]]*c[[:space:]]+\$/) blk("a shell that runs a command from a variable; write the command out")
      x = s; sub(/^.*[[:space:]]-[[:alnum:]]*c[[:space:]]+/, "", x); print "SHC\t" x; runs = 1
      return
    }
    if (a1 == "") blk("input piped or redirected into a shell; write the command out")
    print "SCAN0\t" a1; runs = 1
    return
  }
  if (base ~ /^(python[0-9.]*|pypy[0-9]*|node|nodejs|deno|bun|perl|ruby|php|pwsh|powershell|ts-node|tsx)$/) {
    if (s ~ /[[:space:]]-m[[:space:]]+(awscli|azure\.cli|pip|ensurepip)/) blk("a CLI or installer run as a module; run the read command directly")
    if (s !~ /[[:space:]](-[[:alnum:]]*[ceEr][[:alnum:]]*|--eval|--command|-|-m)([[:space:]]|$)/ && a1 != "" && a1 != "run") { print "SCAN1\t" a1; runs = 1 }
    return
  }
  if (w ~ /^(\.\/|\.\.\/|~\/)/ || w ~ /^\/.*\.(sh|bash|py|js|rb|pl)$/) { print "SCAN0\t" w; runs = 1; return }

  # Files and searches that print secrets, whatever the command.
  if (base !~ /^(ls|stat|file|wc|test|\[|du|find|shasum|sha256sum|md5|md5sum|aws|az|gcloud|kubectl|oc|helm|kustomize|terraform|tofu)$/ &&
      !(base ~ /^(grep|egrep|fgrep|rg|ag|ack)$/ && s ~ /[[:space:]](-[[:alnum:]]*[lLc][[:alnum:]]*|--files-with-matches|--files-without-match|--count)([[:space:]]|$)/) &&
      (s ~ /(^|[[:space:]=<:\/])secrets?\/[^[:space:]]+/ || s ~ /[^[:space:]]\/secrets?([[:space:]]|$)/ ||
       s ~ /(^|[[:space:]\/=<:])[^[:space:]\/]*(secret|cred)[^[:space:]\/]*\.(ya?ml|json|txt|env|ini|conf|cfg|properties|toml)([[:space:]]|$)/ ||
      s ~ /(^|[[:space:]\/=<:])(\.env(\.[[:alnum:]_-]+)?|[^[:space:]]*\.tfstate(\.backup)?|[^[:space:]]*\.tfvars(\.json)?|[^[:space:]]*\.(pem|key|p12|pfx|jks|keystore)|id_(rsa|dsa|ecdsa|ed25519)|credentials(\.json)?|kubeconfig|\.kube\/config|\.docker\/config\.json|\.npmrc|\.netrc|\.pgpass|[^[:space:]]*service[-_]?account[^[:space:]]*\.json)([[:space:]]|$)/) &&
      s !~ /\.(example|sample|template|dist)([[:space:]]|$)/ &&
      !(base == "git" && s !~ /[[:space:]](show|cat-file|blame|diff|grep)([[:space:]]|$)/ &&
        !(s ~ /[[:space:]]log([[:space:]]|$)/ && s ~ /[[:space:]](-p|--patch|-u|-L[^[:space:]]*|--word-diff[^[:space:]]*|--full-diff)([[:space:]]|$)/)))
    blk("a read of a file that can hold secrets (.env, state, tfvars, keys, credentials, secrets/ folders, *secret* or *cred* manifests); report it by location only, or list matches with grep -l")
  if (base ~ /^(grep|egrep|fgrep|rg|ag|ack|git)$/ &&
      sl ~ /(password|passwd|passphrase|api[_-]?key|private[_-]?key|begin[[:space:]].*private|connection[_-]?string|client[_-]?secret|secret[_-]?(key|value)|access[_-]?key|auth[_-]?token|access[_-]?token|bearer)/ &&
      s !~ /[[:space:]](-[[:alnum:]]*[lLc][[:alnum:]]*|--files-with-matches|--files-without-match|--count)([[:space:]]|$)/ &&
      s !~ /(^|[^[:alnum:]_.-])git[[:space:]]+(log|status|branch|show-ref|rev-parse|ls-files)/)
    blk("a search for secret words that prints the matching lines; search with -l to report locations only")

  # GNU sed's e command and s///e flag, and sort's compress program, run commands.
  if (base ~ /^g?sed$/ && (s ~ /[\/|#,:@!][gpiImMw0-9]*e[gpiImM0-9]*([[:space:]'";}]|$)/ || s ~ /(^|[[:space:];{}'"0-9$])e([[:space:]'";}]|$)/))
    blk("a sed script with the e command or flag, which runs a command")
  if (base ~ /^g?sort$/ && s ~ /[[:space:]]--compress/) blk("sort --compress-program, which runs a command")

  # Shell syntax and local tools that only read, or write only local files.
  if (base ~ /^(for|case|esac|in|select|fi|done|then|else|\}|\)|cd|pushd|popd|export|unset|local|readonly|set|shift|true|false|:|exit|return|break|continue|wait|sleep|read|echo|printf|test|\[|\[\[|\]\]|let|expr|seq|bc|date|cal|uname|whoami|id|hostname|which|type|hash|pwd|basename|dirname|realpath|readlink|ls|tree|stat|file|du|df|fd|cat|bat|head|tail|less|more|grep|egrep|fgrep|rg|ag|ack|sed|jq|yq|sort|uniq|cut|tr|wc|diff|cmp|comm|column|nl|fold|fmt|paste|join|rev|tac|expand|unexpand|iconv|base64|xxd|od|hexdump|strings|shasum|sha1sum|sha256sum|md5|md5sum|cksum|mkdir|mktemp|touch|cp|tee|zcat|dig|nslookup|host|whois)$/) {
    if (base == "export" && (wi == NT || T[wi + 1] == "-p")) blk("export without a name prints the environment, which can hold credentials")
    if (base == "set" && wi == NT) blk("set without arguments prints the environment, which can hold credentials")
    return
  }
  if (base ~ /^(awk|gawk|mawk|nawk)$/) {
    if (s ~ /system[[:space:]]*\(|\|[[:space:]]*getline/) blk("an awk program that runs commands")
    # Output pipes and redirections of print and printf. This part has lost
    # its quotes, so a match must also be in the raw command with each "..."
    # string emptied: a printed "->" or "a|b" passes, and so does ||.
    if (full ~ /(^|[[:space:]=])\$'/) blk("an awk program in $'...' quotes, which the hook cannot check; use single quotes")
    x = s; gsub(/\|\|/, "", x); y = unq(full); gsub(/"([^"\\\n]|\\.)*"/, "\"\"", y); gsub(/\|\|/, "", y)
    if (x ~ /printf?[^;}]*\|&?[[:space:]]*["[:alpha:]_($]/ && y ~ /printf?[^;}]*\|&?[[:space:]]*["[:alpha:]_($]/) blk("an awk output pipe, which runs a command")
    if (x ~ /printf?[^;}]*>/ && y ~ /printf?[^;}]*>/) blk("an awk print redirected to a file, which changes files; print to standard output")
    if (s ~ /[[:space:]](-f|--file)([[:space:]=]|$)|[[:space:]]-f[^[:space:]]/) blk("an awk program from a file, which the hook cannot check; write the program out")
    # gawk: a program file (-E), an included source file (-i, @include) or a
    # loaded extension (-l, @load) is code the hook cannot check.
    if (s ~ /[[:space:]](-E|--exec|-i|--include|-l|--load)([[:space:]=]|$)|[[:space:]]-[Eil][^[:space:]]|@(include|load)/) blk("an awk program file, include or extension, which the hook cannot check; write the program out")
    if (s ~ /ENVIRON/) blk("awk ENVIRON, which prints the environment and can hold credentials")
    return
  }
  if (base == "find") {
    if (s ~ /[[:space:]]-(exec|execdir|ok|okdir)[[:space:]]/) {
      x = s; sub(/^.*[[:space:]]-(exec|execdir|ok|okdir)[[:space:]]+/, "", x)
      sub(/[[:space:]]*(;|\+)[[:space:]]*$/, "", x); print "SHC\t" x
      v = x; sub(/^[[:space:]]+/, "", v); sub(/[[:space:]].*/, "", v); sub(/.*\//, "", v)
      if (!blindok(v, x)) blk(BLINDMSG)
    }
    if (s ~ /[[:space:]]-delete([[:space:]]|$)/ && a1 !~ /^(\/tmp\/|\/private\/tmp\/|\/var\/folders\/|\/private\/var\/folders\/|\$TMPDIR|\$\{TMPDIR)/)
      blk("find that deletes files outside a temporary folder")
    return
  }
  # mv may rename inside the project or a temporary folder; it may not take a
  # project file out of the project.
  if (base == "mv") {
    np = pos(wi + 1, "^(-t|--target-directory)$")
    if (np < 2) return
    x = P[np]
    if (x ~ /^(\/|~|\.\.)/ && x !~ TMPRE) blk("mv to a folder outside the project (" x ")")
    if (x ~ TMPRE) for (i = 1; i < np; i++) if (P[i] !~ TMPRE) blk("mv of a project file into a temporary folder (" P[i] "); copy it with cp instead")
    return
  }
  if (base ~ /^(rm|rmdir|shred|unlink|truncate)$/) {
    np = pos(wi + 1, "^$")
    for (i = 1; i <= np; i++) {
      if (P[i] !~ /^(\/tmp\/|\/private\/tmp\/|\/var\/folders\/|\/private\/var\/folders\/|\$TMPDIR|\$\{TMPDIR)/) blk(base " outside a temporary folder (" P[i] "); use the Write or Edit tool")
    }
    return
  }

  # HTTP: reads only, to any host.
  if (base ~ /^(curl|wget|http|https|xh|httpie)$/) {
    if (sl ~ /([[:space:]](-x|--request|--method)[[:space:]=]*|^|[[:space:]])(post|put|patch|delete)([[:space:]]|$)/) blk("an HTTP request that changes state")
    if (s ~ /[[:space:]](-F|--form[a-z-]*|-T|--upload-file|--json|--post-data|--post-file|--body-data|--body-file)([[:space:]=]|$)/ ||
        (s ~ /[[:space:]](-d|--data[a-z-]*)([[:space:]=]|$)/ && !(base == "curl" && s ~ /[[:space:]](-G|--get)([[:space:]]|$)/))) blk("an HTTP request that sends data")
    return
  }

  # Field filters on any CLI: the fields they select must not hold secrets.
  if (base ~ /^(aws|az|gcloud|kubectl|oc|gh)$/ && (x = filt(s)) != "") {
    if (secretfield(x)) blk("a filter that selects a secret value (" x "); select names, ids or settings only")
    if (base ~ /^(kubectl|oc)$/ && s ~ /[[:space:]]get[[:space:]]+[^[:space:]]*(cm|configmaps?|secrets?)([.,\/[:space:]]|$)/ &&
        x ~ /(\.data|\.binarydata|\.stringdata)([^.[:alnum:]_]|$)/ && !pipekeys)
      blk("a Kubernetes filter that prints ConfigMap or Secret data; list the keys with -o jsonpath='{.data}' | jq 'keys'")
    if (x ~ /(\.env|(^|[^[:alnum:]_])env\[)([^[:alnum:]_]|$|\[)/ && x !~ /env(\[[^]]*\])?\.name/ && x !~ /keys\(/)
      blk("a filter that prints environment values; select the names only (env[*].name)")
  }

  # Log reads print whatever the services wrote, secrets included.
  if ((base ~ /^(kubectl|oc)$/ && T[wi + 1] ~ /^logs?$/) ||
      (base == "aws" && s ~ /[[:space:]]logs[[:space:]]+(get-log-events|filter-log-events|get-query-results|get-log-record|tail|start-live-tail)([[:space:]]|$)/) ||
      (base == "gcloud" && s ~ /[[:space:]](logging[[:space:]]+(read|tail)|logs[[:space:]]+(read|tail))([[:space:]]|$)/) ||
      (base == "az" && s ~ /[[:space:]](logs[[:space:]]+show|log[[:space:]]+(tail|download)|log-analytics[[:space:]]+query|app-insights[[:space:]]+(query|events)|monitor[[:space:]]+activity-log[[:space:]]+list[[:space:]].*--query[^[:space:]]*properties)/))
    blk("a log read, which can print anything the service wrote, secrets included; check log settings with a describe command, or put the log query in the document for a human")

  # GitHub webhooks: the config, requests and payloads can carry tokens.
  if (base == "gh" && s ~ /[[:space:]]api[[:space:]]/ && s ~ /\/hooks([\/[:space:]?]|$)/) {
    x = tolower(s); if (!match(x, /[[:space:]](--jq|-q)[[:space:]=]/)) blk("a GitHub webhook read without --jq prints its config and deliveries; select fields, for example --jq '.[] | {id, events, active, host: (.config.url | split(\"/\")[2])}'")
    x = substr(x, RSTART); gsub(/\.config\.url[[:space:]]*\|[[:space:]]*split\([^)]*\)[[:space:]]*\[2\]/, "", x)
    if (x ~ /(config|request|response|payload|headers|secret|token)/) blk("a GitHub webhook read that prints its config or delivery content; select ids, events, status and the URL host only")
  }

  # Reads that print the environment variables or app settings of functions,
  # containers and apps, on any provider: allowed only with a filter.
  if ((base == "az" && s ~ /appsettings[[:space:]]+list/ && sl !~ /--query[= ]+\[\]\.name/) ||
      (!namesonly(sl) &&
      ((base == "aws" && s ~ /(get-function-configuration|lambda[[:space:]]+get-function([[:space:]]|$)|describe-task-definition|describe-configuration-settings|describe-job-definitions|batch-get-projects)/) ||
       (base == "gcloud" && s ~ /(run[[:space:]]+(services|jobs)[[:space:]]+describe|functions[[:space:]]+describe|app[[:space:]]+versions[[:space:]]+describe)/))))
    blk("a read that prints environment values; filter it to the names, for example --query 'Environment.Variables | keys(@)' on AWS, --query '[].name' on Azure, --format='value(spec.template.spec.containers[0].env[].name)' on Google Cloud")

  # Manifest renders, on any tool: piped into a names-only filter, no plugins.
  if ((base == "kustomize" && T[wi + 1] == "build") || (base ~ /^(kubectl|oc)$/ && s ~ /[[:space:]]kustomize([[:space:]]|$)/) ||
      (base == "helm" && s ~ /[[:space:]]template([[:space:]]|$)/)) {
    if (s ~ /--enable-(exec|alpha-plugins|star)/) blk("a manifest render that runs plugins, which can decrypt secrets (for example ksops); read the kustomization files instead")
    if (!piped) blk("a manifest render that can print generated Secret data; pipe it to a names-only filter, for example | yq '.kind + \"/\" + .metadata.name'")
    return
  }

  # AWS: aws <service> <operation>; only read operations.
  if (base == "aws") {
    np = pos(wi + 1, "^--(profile|region|output|endpoint-url|query|color|ca-bundle|cli-read-timeout|cli-connect-timeout|cli-binary-format)$")
    if (np == 0 || P[1] == "help" || P[2] == "help" || P[2] == "") return
    if (P[1] ~ /^\$/ || P[2] ~ /^\$/) blk("an AWS service or operation taken from a variable; write it out")
    if (s ~ /[[:space:]](--with-decryption|--include-values?)([[:space:]]|$)/) blk("an AWS read that prints a secret value")
    if (P[1] == "configure" && v == "get" && P[3] ~ /(secret|key_id|token|password|credential)/) blk("AWS configure get of a credential prints it; check the login with aws sts get-caller-identity")
    v = P[2]
    if (v ~ /^(get-secret-value|get-password-data|get-authorization-token|get-login-password|get-session-token|get-federation-token|get-credentials-for-identity|get-open-id-token.*|get-.*-token|get-object|get-item|batch-get-item|get-records)$/)
      blk("AWS " v " prints a secret or stored data")
    # An app client holds its secret: pass only with a --query that leaves it out.
    if (v == "describe-user-pool-client" && sl ~ /--query[= ]/ && sl !~ /secret/) return
    if (v ~ /(password|token|credential|access-details|api-keys?$|user-pool-client$)/) blk("AWS " v " can print a secret; read only the fields you need with --query, or list the resource by name")
    if ((P[1] == "s3" && v == "ls") || (P[1] == "configure" && v ~ /^(list|list-profiles)$/) ||
        (P[1] == "configure" && v == "get" && P[3] !~ /(secret|key_id|token|password|credential)/) ||
        (P[1] == "sso" && v == "login") || (P[1] == "eks" && v == "update-kubeconfig") ||
        v ~ /^(describe|list|get|head|lookup|search|filter|batch-get|preview|estimate|validate|check|simulate)-/) return
    no("AWS " P[1] " " v)
  }

  # Azure: az <group...> <verb>; only list and show, plus local selection.
  if (base == "az") {
    if (s ~ /(secret[[:space:]]+(show|download|backup)|(key|certificate)[[:space:]]+(download|backup)|connection-string|keys[[:space:]]+list|list-keys|list-secrets|list-credentials|credential[[:space:]]+show|publishing-profiles|publishing-credentials|--show-secrets|--show-values|get-access-token|generate-sas)/)
      blk("an Azure command that prints a secret")
    np = path(wi + 1)
    for (i = 1; i <= np; i++) if (P[i] ~ /^\$/) blk("an Azure command path taken from a variable; write it out")
    g = ""; for (i = 1; i <= np; i++) g = g (i > 1 ? " " : "") P[i]
    if (g == "rest") { if (sl ~ /[[:space:]](--method|-m)[[:space:]=]*(put|post|patch|delete)([[:space:]]|$)/) blk("an Azure REST request that changes state"); return }
    if (g == "aks get-credentials" && s ~ /[[:space:]](--admin|-a|--file[[:space:]=]+-|-f[[:space:]=]+-)([[:space:]]|$)/)
      blk("az aks get-credentials --admin or --file - gets or prints cluster-admin credentials; use the user credentials")
    if (np == 0 || g ~ /^(account (set|show|list)|aks get-credentials|login|version|account list-locations)$/ || P[np] ~ /^(list(-[a-z-]+)?|show(-[a-z-]+)?|exists|query|version|check-name(-availability)?)$/) return
    no("Azure \"az " g "\"")
  }

  # Google Cloud: the first verb in the command path decides.
  if (base == "gcloud") {
    np = path(wi + 1)
    for (i = 1; i <= np; i++) if (P[i] ~ /^\$/) blk("a Google Cloud command path taken from a variable; write it out")
    if (np == 0 || P[1] ~ /^(config|version|info)$/ || (P[1] == "auth" && P[2] ~ /^(list|login)$/) ||
        (P[1] == "container" && P[2] == "clusters" && P[3] == "get-credentials")) return
    # The first word is a group (run, deploy, sql...), after a release track.
    for (i = (P[1] ~ /^(alpha|beta|preview)$/ ? 3 : 2); i <= np; i++) {
      if (P[i] ~ /^(list|describe|ls|du|read|get-iam-policy|get-value|get-ancestors|get-ancestors-iam-policy|search-all-resources|search-all-iam-policies|list-[a-z-]+|describe-[a-z-]+)$/) return
      if (P[i] ~ /^(create|delete|update|patch|deploy|set|add|remove|import|export|restore|start|stop|reset|resize|restart|clone|switchover|failover|upload|cancel|enable|disable|apply|undelete|rollback|cp|mv|rm|rsync|cat|run|execute|submit|publish|pull|push|attach|detach|move|rename|replace|suspend|resume|reboot|rotate|sign|ssh|scp|connect|proxy|tail|access|wait|activate|revoke|[a-z]+-[a-z-]+)$/)
        no("Google Cloud " P[i])
    }
    no("this Google Cloud command")
  }
  if (base == "gsutil") {
    if (s !~ /(^|[^[:alnum:]_.-])gsutil[[:space:]]+(-[[:alnum:]]+[[:space:]]+)*(ls|du|stat|version|hash)([[:space:]]|$)/) no("gsutil other than ls, du, stat, version and hash")
    return
  }

  # Kubernetes and Helm.
  if (base ~ /^(kubectl|oc)$/) {
    if (s ~ /[[:space:]]--raw/) blk("a raw Kubernetes API request")
    # The verb and the resource type are the first words that are not flags
    # or flag values: kubectl get -n prod secret db is a secret read too.
    np = pos(wi + 1, "^(-n|--namespace|--context|--cluster|--kubeconfig|--user|-s|--server|--as|--as-group|--token|--request-timeout|-l|--selector|-o|--output|--field-selector|-L|--label-columns|--sort-by|--template|-f|--filename|-c|--container|--chunk-size|--subresource|-k|--kustomize)$")
    if (P[1] ~ /^(get|describe)$/) {
      x = tolower(P[2]); gsub(/,/, " ", x); np = split(x, R, " ")
      for (i = 1; i <= np; i++) {
        sub(/\/.*/, "", R[i]); sub(/\..*/, "", R[i])
        if (R[i] ~ /^secrets?$/ && (P[1] == "describe" ? 0 : s ~ /(-o|--output)/)) blk("a Kubernetes command that prints secret data")
        if (P[1] == "get" && R[i] ~ /^(cm|configmaps?|po|pods?|deploy|deployments?|sts|statefulsets?|ds|daemonsets?|rs|replicasets?|jobs?|cronjobs?|cj|all|applications?|app|applicationsets?|helmreleases?|hr|kustomizations?|notebooks?|inferenceservices?|isvc|externalsecrets?|es|secretstores?|clustersecretstores?)$/ &&
            s ~ /[[:space:]](-o|--output)[[:space:]=]*(yaml|json)([[:space:]]|$)/)
          blk("a Kubernetes read that prints config or environment values; select fields with -o jsonpath or -o custom-columns")
        if (P[1] == "describe" && R[i] ~ /^(cm|configmaps?)$/) blk("kubectl describe configmap prints its data; list the keys with -o jsonpath='{.data}' | jq 'keys'")
      }
    }
    if (s ~ /[[:space:]]get[[:space:]]+(secret|secrets)([[:space:]]|\/|$)/ && s ~ /(-o|--output)/) blk("a Kubernetes command that prints secret data")
    if (s ~ /[[:space:]](-o|--output)[[:space:]=]*(yaml|json)([[:space:]]|$)/ &&
        s ~ /[[:space:]]get[[:space:]]+[^[:space:]]*(^|,|[[:space:]]|\/)?(cm|configmaps?|po|pods?|deploy|deployments?|sts|statefulsets?|ds|daemonsets?|rs|replicasets?|jobs?|cronjobs?|cj|all|applications?|app|applicationsets?|helmreleases?|hr|kustomizations?|notebooks?|inferenceservices?|isvc|externalsecrets?|es|secretstores?|clustersecretstores?)([.,\/[:space:]]|$)/)
      blk("a Kubernetes read that prints config or environment values; select fields with -o jsonpath or -o custom-columns")
    if (s ~ /[[:space:]]describe[[:space:]]+(cm|configmaps?)([[:space:]\/]|$)/) blk("kubectl describe configmap prints its data; list the keys with -o jsonpath='{.data}' | jq 'keys'")
    np = pos(wi + 1, "^(-n|--namespace|--context|--cluster|--kubeconfig|--user|-s|--server|--as|--as-group|--token|--request-timeout)$")
    v = P[1]
    if (v ~ /^\$/) blk("a Kubernetes verb taken from a variable; write it out")
    if (np == 0 || v ~ /^(get|describe|explain|api-resources|api-versions|version|cluster-info|top|events)$/ ||
        (v == "auth" && P[2] ~ /^(can-i|whoami)$/) || (v == "config" && P[2] ~ /^(view|get-contexts|current-context|use-context|get-clusters|get-users)$/)) return
    no("kubectl " v)
  }
  if (base == "helm") {
    np = pos(wi + 1, "^(-n|--namespace|--kube-context|--kubeconfig)$")
    v = P[1]
    if (np == 0 || v ~ /^(list|ls|status|history|show|search|version|env|lint|verify)$/ ||
        (v ~ /^(dependency|dep|repo)$/ && P[2] ~ /^(list|ls)$/) || (v == "get" && P[2] ~ /^(notes|metadata|hooks)$/)) return
    no("helm " v (v == "get" ? " " P[2] : ""))
  }
  if (base == "kustomize") { if (T[wi + 1] ~ /^(version|help|--help)$/) return; no("kustomize " T[wi + 1]) }

  # Infrastructure as code: never init, plan, apply, state, output or show.
  if (base ~ /^(terraform|tofu)$/) {
    np = pos(wi + 1, "^$")
    v = P[1]
    if (np == 0 || v ~ /^(version|validate|graph|help)$/ || (v == "providers" && P[2] ~ /^(schema)?$/) ||
        (v == "workspace" && P[2] ~ /^(list|show)$/) || (v == "fmt" && s ~ /[[:space:]]-check([[:space:]]|$)/)) return
    no(base " " v)
  }

  # Git and GitHub: reads only.
  if (base == "git") {
    # Global options before the subcommand: -c, --config-env and --exec-path
    # can make git run a command.
    for (i = wi + 1; i <= NT && T[i] ~ /^-/; i++) {
      if (T[i] ~ /^(-c|--config-env|--exec-path)(=|$)/ || T[i] ~ /^-c./) blk("git " T[i] ", which can make git run a command; leave git configuration to the user")
      if (T[i] ~ /^(-C|--git-dir|--work-tree|--namespace)$/) i++
    }
    np = pos(wi + 1, "^(-C|-c|--git-dir|--work-tree|--namespace)$")
    v = P[1]
    if (s ~ /[[:space:]](-O[^[:space:]]*|--open-files-in-pager[^[:space:]]*|--upload-pack[^[:space:]]*|--receive-pack[^[:space:]]*|--exec[^[:space:]]*|--ext-diff|--textconv)([[:space:]]|$)/ ||
        (v == "ls-remote" && s ~ /[[:space:]]-u([[:space:]]|$)/))
      blk("a git option that runs a command (a pager, upload-pack or external diff)")
    if (v == "branch" && s ~ /[[:space:]](-[[:alnum:]]*[dDmMcCfu][[:alnum:]]*|--delete|--force|--move|--copy|--set-upstream-to|--unset-upstream|--edit-description)([[:space:]]|$)/)
      blk("a git command that changes branches")
    if (v == "tag" && P[2] != "" && s !~ /[[:space:]]tag[[:space:]]+(-l|--list|-n[0-9]*|--contains|--no-contains|--points-at|--merged|--no-merged|--sort)/)
      blk("a git command that creates or deletes tags")
    if (v == "config" && s !~ /[[:space:]](--get|--get-all|--get-regexp|--list|-l)([[:space:]]|$)/) blk("a git configuration change")
    if (np == 0 || v ~ /^(log|show|diff|status|ls-files|ls-tree|ls-remote|grep|blame|annotate|rev-parse|rev-list|describe|shortlog|cat-file|name-rev|for-each-ref|show-ref|merge-base|count-objects|check-ignore|check-attr|whatchanged|var|help|version|branch|tag|config)$/ ||
        (v == "remote" && P[2] ~ /^(show|get-url)?$/) || (v == "reflog" && P[2] ~ /^(show)?$/) ||
        (v ~ /^(stash|worktree)$/ && P[2] == "list")) return
    blk("a git command that changes the repository (git " v "); leave git to the user")
  }
  if (base == "gh") {
    np = pos(wi + 1, "^(-R|--repo)$")
    if (P[1] == "api") {
      if (sl ~ /([[:space:]](-x|--method)[[:space:]=]*(post|put|patch|delete)|[[:space:]](-f|--field|--raw-field|--input)([[:space:]=]|$))/) blk("a GitHub API request that changes state")
      return
    }
    if (np == 0 || P[1] ~ /^(search|status|version)$/ || (P[1] == "auth" && P[2] == "status") || P[2] ~ /^(list|ls|view|status|checks|diff|get)$/) return
    no("gh " P[1] " " P[2])
  }

  blk("`" base "` is not on this skill's list of read-only commands. Use a listed read command, or record the fact as _unverified_ with this command for a human to run")
}
END {
  if (cur != "") emit(cur, lit)
  f = full; gsub(/["'\\]/, "", f)
  # Credentials from the instance metadata service.
  if (f ~ /169\.254\.169\.254|169\.254\.170\.2|fd00:ec2::254|metadata\.google\.internal|metadata\.azure\.com|\/metadata\/identity/)
    blk("a request to the instance metadata service, which returns credentials")
  if (f ~ /drp-active/) blk("a command that touches the DR run mark, which turns on the checks in subagents")
  # Program code that drives a cloud SDK, starts processes or uses the network.
  if (code == 1 || f ~ /(^|[^[:alnum:]_.-])(python[0-9.]*|pypy[0-9]*|node|nodejs|deno|bun|perl|ruby|php|pwsh|powershell|osascript)[[:space:]]+(-[[:alnum:]]*[[:space:]]+)*(-[[:alnum:]]*[ceEr][[:alnum:]]*|--eval|--command|-)([[:space:]]|$)/)
    if (f ~ /(^|[;[:space:]])(import|from)[[:space:]]+(boto3|botocore|aiobotocore|azure|google\.cloud|googleapiclient|kubernetes|subprocess|urllib|requests|httpx|http\.client|aiohttp|socket|pty|paramiko|fabric|pexpect)([.[:space:],;]|$)/ ||
        f ~ /(require|import)[[:space:]]*\(?[[:space:]]*(child_process|@aws-sdk|aws-sdk|@azure\/|@google-cloud|@kubernetes|node:child_process|node:https?|node:net|https?|net|axios|node-fetch)([^[:alnum:]_-]|$)/ ||
        f ~ /(subprocess\.|os\.(system|popen|exec[a-z]*|spawn[a-z]*)[[:space:]]*\(|pty\.spawn|execSync|spawnSync|execFileSync|Popen\(|fetch\(|XMLHttpRequest|Net::HTTP|LWP::|IO::Socket|Open3|IO\.popen|shell_exec|passthru|proc_open|[^.[:alnum:]_]system[[:space:]]*\()/)
      blk("program code that uses a cloud SDK, starts processes or uses the network; use the listed read commands directly")
  # Program code is not shell: its lines are not commands.
  if (code == 1) { print "OK"; exit 0 }
  # A manifest render passes only when piped into yq or grep, the names-only
  # filter references/rules.md asks for.
  piped = (f ~ /\|[[:space:]]*(yq|grep)([[:space:]]|$)/)
  # ConfigMap data passes only when piped into jq that keeps the keys.
  pipekeys = (f ~ /\|[[:space:]]*jq[[:space:]][^|]*keys/)
  for (k = 1; k <= ns; k++) check(segs[k], lits[k])
  # A heredoc that writes a file is data, unless the same call runs a script:
  # then write the script in one call and run it in the next, where it is read.
  if (hfile && runs) blk("a call that writes a file from a heredoc and runs a script; write the script first, then run it in a separate call")
  print "OK"
  exit 0
}
AWK
}

out=$(printf '%s\n' "$cmd" | LC_ALL=C awk -v code="${DRP_CODE:-0}" "$(awkprog)")
reason=$(printf '%s\n' "$out" | sed -n 's/^BLOCK	//p' | head -n 1)
[ -n "$reason" ] && block "$reason"
# No verdict means the check itself failed: refuse rather than let it pass.
printf '%s\n' "$out" | grep -qx OK || block "the hook could not check this command (awk failed); split it into simpler commands"

# Check scripts and `sh -c` strings the same way, before they run.
nested() { # nested <code: 0 or 1> <label>; text on stdin
  [ "$depth" -lt 2 ] || block "a command that runs another script or shell more than two levels deep ($2)"
  DRP_RAW=1 DRP_CODE="$1" DRP_CWD="$cwd" DRP_DEPTH=$((depth + 1)) sh "$self" ||
    block "$2 holds a blocked command (see above)"
}
printf '%s\n' "$out" | {
  while IFS= read -r l; do
    kind=${l%%	*}
    arg=${l#*	}
    case $kind in
      SHC) printf '%s\n' "$arg" | nested 0 "the sh -c string" || exit 2 ;;
      SHCB) printf '%s\n' "$arg" | nested 0 "a backtick substitution (backticks run their text as a command, inside double quotes too; to match a literal backtick, put it in single quotes)" || exit 2 ;;
      SCAN0 | SCAN1)
        case $arg in
          /*) p=$arg ;;
          "~/"*) p="$HOME/${arg#\~/}" ;;
          *) p="$cwd/$arg" ;;
        esac
        # A missing file runs nothing; the command fails on its own.
        if [ -f "$p" ]; then
          head -c 262144 "$p" | nested "${kind#SCAN}" "the script $arg" || exit 2
        fi
        ;;
    esac
  done
  exit 0
} || exit 2
