# Validate all registry entries against their schemas
validate-registry *ARGS:
    cd server && uv run python -m awos_recruitment_mcp.validate {{ARGS}}
