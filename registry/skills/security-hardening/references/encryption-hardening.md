## Encryption and Data Protection

### TLS Configuration

```nginx
# Recommended TLS configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_stapling on;
ssl_stapling_verify on;
```

### Security Headers

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 0
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

### Password Hashing

```python
from werkzeug.security import generate_password_hash, check_password_hash

def create_user(username, password):
    validate_password_strength(password)
    password_hash = generate_password_hash(
        password,
        method='pbkdf2:sha256',
        salt_length=16
    )
    user = User(username=username, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()
```

Password policy:
- Minimum 12 characters
- Must include uppercase, lowercase, number, and special character
- Account lockout after 5 failed attempts for 30 minutes
- No password reuse for last 12 passwords

## Rate Limiting and DoS Protection

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"],
    storage_uri="redis://localhost:6379"
)

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    # Authentication logic

@app.route('/api/search')
@limiter.limit("30 per minute")
def search():
    # Search logic
```

## Security Audit Logging

### What to Log

- Authentication attempts (success and failure)
- Authorization failures and privilege escalation attempts
- Data access to sensitive resources
- Configuration changes to security controls
- API key creation, rotation, and revocation
- User account lifecycle events (creation, modification, deletion)
- File upload and download of sensitive data

### Log Format

```json
{
  "timestamp": "2025-12-09T14:32:01Z",
  "level": "SECURITY",
  "event": "AUTH_FAILURE",
  "actor": "user@example.com",
  "action": "login",
  "resource": "/api/auth/login",
  "outcome": "failure",
  "reason": "invalid_password",
  "ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "metadata": {
    "failed_attempts": 3,
    "account_locked": false
  }
}
```

## Risk Classification for Code Changes

Automated risk scoring for pull requests and code changes:

- Classify code changes by risk level (LOW, MEDIUM, HIGH, CRITICAL) based on files modified, keywords present, and scope of change
- Flag changes touching authentication, authorization, encryption, or database schema as elevated risk
- Integrate security scanner module for automated vulnerability detection on changed files
- Generate risk reports that feed into approval workflows and deployment gates

## Security Audit Workflow Formulas

Structured audit workflows using formula-based automation:

- Define repeatable security audit steps as workflow formulas
- Chain scanning, analysis, and reporting steps into automated audit pipelines
- Track audit findings across iterations with status tracking (open, in-progress, mitigated, accepted)
- Generate compliance evidence artifacts from audit runs

## Security Checklist

- [ ] Use HTTPS for all communications
- [ ] Hash passwords with bcrypt/Argon2
- [ ] Use parameterized queries for all database operations
- [ ] Validate and sanitize all input
- [ ] Implement proper authentication with MFA
- [ ] Implement proper authorization with RBAC
- [ ] Use CSRF tokens for state-changing operations
- [ ] Set secure cookie flags (HttpOnly, Secure, SameSite)
- [ ] Implement rate limiting on sensitive endpoints
- [ ] Keep dependencies updated with automated scanning
- [ ] Use environment variables for secrets
- [ ] Implement security event logging and monitoring
- [ ] Configure security headers (CSP, HSTS, X-Frame-Options)
- [ ] Sanitize error messages to prevent information leakage
- [ ] Implement account lockout after failed attempts
- [ ] Validate file uploads by type, size, and content
- [ ] Use Content Security Policy to prevent XSS
- [ ] Implement proper session management with timeouts
