# Start the MCP server
serve:
    cd server && uv run python -m awos_recruitment_mcp

# Run server tests
test *ARGS:
    cd server && uv run pytest {{ARGS}}

# Validate all registry entries against their schemas
validate-registry *ARGS:
    cd server && uv run python -m awos_recruitment_mcp.validate {{ARGS}}

# Check that the skills copied into .claude/skills/ match their registry source
check-skill-parity *ARGS:
    cd server && uv run python -m awos_recruitment_mcp.validate.parity {{ARGS}}

# Build the CLI
build-cli:
    cd cli && npm run build

# Run CLI tests
test-cli *ARGS:
    cd cli && npm test {{ARGS}}

# Publish CLI to npm (bump: patch, minor, or major)
publish-cli bump="patch":
    cd cli && npm version {{bump}} && npm publish --access public

# Build, push to ECR, and redeploy ECS service
deploy account_id region="us-east-1":
    #!/usr/bin/env bash
    set -euo pipefail

    IMAGE="awos-recruitment-mcp"
    ECR_URL="{{account_id}}.dkr.ecr.{{region}}.amazonaws.com/$IMAGE"
    SHA="$(git rev-parse --short HEAD)"

    echo "Building image..."
    docker build --platform linux/amd64 -t "$IMAGE" -f server/Dockerfile .

    echo "Tagging $ECR_URL:$SHA and $ECR_URL:latest..."
    docker tag "$IMAGE" "$ECR_URL:$SHA"
    docker tag "$IMAGE" "$ECR_URL:latest"

    echo "Logging in to ECR..."
    aws ecr get-login-password --region {{region}} | \
        docker login --username AWS --password-stdin "{{account_id}}.dkr.ecr.{{region}}.amazonaws.com"

    echo "Pushing images..."
    docker push "$ECR_URL:$SHA"
    docker push "$ECR_URL:latest"

    echo "Forcing new ECS deployment..."
    aws ecs update-service \
        --region {{region}} \
        --cluster awos-recruitment \
        --service awos-recruitment-mcp \
        --force-new-deployment \
        --no-cli-pager

    echo "Waiting for deployment to stabilize..."
    aws ecs wait services-stable \
        --region {{region}} \
        --cluster awos-recruitment \
        --services awos-recruitment-mcp

    echo "Deploy complete (image: $SHA)"
