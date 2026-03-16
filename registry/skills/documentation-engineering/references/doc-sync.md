# Documentation Sync Reference

## Change Detection

Use `git log --since="<last-sync-date>" --name-only` to detect repo changes since the last Confluence sync. Filter for doc-relevant paths (README, docs/, api/, schema, models, routes, controllers).

## Sync Workflow

1. Fetch current Confluence page content via API
2. Re-analyze repository for changes
3. Generate updated documentation sections
4. Diff old vs new content
5. Update only changed sections (preserve manual edits)
6. Update sync timestamp label

## Reference Assets

| Asset | Source | Description |
|-------|--------|-------------|
| README templates | Provectus repos | Standardized README structures |
| Architecture templates | `docs/architecture/` | System design document templates |
| API doc generators | OpenAPI specs | Automated API documentation |
| Confluence macros | Atlassian docs | Storage format reference |
| Runbook templates | SRE practices | Incident response documentation |
