#!/bin/sh
# skill-update-check — SessionStart hook.
# Sends .claude/awos-recruitment.lock.json to the registry server and shows
# one line when installed skills are outdated or removed. Once a day per
# project. Fails open: every unexpected condition exits 0 without output.

[ "${AWOS_UPDATE_CHECK:-1}" = "0" ] && exit 0

lock="${CLAUDE_PROJECT_DIR:-.}/.claude/awos-recruitment.lock.json"
[ -f "$lock" ] || exit 0
command -v curl >/dev/null 2>&1 || exit 0

server="${AWOS_SERVER_URL:-https://recruitment.awos.provectus.pro}"
interval="${AWOS_UPDATE_CHECK_INTERVAL:-86400}"

# --- once per interval, keyed by the lock file path -------------------------
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

# --- ask the server ----------------------------------------------------------
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

# --- tell the user (not the model) --------------------------------------------
escaped=$(printf '%s' "$summary" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '{"systemMessage":"%s"}\n' "$escaped"
exit 0
