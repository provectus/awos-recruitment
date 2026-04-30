# Wireguard-vpn module Makefile

# Clean up
clean:
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@rm -rf build/ dist/ .pytest_cache/
	@docker system prune -f || true


# Pre-commit
PRE_COMMIT_IMAGE=ghcr.io/antonbabenko/pre-commit-terraform:v1.105.0

pre-commit:
	@echo "Running pre-commit (dockerized)..."
	@mkdir -p $$HOME/.cache/pre-commit-docker
	@docker run --rm \
	  -e "USERID=$$(id -u):$$(id -g)" \
	  -e "PRE_COMMIT_HOME=/pc-cache" \
	  -v "$$PWD:/lint" \
	  -v "$$HOME/.cache/pre-commit-docker:/pc-cache" \
	  -w /lint \
	  $(PRE_COMMIT_IMAGE) \
	  run -a


.PHONY: clean pre-commit
