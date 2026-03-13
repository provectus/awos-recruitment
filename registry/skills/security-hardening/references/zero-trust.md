## Zero Trust Architecture

### Core Principles

1. **Never trust, always verify** - Authenticate and authorize every request
2. **Least privilege access** - Grant minimum permissions needed for each operation
3. **Assume breach** - Design systems to limit blast radius when compromise occurs
4. **Continuous verification** - Validate identity and posture continuously, not just at login

### Implementation Patterns

```python
# Trust ladder for progressive agent autonomy
class TrustLevel(Enum):
    SUPERVISED = 1      # Human reviews every action
    APPROVAL_GATED = 2  # Human approves before execution
    MONITORED = 3       # Autonomous with real-time monitoring
    AUTONOMOUS = 4      # Full autonomy with periodic audits
    ZERO_TOUCH = 5      # Complete trust with compliance guardrails
```

### Trust Assessment Engine

Automated trust level assessment based on task risk:

- Evaluate task keywords against risk dictionaries (delete, deploy, migrate, credential, etc.)
- Score task complexity using architecture, integration, and scope indicators
- Assign trust level dynamically based on combined risk and complexity score
- Enforce approval gates when trust level exceeds the agent's current authorization

### Agent Sandboxing and Hardening

Production security for autonomous agents:

- Sandbox agent execution with restricted filesystem, network, and process access
- Enforce permission boundaries: agents cannot escalate beyond their assigned trust level
- Isolate agent sessions to prevent cross-contamination between tasks
- Implement resource limits (CPU, memory, execution time) for agent processes
- Audit all agent actions with immutable logging for post-incident analysis

Access control enforcement:
- Identity-based access with strong authentication (OAuth 2.0/OIDC, WebAuthn, FIDO2)
- Context-aware policies (device posture, location, time, risk score)
- Micro-segmentation for network access
- Just-in-time and just-enough-access for privileged operations
- Continuous session validation with re-authentication triggers

### Micro-Segmentation Example

```yaml
# Kubernetes NetworkPolicy — restrict backend pods to only accept traffic from API gateway
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-allow-gateway-only
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes: ["Ingress"]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - port: 8080
```

### Just-In-Time Access Pattern

```python
# Grant temporary elevated access with automatic expiry
def grant_jit_access(user_id: str, role: str, duration_minutes: int = 30):
    expiry = datetime.utcnow() + timedelta(minutes=duration_minutes)
    grant = AccessGrant(user_id=user_id, role=role, expires_at=expiry)
    db.session.add(grant)
    audit_log.info("jit_access_granted", user=user_id, role=role, expires=expiry)
    return grant

# Middleware checks expiry on every request
def check_jit_access(user_id: str, required_role: str) -> bool:
    grant = AccessGrant.query.filter_by(
        user_id=user_id, role=required_role
    ).first()
    if not grant or grant.expires_at < datetime.utcnow():
        return False
    return True
```
