# Project Scaffold Reference

## .env.example (always generate this)
```
# Required
BASE_URL=https://api.example.com

# Auth — uncomment one block only

# Bearer token
# auth_bearer=your-jwt-token-here

# API Key
# auth_apikey=your-api-key-here
# auth_apikey_header=X-API-Key

# Basic auth (base64 of user:pass)
# auth_basic=dXNlcjpwYXNz
```

## README.md template
```markdown
# API Test Suite — <Spec Title>

Generated from: `<spec file name>`  
Generated at: `<timestamp>`  
Framework: `<framework>`

## Prerequisites
<framework-specific prerequisites>

## Setup
```sh
cp .env.example .env
# Edit .env and fill in BASE_URL and auth credentials
```

## Run tests
```sh
<run command from framework reference>
```

## View report
Open `reports/index.html` in your browser after running tests.

## Coverage
| Tag | Endpoints | Happy | Negative | Edge | Workflow |
|-----|-----------|-------|----------|------|----------|
<generated coverage table>

## Gaps
<list any endpoints skipped due to insufficient spec info>
```

## Directory scaffold (create these empty dirs/files)
```
api-tests/
├── .env.example         ← generated
├── README.md            ← generated
├── <config file>        ← from framework reference
├── <package file>       ← from framework reference
├── tests/
│   └── .gitkeep
├── helpers/
│   └── .gitkeep
└── reports/
    └── .gitkeep
```
