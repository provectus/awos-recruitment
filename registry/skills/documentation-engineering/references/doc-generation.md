# Document Generation Reference

## README Generation

A generated README should include:

1. **Project title and description** — extracted from package metadata
2. **Tech stack badges** — language, framework, CI status
3. **Prerequisites** — runtime versions, tools required
4. **Installation** — step-by-step setup instructions
5. **Configuration** — environment variables from `.env.example`
6. **Usage** — how to run, common commands
7. **API Reference** — endpoint summary if applicable
8. **Testing** — how to run tests
9. **Deployment** — CI/CD pipeline overview
10. **Contributing** — guidelines extracted from CONTRIBUTING.md or inferred

## Architecture Documentation Template

```markdown
# Architecture: <Project Name>

## Overview
High-level system description and purpose.

## System Diagram
[Mermaid or PlantUML diagram]

## Components
### Component A
- **Purpose**: ...
- **Technology**: ...
- **Key Files**: ...

## Data Flow
1. Request enters via ...
2. Processed by ...
3. Stored in ...

## Infrastructure
- Hosting: ...
- Database: ...
- External Services: ...
```

## API Documentation Template

Extract from OpenAPI/Swagger specs, route definitions, or controller decorators:

```markdown
## API Reference

### GET /api/v1/users
**Description**: List all users
**Auth**: Bearer token required
**Query Params**: `page`, `limit`, `search`
**Response**: `200 OK` — Array of User objects

### POST /api/v1/users
**Description**: Create a new user
**Auth**: Admin role required
**Body**: `{ name, email, role }`
**Response**: `201 Created` — User object
```

## Onboarding Guide Template

```markdown
# Developer Onboarding: <Project Name>

## Day 1: Environment Setup
1. Clone the repository
2. Install dependencies
3. Configure environment variables
4. Run the application locally
5. Run the test suite

## Day 2: Codebase Tour
- Project structure overview
- Key modules and their responsibilities
- Data models and relationships

## Day 3: First Contribution
- Pick a "good first issue"
- Development workflow (branch, commit, PR)
- Code review process
```

## Runbook Template

```markdown
# Runbook: <Project Name>

## Service Overview
- **Service**: ...
- **Team**: ...
- **On-call**: ...

## Health Checks
- Endpoint: `GET /health`
- Expected: `200 OK`

## Common Issues
### Issue: High Latency
- **Symptoms**: Response times > 2s
- **Diagnosis**: Check database connections, cache hit rate
- **Resolution**: Scale replicas, flush cache

### Issue: OOM Errors
- **Symptoms**: Pod restarts, memory alerts
- **Diagnosis**: Check memory usage, heap dumps
- **Resolution**: Increase memory limit, check for leaks
```
