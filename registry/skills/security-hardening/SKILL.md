---
name: security-hardening
description: >-
  Application security best practices. Use when performing security audits,
  vulnerability scanning, threat modeling, secrets management, compliance checks
  (GDPR, SOC 2, PCI-DSS, HIPAA), OWASP Top 10 remediation, Zero Trust
  architecture, encryption setup, or code security reviews.
version: 0.1.0
---

# Security Hardening

Production-tested security patterns covering vulnerability scanning, secrets management, OWASP Top 10 protection, compliance frameworks, Zero Trust architecture, and encryption hardening.

## OWASP Top 10 — Code-Level Patterns

### A01: Broken Access Control

Always verify ownership, not just authentication:

```python
@app.route('/api/orders/<order_id>')
@login_required
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != g.current_user.id and not g.current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    return jsonify(order.to_dict())
```

### A03: Injection

Always use parameterized queries:

```python
# CORRECT — parameterized
sql = text("SELECT id, username FROM users WHERE username LIKE :query")
users = db.engine.execute(sql, {'query': f'%{query}%'}).fetchall()

# CORRECT — ORM (automatically parameterized)
users = User.query.filter(User.username.like(f'%{query}%')).all()
```

Input validation rules:
- Validate against allowlists, not blocklists
- Limit input length and file upload size
- Validate file uploads by magic bytes, not extension
- Escape output for rendering context (HTML, JS, URL, CSS)

### A05: Security Misconfiguration

Check for:
- Default credentials still active
- Debug mode enabled in production
- Missing security headers (CSP, HSTS, X-Frame-Options)
- Overly permissive CORS
- Directory listing enabled
- Error messages leaking internals

### A06: Vulnerable Components

```bash
npm audit --audit-level=high          # Node.js
pip-audit --strict --desc             # Python
govulncheck ./...                     # Go
trivy image --severity HIGH,CRITICAL  # Container images
```

Pin versions in lock files. Enable Dependabot or Renovate. Remove unused dependencies.

## Vulnerability Scanning

### SAST (Static Analysis)

```yaml
# CodeQL in GitHub Actions
- name: Initialize CodeQL
  uses: github/codeql-action/init@v3
  with:
    languages: ${{ matrix.language }}
    queries: +security-extended,security-and-quality
- name: Perform CodeQL Analysis
  uses: github/codeql-action/analyze@v3
```

```yaml
# Bandit for Python
- name: Run Bandit
  run: bandit -r src/ -ll -ii -f json -o bandit-report.json
```

Tools by language:
- **Python**: Bandit, Semgrep, CodeQL
- **JavaScript/TypeScript**: ESLint security plugin, Semgrep, CodeQL
- **Go**: gosec, staticcheck
- **Java**: SpotBugs + FindSecBugs, PMD

### Dependency Scanning

```yaml
# Dependabot configuration
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly" }
  - package-ecosystem: "npm"
    directory: "/"
    schedule: { interval: "weekly" }
  - package-ecosystem: "docker"
    directory: "/"
    schedule: { interval: "weekly" }
```

## Secrets Management

### Detection Patterns

```
AWS Access Key:       AKIA[0-9A-Z]{16}
AWS Secret Key:       [0-9a-zA-Z/+]{40}
GitHub Token:         gh[pousr]_[0-9a-zA-Z]{36}
GitLab Token:         glpat-[0-9a-zA-Z\-]{20}
Private Key:          -----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----
JWT Token:            eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+
Database URL:         (postgres|mysql|mongodb)://[^\s]+:[^\s]+@
```

### Files to Always Exclude

```gitignore
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

### Secure Storage

Use environment variables for development, secrets managers for production (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager). Never commit secrets to git.

## Compliance Frameworks

Detailed checklists in `references/compliance-frameworks.md`:
- **GDPR**: DPA, DSAR, consent, breach notification, data retention
- **SOC 2 Type II**: Access controls, change management, incident response
- **PCI-DSS**: CDE segmentation, cardholder encryption, monitoring
- **HIPAA**: PHI encryption, RBAC, audit logging, BAAs
- **ISO 27001**: ISMS, risk assessment, asset inventory
- **NIST CSF**: Identify, Protect, Detect, Respond, Recover

## Zero Trust Architecture

### Core Principles

1. **Never trust, always verify** — authenticate every request
2. **Least privilege** — minimum permissions per operation
3. **Assume breach** — limit blast radius
4. **Continuous verification** — validate identity continuously

### Implementation

- Identity-based access with OAuth 2.0/OIDC, WebAuthn
- Context-aware policies (device posture, location, risk score)
- Micro-segmentation for network access
- Just-in-time access with automatic expiry

## Encryption and Hardening

### TLS Configuration

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
ssl_prefer_server_ciphers off;
ssl_stapling on;
```

### Security Headers

```
Content-Security-Policy: default-src 'self'; script-src 'self'; frame-ancestors 'none'
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Password Policy

- Minimum 12 characters, mixed case + number + special
- Use bcrypt or Argon2 for hashing
- Account lockout after 5 failures for 30 minutes
- No reuse of last 12 passwords

## Threat Modeling

Use STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) or PASTA for systematic threat analysis. Score threats by risk and complexity. Apply defense in depth with multiple security layers.

## Deep Dives

| Topic | Reference |
|---|---|
| OWASP Top 10 with full code examples | `references/owasp-patterns.md` |
| Vulnerability scanning setup (SAST, DAST, Trivy) | `references/vulnerability-scanning.md` |
| Secrets detection, rotation, threat modeling | `references/secrets-threats.md` |
| Zero Trust, agent sandboxing, micro-segmentation | `references/zero-trust.md` |
| GDPR, SOC 2, PCI-DSS, HIPAA checklists | `references/compliance-frameworks.md` |
| TLS, headers, hashing, rate limiting, audit logging | `references/encryption-hardening.md` |
