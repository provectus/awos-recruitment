## OWASP Top 10 Protection

### A01: Broken Access Control

```python
from functools import wraps
from flask import g, request, jsonify

def require_permission(permission):
    """Decorator to check user permissions."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not g.current_user:
                return jsonify({'error': 'Authentication required'}), 401
            if not g.current_user.has_permission(permission):
                logger.warning(
                    f"Unauthorized access attempt: {g.current_user.id} "
                    f"to {request.path}"
                )
                return jsonify({'error': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/api/orders/<order_id>')
@login_required
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    # Verify user owns this order or is admin
    if order.user_id != g.current_user.id and not g.current_user.is_admin:
        logger.warning(
            f"Unauthorized order access: User {g.current_user.id} "
            f"attempted to access order {order_id}"
        )
        return jsonify({'error': 'Access denied'}), 403
    return jsonify(order.to_dict())
```

### A02: Cryptographic Failures

- Use HTTPS/TLS for all communications
- Encrypt sensitive data with AES-256-GCM at rest
- Use strong password hashing (bcrypt, Argon2)
- Implement key rotation with a 30-day cycle
- Store encryption keys in HSM or KMS, never in code

### A03: Injection

```python
from sqlalchemy import text

# ALWAYS use parameterized queries
sql = text("SELECT id, username, email FROM users WHERE username LIKE :query")
users = db.engine.execute(sql, {'query': f'%{query}%'}).fetchall()

# Or use ORM (automatically parameterized)
users = User.query.filter(User.username.like(f'%{query}%')).all()
```

Input validation rules:
- Validate all user input against allowlists
- Sanitize input before use in any context (SQL, HTML, OS commands, LDAP)
- Limit input length and size
- Validate file uploads by type, size, and content (magic bytes)
- Escape output for the rendering context (HTML, JavaScript, URL, CSS)

### A04: Insecure Design

- Apply threat modeling during design phase (STRIDE, PASTA)
- Implement defense in depth with multiple security layers
- Use secure design patterns (fail-safe defaults, complete mediation)
- Define security requirements alongside functional requirements

### A05: Security Misconfiguration

Common misconfigurations to check:
- Default credentials still active
- Unnecessary features or services enabled
- Error messages that leak internal details
- Missing security headers (CSP, HSTS, X-Frame-Options)
- Overly permissive CORS configuration
- Debug mode enabled in production
- Directory listing enabled on web servers

### A06: Vulnerable and Outdated Components

```bash
# Automated dependency auditing
npm audit --audit-level=high          # Node.js
pip-audit --strict --desc             # Python
govulncheck ./...                     # Go
trivy image --severity HIGH,CRITICAL  # Container images
```

- Pin dependency versions in lock files
- Enable Dependabot or Renovate for automated updates
- Remove unused dependencies to reduce attack surface

### A07: Identification and Authentication Failures

```python
# Enforce strong session management
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
```

- Require MFA for privileged operations
- Implement account lockout after 5 failed attempts
- Use bcrypt/Argon2 (never MD5/SHA1 for passwords)

### A08: Software and Data Integrity Failures

```yaml
# Pin GitHub Actions to commit SHA, not tags
- uses: actions/checkout@8ade135a41bc03ea155e62e844d188df1ea18608  # v4.1.1
```

- Generate SBOM with `syft` or `cyclonedx-cli`
- Verify package signatures and checksums
- Use Sigstore/cosign for container image signing

### A09: Security Logging and Monitoring Failures

```python
# Log security events with structured fields
logger.warning("auth_failure", extra={
    "event": "LOGIN_FAILED",
    "user": username,
    "ip": request.remote_addr,
    "reason": "invalid_credentials"
})
```

- Centralize logs with SIEM integration
- Alert on authentication failures, privilege escalation, and anomalous access
- Retain logs per compliance requirements (SOC 2: 1 year, PCI: 1 year, HIPAA: 6 years)

### A10: Server-Side Request Forgery (SSRF)

```python
# Validate URLs against allowlist
ALLOWED_HOSTS = {"api.example.com", "cdn.example.com"}

def fetch_url(url: str):
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed: {parsed.hostname}")
    if parsed.scheme not in ("https",):
        raise ValueError("Only HTTPS allowed")
    return requests.get(url, allow_redirects=False, timeout=5)
```

- Block requests to internal/private IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x)
- Disable HTTP redirects on server-side requests
- Use network segmentation to isolate backend services
