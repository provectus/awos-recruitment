# Function Code Best Practices

## Handler Design Principles

The handler is Lambda's entry point. A well-designed handler is thin, testable, and separates concerns:

```
Module level:  initialize DB client, validator (reused across invocations)

Handler:
  1. Validate incoming event
  2. Call business logic (pure function, no Lambda dependencies)
  3. Return structured response
```

### Why this matters

- **Testability** -- business logic in pure functions can be unit-tested without mocking Lambda
- **Portability** -- if you later move to ECS or another compute, the business logic doesn't change
- **Readability** -- the handler reads as a pipeline: input -> process -> output

### Anti-pattern: fat handler

```
Handler:
  Create new DB connection           <-- re-created every invocation
  If event type is "order":          <-- routing logic in handler
    50 lines of validation...
    80 lines of business logic...
    30 lines of error handling...
    Write to DB                      <-- data access mixed in
    Send email                       <-- side effects buried deep
    Catch all exceptions --> 500     <-- generic catch-all hides real errors
```

This is untestable, unreusable, and impossible to reason about when it grows. Split validation, business logic, and data access into separate modules.

## Execution Environment Reuse

Lambda may reuse the execution environment (the container running your function) across invocations. This is called a "warm start."

### What persists between invocations

| Resource | Persists? | Notes |
|---|---|---|
| Global/module-level variables | Yes | Use for SDK clients, DB connections, config |
| `/tmp` directory contents | Yes | Up to configured size (512 MB - 10 GB) |
| Background processes | Yes, but risky | Lambda may freeze/thaw the environment |
| Handler-local variables | No | Fresh each invocation |

### Best practices

- **Initialize expensive resources at module level** -- SDK clients, database connection pools, configuration loading, static asset caching
- **Cache in `/tmp`** -- downloaded files, compiled templates, ML model weights
- **Never store user-specific state in globals** -- this leaks data between invocations from different users
- **Don't rely on reuse** -- your code must work correctly on cold starts too

### Cold start impact

| Factor | Impact on cold start |
|---|---|
| Package size | Larger package = longer initialization |
| Number of imports/dependencies | More imports = longer module-level execution |
| VPC attachment | Adds ENI setup time on first invocation; significantly reduced since Hyperplane ENI improvements (seconds, not minutes) |
| Runtime | Interpreted languages (Python, Node.js) generally start faster than compiled (Java, .NET) |
| Provisioned concurrency | Eliminates cold starts entirely (at additional cost) |

## Idempotency

Lambda provides **at-least-once** invocation semantics. Your function will receive duplicate events in the following scenarios:

- Async invocation retries (up to 2 retries by default)
- Stream event source mapping reprocessing on failure
- SQS visibility timeout expiry causing redelivery
- Network issues between Lambda and your function

### Implementing idempotency

1. **Extract an idempotency key** from the event (request ID, message ID, transaction ID)
2. **Check if already processed** -- look up the key in a persistent store (DynamoDB is common)
3. **If new, process and store the result** with the key
4. **If duplicate, return the stored result** without reprocessing

### Idempotency key selection

| Event source | Good idempotency key |
|---|---|
| API Gateway | `requestContext.requestId` or a client-supplied header |
| SQS | `messageId` |
| SNS | `Sns.MessageId` |
| Kinesis | `eventID` or a composite of `partitionKey` + `sequenceNumber` |
| DynamoDB Streams | `eventID` |
| S3 | Bucket + key + versionId |
| EventBridge | `id` |

### Operations that are naturally idempotent

Some operations don't need explicit idempotency handling:

- **Upserts** -- writing the same value to the same key
- **S3 PutObject** with deterministic content -- same content to same key
- **DynamoDB PutItem** with same attributes -- overwrites with identical data

Operations that are **not** naturally idempotent:

- Counter increments (`UpdateItem` with `ADD`)
- Sending emails or notifications
- Financial transactions
- Appending to a list

## Connection Management

### Keep-alive directives

Lambda reuses execution environments, but idle connections get purged. Without keep-alive, you get connection errors on warm starts.

- Enable TCP keep-alive in your HTTP client configuration
- Set appropriate idle timeout (shorter than Lambda's purge interval)
- Most AWS SDKs enable keep-alive by default in recent versions -- verify your SDK version

### Database connections

| Pattern | Verdict | When to use |
|---|---|---|
| Module-level connection + RDS Proxy | Best | Any function connecting to RDS with non-trivial concurrency |
| Module-level connection (no proxy) | Good | Low-concurrency functions with simple connection needs |
| Connection per invocation | Avoid for concurrent workloads | Acceptable only for very-low-concurrency functions that run infrequently |
| HTTP-based services (DynamoDB, S3, SQS) | No pooling needed | SDK handles connection management |

### RDS Proxy

For relational databases with non-trivial concurrency, **use RDS Proxy** with Lambda:

- Pools and shares database connections across function instances
- Handles connection cleanup when Lambda scales down
- Supports IAM authentication (no passwords in config)
- Without it: 1,000 concurrent Lambda invocations = 1,000 database connections

For low-concurrency functions (e.g., cron jobs, admin tools), a module-level connection without RDS Proxy is acceptable and avoids the additional cost.

## Recursive Invocations

See `anti-patterns.md` for full analysis of why recursive patterns feel right, impact tables, and safeguards. This section provides a quick prevention checklist.

A recursive invocation occurs when a Lambda function directly or indirectly triggers itself:

- Function writes to an S3 bucket -> S3 event triggers the same function
- Function publishes to an SNS topic -> SNS triggers the same function
- Function writes to a DynamoDB table -> DynamoDB Stream triggers the same function

### Prevention

- **Design the trigger and output to use different resources** -- write to a different bucket/table than the one triggering the function
- **Use prefixes or suffixes** -- trigger on `input/` prefix, write to `output/` prefix
- **Add a recursion guard** -- check for a recursion marker in the event and bail out
- **Emergency stop** -- if detected, set reserved concurrency to 0 immediately to halt all invocations while you fix the code
- **Lambda recursive loop detection** -- Lambda automatically detects and stops recursive loops between Lambda, SQS, and SNS (limited scope -- do not rely on this as sole protection)

## Environment Variables

| Guideline | Why |
|---|---|
| Use env vars for operational parameters | Bucket names, table names, API endpoints, feature flags |
| Never hardcode resource identifiers | Enables multi-environment deployment (dev/staging/prod) |
| Don't store secrets in plain-text env vars | Use Secrets Manager or Parameter Store with env var references |
| Total env var size limit is 4 KB | For larger config, use Parameter Store or S3 |
| Env vars are encrypted at rest with KMS | Use a customer-managed CMK for sensitive values |
