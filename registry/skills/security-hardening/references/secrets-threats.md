## Secrets Management

### Secret Detection and Prevention

Patterns to detect in pre-commit scanning:
```
# High-confidence secret patterns
AWS Access Key:       AKIA[0-9A-Z]{16}
AWS Secret Key:       [0-9a-zA-Z/+]{40}
GitHub Token:         gh[pousr]_[0-9a-zA-Z]{36}
GitLab Token:         glpat-[0-9a-zA-Z\-]{20}
Generic API Key:      [aA][pP][iI][-_]?[kK][eE][yY].*['\"][0-9a-zA-Z]{32,}
Private Key:          -----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----
JWT Token:            eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+
Database URL:         (postgres|mysql|mongodb)://[^\s]+:[^\s]+@
Slack Webhook:        https://hooks.slack.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[a-zA-Z0-9]+
```

Files that should always be excluded from commits:
```gitignore
# Secrets and credentials
.env
.env.local
.env.*.local
*.pem
*.key
*.p12
*.pfx
secrets/
credentials/
**/service-account*.json
```

### Automated Scanning with security-scan

When the `security-scan` CLI is installed, prefer it over manual regex matching:

```bash
# Check availability
which security-scan

# Basic scan with console output
security-scan scan .

# JSON output for programmatic processing
security-scan scan . --format json

# Markdown output for reports
security-scan scan . --format markdown

# Scan only staged files (pre-commit)
security-scan scan --staged-only

# Use project-specific config
security-scan -c security-scan.yaml scan .

# Generate baseline to filter known findings
security-scan baseline .
```

`security-scan` wraps gitleaks and adds:
- Custom regex rules configurable via YAML
- 3-tier severity classification: BLOCKED (pipeline fails), WARNING (needs review), APPROVED (known-safe)
- Baseline filtering to suppress known/accepted findings
- VCS commenting (GitHub PR / GitLab MR)

Severity mapping to plugin classification:
| security-scan | Plugin Severity |
|---|---|
| BLOCKED | CRITICAL / HIGH |
| WARNING | MEDIUM |
| APPROVED | LOW |

Install: `pip install security-scan` (requires `gitleaks` binary on PATH)

### Secure Secrets Storage

```python
import os
from dotenv import load_dotenv

# Load from .env file (not committed to git)
load_dotenv()

# Get secrets from environment
API_KEY = os.getenv('EXTERNAL_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if not API_KEY:
    raise ValueError("EXTERNAL_API_KEY environment variable not set")

# For production, use secrets management service
# AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager
try:
    import boto3
    secrets_client = boto3.client('secretsmanager')
    secret = secrets_client.get_secret_value(SecretId='prod/api/keys')
    API_KEY = json.loads(secret['SecretString'])['external_api_key']
except Exception:
    pass  # Fallback to environment variable
```

Secret rotation policy:
- API keys: Rotate every 90 days
- Database passwords: Rotate every 60 days
- Service account keys: Rotate every 30 days
- SSL/TLS certificates: Monitor expiration, renew 30 days before

## Threat Modeling

### STRIDE Methodology

For each component in the system, evaluate:

| Threat | Description | Example Mitigation |
|--------|-------------|-------------------|
| **Spoofing** | Impersonating a user or system | MFA, OAuth2/OIDC, certificate-based auth |
| **Tampering** | Modifying data or code | HMAC signatures, code signing, integrity checks |
| **Repudiation** | Denying an action occurred | Audit logs, immutable logging, timestamps |
| **Information Disclosure** | Exposing sensitive data | Encryption at rest/in transit, data classification |
| **Denial of Service** | Making a service unavailable | Rate limiting, WAF, auto-scaling, circuit breakers |
| **Elevation of Privilege** | Gaining unauthorized access | RBAC, least privilege, input validation |

### Trust Assessment for Agent Operations

```python
class TaskRisk(Enum):
    LOW = "low"          # Read-only, reversible
    MEDIUM = "medium"    # Modifies files, testable
    HIGH = "high"        # Production impact, external systems
    CRITICAL = "critical"  # Security, data loss potential

# High-risk keywords that trigger elevated assessment
HIGH_RISK_KEYWORDS = [
    "delete", "remove", "drop", "production", "deploy",
    "migrate", "security", "password", "credential",
    "secret", "api_key", "database", "schema",
]
```

Risk-based approval requirements:
- **LOW risk**: Supervised execution, no approval needed
- **MEDIUM risk**: Approval-gated, review before execution
- **HIGH risk**: Monitored execution, requires explicit approval
- **CRITICAL risk**: Zero-touch only with full human oversight

### Attack Surface Analysis

For every application, document:

1. **Entry points**: APIs, web forms, file uploads, webhooks, message queues
2. **Trust boundaries**: Internal vs external networks, user vs admin, service-to-service
3. **Data flows**: Where sensitive data enters, is processed, stored, and transmitted
4. **Dependencies**: Third-party libraries, external services, shared infrastructure
