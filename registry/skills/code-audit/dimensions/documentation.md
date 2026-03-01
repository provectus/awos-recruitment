---
name: documentation
title: Documentation Quality
description: Verifies that project documentation is accurate, complete, and maintainable
severity: critical
depends-on: [project-topology]
---

# Documentation Quality

Audits documentation coverage across the repository. Well-documented projects are faster to onboard, easier to maintain, and produce fewer knowledge-silo bugs.

## Checks

### DOC-01: Root README exists and is useful

- **What:** The repository has a top-level README.md with setup instructions
- **How:** Read `README.md` at the repo root. Check that it contains: project name, description, setup/install steps, and how to run the project.
- **Pass:** README.md exists and contains setup instructions a new developer could follow
- **Warn:** README.md exists but is missing setup steps or is clearly outdated
- **Fail:** README.md is missing or is an empty placeholder
- **Severity:** critical

### DOC-02: Service-level READMEs exist

- **What:** Each major service directory has its own README.md
- **How:** Read the topology artifact to get the list of service directories. For each detected service directory, check for a README.md
- **Pass:** Every service directory has a README.md with build/run instructions
- **Warn:** Some service directories are missing READMEs
- **Fail:** No service-level READMEs exist
- **Severity:** high

### DOC-03: CLAUDE.md coverage

- **What:** CLAUDE.md files exist at the root and in each major service, providing AI-agent context
- **How:** Glob for `**/CLAUDE.md`. Read the topology artifact to get the list of service directories. Check that the root and each detected service directory has a CLAUDE.md. Verify they contain actionable instructions (not just boilerplate).
- **Pass:** Root + all services have CLAUDE.md files with meaningful content
- **Warn:** Root CLAUDE.md exists but some services are missing theirs
- **Fail:** No CLAUDE.md files exist
- **Severity:** high

### DOC-04: Architecture documentation exists

- **What:** The project has architecture documentation describing system design
- **How:** Look for architecture docs in `context/product/architecture.md`, `docs/architecture.md`, or similar paths. Check for diagrams, component descriptions, or system-level design notes.
- **Pass:** Architecture doc exists and describes the system's components and how they interact
- **Warn:** Architecture doc exists but is incomplete or stale (references removed components)
- **Fail:** No architecture documentation found
- **Severity:** medium

### DOC-05: API documentation is available

- **What:** API endpoints are documented via OpenAPI/Swagger specs or equivalent
- **How:** Glob for `**/swagger/**/*.yaml`, `**/swagger/**/*.yml`, `**/openapi.yaml`, `**/openapi.json`. Also check for generated API docs or Swagger UI configuration.
- **Pass:** OpenAPI specs exist and cover the project's API surface
- **Warn:** Specs exist but appear incomplete (few paths defined relative to the number of controllers)
- **Fail:** No API documentation found
- **Severity:** high

### DOC-06: No stale documentation

- **What:** Documentation references match current code reality
- **How:** Sample 3-5 specific claims from READMEs and CLAUDE.md files (e.g., referenced commands, file paths, tool names). Verify each claim against the actual codebase using Glob and Grep.
- **Pass:** All sampled claims are accurate
- **Warn:** 1-2 sampled claims are inaccurate or outdated
- **Fail:** 3+ sampled claims are inaccurate
- **Severity:** medium
