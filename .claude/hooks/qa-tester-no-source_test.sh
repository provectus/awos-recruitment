#!/bin/sh
# Tests for qa-tester-no-source.sh: run from anywhere; builds a throwaway project tree so directory checks are real.
# Usage: sh .claude/hooks/qa-tester-no-source_test.sh
here=$(cd "$(dirname "$0")" && pwd); hook="$here/qa-tester-no-source.sh"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT; cd "$tmp" || exit 1
mkdir -p src cli server tests logs/server; : > src/app.py; : > src/x.ts; : > src/x.test.ts; : > cli/vitest.config.ts
: > server/.env.example; : > tests/x.test.ts; : > logs/server/out.log; : > package.json; : > README.md
pass=0; fail=0
run() { printf '%s' "$2" | jq -Rs '{tool_input:{command:.}}' | sh "$hook" >/dev/null 2>&1; rc=$?
  want=0; [ "$1" = block ] && want=2
  if [ $rc -eq $want ]; then pass=$((pass+1)); else fail=$((fail+1)); printf 'FAIL expected %s (got %s): %s\n' "$1" "$rc" "$2"; fi; }

# --- must block: plain viewers and shell-syntax bypasses
for c in 'cat src/app.py' '{ cat src/x.ts; }' '(cat src/x.ts)' 'if true; then cat src/x.ts; fi' \
  'for f in src/*.ts; do cat $f; done' 'true & cat src/x.ts' '\cat src/x.ts' '\\cat src/x.ts' 'cat<src/x.ts' '<src/x.ts cat' \
  'while read l; do echo "$l"; done < src/app.py' 'echo "$(<src/app.py)"' 'ls; cat src/app.py' 'ls && cat src/app.py' \
  'FOO=1 cat src/app.py' 'sudo cat src/app.py' 'cat ./src/app.py' "cat 'src/app.py'" \
  'npm test | cat src/app.py' 'diff src/a.py src/b.py' 'cp src/app.py /tmp/' 'sed -n 1,10p src/app.py' 'awk 1 src/app.py' \
  'sort src/app.py' 'cut -c1- src/app.py' 'paste src/app.py' 'hexdump -C src/app.py' 'dd if=src/app.py' 'uniq src/app.py' \
  'xargs cat < list' 'find src -name "*.ts" -exec cat {} \;' 'find . -name "*.py" -exec sh -c "cat {}" \;' \
  'node -e "console.log(require(\"fs\").readFileSync(\"src/app.py\"))"' 'python -c "print(open(\"src/app.py\").read())"'; do run block "$c"; done
# --- must block: recursive searches over source
for c in 'grep -rn "" cli' 'grep -rn "app.get" .' 'grep -r pattern' 'grep --recursive foo' 'rg def .' 'rg def' 'rg -n foo src' 'ag foo' 'ack foo .' 'grep -R foo server' 'rg -e foo' 'grep -nr foo' 'grep -rin foo'; do run block "$c"; done
# --- must block: git content paths
for c in 'git show HEAD:src/app.py' 'git show --stat HEAD:src/app.py' 'git show --name-only HEAD:src/app.py' 'git diff --stat -p' 'git log --patch-with-stat' \
  'git log -p' 'git log --patch' 'git stash show -p' 'git blame src/app.py' 'git cat-file -p HEAD:src/app.py' 'git grep foo' 'git diff' 'git show' 'git log -u' 'git log -pn5' 'git log -np' 'git log -- src/app.py'; do run block "$c"; done

# --- must allow: operational files, tests, logs, running things
for c in 'cat cli/vitest.config.ts' 'cp server/.env.example server/.env' 'tail /var/log/app/server.log' 'grep ERROR logs/server/out.log' \
  'find src -name "*.test.ts"' 'find . -name "*.py"' 'cat package.json' 'cat README.md' 'cat tests/x.test.ts' 'cat src/x.test.ts' 'npm test' 'pytest tests -k smoke' \
  'grep -rn foo tests/' 'rg pattern tests' 'npm test | rg FAIL' 'npm test 2>&1 | grep -i error' 'git diff --stat' 'git log --oneline -5' 'git log --author=pat -n5' 'git show --stat HEAD' \
  'git status' 'ls src' 'npx tsc --noEmit' 'echo hi 2>&1' 'curl -s localhost:3000/api | head' 'cat output.txt' 'grep foo build.out' \
  'python src/app.py' 'node src/x.ts' 'for t in tests/*.test.ts; do npx vitest run $t; done' 'cat <<EOF
hello
EOF' 'sort results.txt | uniq -c' 'make test' 'docker compose up -d'; do run allow "$c"; done

# --- no-jq fallback must still split on JSON \n (PATH with every tool the hook needs except jq)
mkdir -p "$tmp/bin"; for t in sh cat tr sed awk grep printf; do ln -s "$(command -v $t)" "$tmp/bin/$t" 2>/dev/null; done
printf '{"tool_input":{"command":"ls\\ncat src/app.py"}}' | env PATH="$tmp/bin" sh "$hook" >/dev/null 2>&1; rc=$?
if [ $rc -eq 2 ]; then pass=$((pass+1)); else fail=$((fail+1)); printf 'FAIL expected block (got %s): fallback parser on JSON \\n\n' "$rc"; fi

printf 'passed: %d, failed: %d\n' "$pass" "$fail"; [ $fail -eq 0 ]
