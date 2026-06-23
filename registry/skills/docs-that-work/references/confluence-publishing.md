# Confluence Publishing

## Markdown to Confluence Storage Format

| Markdown | Confluence Storage Format |
|----------|--------------------------|
| `# Heading` | `<h1>Heading</h1>` |
| `**bold**` | `<strong>bold</strong>` |
| `` `code` `` | `<code>code</code>` |
| Code blocks | `<ac:structured-macro ac:name="code">` |
| Tables | `<table><tr><th>...</th></tr></table>` |
| Links | `<a href="...">text</a>` |
| Images | `<ac:image><ri:url ri:value="..." /></ac:image>` |
| Info boxes | `<ac:structured-macro ac:name="info">` |

## Page Creation Workflow

1. **Source credentials** — load .env file
2. **Identify target space** — ask user or use provided `--space` parameter
3. **Check for existing page** — search by title via API to avoid duplicates
4. **Convert content** — Markdown to Confluence Storage Format
5. **Create/update page** — via Confluence MCP server
6. **Add labels** — auto-generated, auto-docs, repo name, doc type
7. **Verify publication** — fetch page back and confirm formatting
8. **Report result** — display page URL, space, and parent location

## Page Update Strategy

- Compare content hash to detect changes
- Preserve existing page metadata (labels, watchers, restrictions)
- Increment version number for Confluence versioning
- Add update note: "Auto-updated from <repo> on <date>"

## Sync with Git

Use `git log --since="<last-sync-date>" --name-only` to detect repo changes since the last sync. Filter for doc-relevant paths (README, docs/, api/, schema, models, routes, controllers).

1. Fetch current Confluence page content via API
2. Re-analyze repository for changes
3. Generate updated documentation sections
4. Diff old vs new content
5. Update only changed sections — preserve manual edits
6. Update sync timestamp label
