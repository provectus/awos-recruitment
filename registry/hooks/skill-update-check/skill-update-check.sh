#!/bin/sh
# skill-update-check — SessionStart hook.
# With a lock file: sends .claude/awos-recruitment.lock.json to the registry
# server and shows one line when installed skills are outdated or removed.
# Without a lock file but with installed skills: shows one line that says
# to run `skill status` (no network needed). Once a day per project.
# Fails open: every unexpected condition exits 0 without output.

[ "${AWOS_UPDATE_CHECK:-1}" = "0" ] && exit 0

project="${CLAUDE_PROJECT_DIR:-.}"
lock="$project/.claude/awos-recruitment.lock.json"
skills_dir="$project/.claude/skills"
server="${AWOS_SERVER_URL:-https://recruitment.awos.provectus.pro}"
interval="${AWOS_UPDATE_CHECK_INTERVAL:-86400}"

# --- nothing installed: nothing to say ---------------------------------------
if [ ! -f "$lock" ] && [ ! -d "$skills_dir" ]; then
  exit 0
fi

# --- once per interval, keyed by the project path -----------------------------
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/awos-recruitment"
key=$(printf '%s' "$lock" | cksum | cut -d' ' -f1)
stamp="$cache_dir/$key.checked"
now=$(date +%s 2>/dev/null) || exit 0
last=$(cat "$stamp" 2>/dev/null || echo 0)
case "$last" in
  ''|*[!0-9]*) last=0 ;;
esac
if [ "$interval" -gt 0 ] 2>/dev/null && [ $((now - last)) -lt "$interval" ]; then
  exit 0
fi
mkdir -p "$cache_dir" 2>/dev/null && printf '%s' "$now" > "$stamp" 2>/dev/null

# --- tell the user AND the model ----------------------------------------------
# systemMessage is shown to the user at session start. additionalContext goes
# into the model's context, so the assistant brings it up in its first reply
# and offers the update; people who skip the banner still get asked.
say() {
  escaped=$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')
  context="$escaped In your first reply, tell the user this in one line and offer to run \`npx @provectusinc/awos-recruitment skill update\` for them (it asks before overwriting local edits and keeps them without a terminal). Run it only if the user agrees. Do not bring it up again."
  printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$escaped" "$context"
  exit 0
}

# --- no lock file: installed before the lock file existed ---------------------
if [ ! -f "$lock" ]; then
  count=0
  names=""
  for dir in "$skills_dir"/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    count=$((count + 1))
    names="${names}${names:+, }${name}"
  done
  [ "$count" -gt 0 ] || exit 0
  say "awos-recruitment: $count skill(s) installed without a lock file ($names). Run \`npx @provectusinc/awos-recruitment skill status\` to check for updates."
fi

# --- lock file: ask the server -------------------------------------------------
command -v curl >/dev/null 2>&1 || exit 0
summary=$(curl -sS --max-time 5 \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/plain' \
  --data-binary @"$lock" \
  "$server/check" 2>/dev/null) || exit 0
[ -n "$summary" ] || exit 0

# A server error page would not start with our prefix; stay silent then.
case "$summary" in
  awos-recruitment:*) ;;
  *) exit 0 ;;
esac

say "$summary"
