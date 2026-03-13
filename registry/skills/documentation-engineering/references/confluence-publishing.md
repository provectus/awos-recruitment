# Confluence Publishing Reference

## Markdown to Confluence Storage Format

Key conversions:

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
