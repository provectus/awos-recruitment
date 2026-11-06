#!/bin/sh
# format-on-edit — PostToolUse hook for Edit|Write|MultiEdit.
# Formats the file Claude just changed with the formatter the project
# already uses: Biome or Prettier from node_modules, ruff or black from
# .venv, gofmt, terraform/tofu fmt. Never installs anything and never uses
# a global JS or Python formatter. Fails open: always exits 0, prints nothing.

[ "${AWOS_FORMAT_ON_EDIT:-1}" = "0" ] && exit 0

project="${CLAUDE_PROJECT_DIR:-.}"
input=$(cat 2>/dev/null) || exit 0

# First "file_path":"..." in the payload is tool_input.file_path. Quotes
# inside file contents are escaped (\"), so they cannot match here.
file=$(printf '%s' "$input" | grep -o '"file_path" *: *"[^"]*"' | head -n 1 \
  | sed 's/^"file_path" *: *"//; s/"$//')
[ -n "$file" ] || exit 0
[ -f "$file" ] || exit 0

# Only files inside the project.
case "$file" in
  "$project"/*) ;;
  *) exit 0 ;;
esac

bin="$project/node_modules/.bin"
venv="$project/.venv/bin"

has_ruff_config() {
  [ -f "$project/ruff.toml" ] || [ -f "$project/.ruff.toml" ] \
    || grep -q '^\[tool\.ruff' "$project/pyproject.toml" 2>/dev/null
}

run() { "$@" >/dev/null 2>&1; }

case "$file" in
  *.js|*.jsx|*.mjs|*.cjs|*.ts|*.tsx|*.mts|*.cts|*.json|*.jsonc|*.css|*.scss|*.less|*.html|*.vue|*.svelte|*.md|*.mdx|*.yaml|*.yml|*.graphql|*.gql)
    if [ -x "$bin/biome" ] && { [ -f "$project/biome.json" ] || [ -f "$project/biome.jsonc" ]; }; then
      run "$bin/biome" format --write "$file"
    elif [ -x "$bin/prettier" ]; then
      run "$bin/prettier" --write --ignore-unknown "$file"
    fi
    ;;
  *.py|*.pyi)
    if [ -x "$venv/ruff" ] && has_ruff_config; then
      # --force-exclude: skip files the project excludes (generated code,
      # migrations), as `ruff format .` does. Without it, ruff formats any
      # file passed by name.
      run "$venv/ruff" format --force-exclude "$file"
    elif [ -x "$venv/black" ]; then
      run "$venv/black" -q "$file"
    fi
    ;;
  *.go)
    command -v gofmt >/dev/null 2>&1 && run gofmt -w "$file"
    ;;
  *.tf|*.tfvars)
    if command -v terraform >/dev/null 2>&1; then
      run terraform fmt "$file"
    elif command -v tofu >/dev/null 2>&1; then
      run tofu fmt "$file"
    fi
    ;;
esac

exit 0
