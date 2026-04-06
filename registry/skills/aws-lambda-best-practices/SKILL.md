---
name: aws-lambda-best-practices
description: >-
  AWS Lambda best practices for function design, configuration, and operations. Use when
  designing Lambda functions, choosing memory/timeout settings, planning concurrency and
  scaling, setting up monitoring, processing streams, or securing Lambda workloads. Triggers
  on tasks involving Lambda function creation, handler design, cold start optimization,
  idempotency, event source mapping, reserved/provisioned concurrency, or deciding whether
  Lambda is the right compute choice. Does not cover language-specific SDK patterns,
  CloudFormation/Terraform resource definitions, or Lambda@Edge.
version: 0.1.0
---

# AWS Lambda Best Practices

Opinionated, language-agnostic conventions for designing and operating Lambda functions at scale. For SDK/API usage, infrastructure-as-code definitions, or language-specific handler patterns, consult the relevant AWS SDK or Terraform documentation instead.

## Is Lambda the Right Choice?

Lambda is not a general-purpose compute service -- it excels at event-driven, short-lived, stateless workloads. Evaluate fit before committing.

| Requirement | Lambda fit | Better alternative |
|---|---|---|
| Event-driven, bursty traffic | Excellent | -- |
| Execution < 15 minutes | Good | ECS/Fargate for longer tasks |
| Stateless request/response | Excellent | -- |
| Persistent connections (WebSockets) | Poor | API Gateway WebSocket + ECS |
| Predictable, steady-state high throughput | Evaluate cost | ECS/Fargate or EC2 |
| GPU or specialized hardware | Not supported | EC2 or SageMaker |
| Large deployment artifact (> 10 GB) | Container image limit | ECS/Fargate |
| Sub-millisecond latency | Cold starts add latency | EC2 or containers |

See `references/anti-patterns.md` for detailed analysis of each anti-pattern with migration strategies.

## Architecture Anti-Patterns -- When Lambda Feels Right But Isn't

Even when Lambda appears to fit, certain architectural patterns lead to fragile, costly, or unmaintainable systems. Recognize these before committing.

| Anti-pattern | Signal | What to use instead |
|---|---|---|
| **Lambda monolith** | One function handles all routes/event types | Decompose: one function per task |
| **Lambda as orchestrator** | Function has more workflow logic than business logic | AWS Step Functions for workflows; EventBridge across services |
| **Lambda calling Lambda** | Function synchronously invokes another function and waits | SQS between functions; Step Functions for orchestration |
| **Recursive invocation loop** | Function writes to the same resource that triggered it | Separate source and destination resources |
| **Synchronous waiting** | Function runs 3+ independent operations sequentially | Concurrent execution or event-driven split |

### Quick self-check

If any of these are true, reconsider your design:
- Your function's IAM role needs broad wildcards because it does too many things
- Your function's timeout must be 15 minutes because it chains through multiple steps
- Your function has more `if/else/try/catch` orchestration than business logic
- Your function invokes other Lambda functions with `invoke()` and waits for the response
- Your function writes output to the same S3 bucket / SQS queue / DynamoDB table that triggered it

See `references/anti-patterns.md` for detailed analysis of each anti-pattern with migration strategies.

## Function Code

### Handler design -- separate logic from plumbing

The handler is the entry point. Keep it thin:

1. **Parse and validate** the incoming event
2. **Delegate** to business logic (pure functions, testable independently)
3. **Return** a well-structured response

### Execution environment reuse

Initialize SDK clients, database connections, and heavy resources **outside** the handler. Lambda reuses the execution environment across invocations -- resources initialized at module level persist.

```
# GOOD: initialized once, reused across invocations
db_client = create_db_client()

def handler(event, context):
    return db_client.query(event["id"])

# BAD: new connection every invocation
def handler(event, context):
    db_client = create_db_client()
    return db_client.query(event["id"])
```

### Idempotency -- design for at-least-once delivery

Lambda guarantees at-least-once invocation. Your function **will** receive duplicate events. Design accordingly:

- Use a unique event identifier (request ID, message ID) as an idempotency key
- Store the key in DynamoDB or a similar store before processing
- On duplicate, return the cached result instead of re-processing
- Consider using Powertools for AWS Lambda idempotency utilities

### Persistent connections

Use keep-alive directives to maintain connections between invocations. Lambda purges idle connections -- attempting to reuse a stale connection causes errors.

See `references/function-code.md` for recursive invocation prevention, environment variable usage, and security implications of execution environment reuse.

## Function Configuration

### Memory and CPU -- they are linked

Lambda allocates CPU proportional to memory. At **1,769 MB**, a function gets one full vCPU.

| Memory | CPU | Best for |
|---|---|---|
| 128-512 MB | Fractional vCPU | Simple transforms, routing |
| 512-1,769 MB | Up to 1 vCPU | API handlers, moderate processing |
| 1,769-3,008 MB | 1-2 vCPU | Data processing, image manipulation |
| 3,008-10,240 MB | 2-6 vCPU | ML inference, heavy computation |

**Always performance-test** to find the optimal memory setting. Use the open-source [AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning) tool to find the best price/performance balance.

### Timeout -- set deliberately, not defensively

| Guideline | Why |
|---|---|
| Set timeout to expected duration + buffer, not max (900s) | Prevents runaway invocations from accumulating cost and concurrency |
| Load-test to measure actual duration under load | Network calls to downstream services can slow under concurrency |
| For SQS triggers, keep timeout < Visibility Timeout | Prevents duplicate processing |

### Key quotas to remember

| Resource | Limit | Notes |
|---|---|---|
| Max execution time | 15 minutes | Hard limit |
| Payload (sync) | 6 MB request / 6 MB response | 200 MB for streamed responses |
| Payload (async) | 1 MB | -- |
| Deployment package (.zip) | 50 MB zipped / 250 MB unzipped | Use S3 for larger uploads |
| Container image | 10 GB | -- |
| `/tmp` storage | 512 MB - 10,240 MB | Configurable |
| Environment variables | 4 KB total | Aggregate across all variables |
| Concurrent executions | 1,000 default | Soft limit, increase via Service Quotas |
| Layers | 5 per function | -- |

See `references/function-configuration.md` for IAM policy guidance, SQS integration, quota management, and cleanup best practices.

## Function Scalability

### Concurrency model

```
Concurrency = (requests per second) x (average duration in seconds)
```

100 RPS with 200ms average duration = 20 concurrent executions.

### Concurrency controls

| Control | What it does | Cost | Use case |
|---|---|---|---|
| **Unreserved** (default) | Shares account pool (1,000 default) | Free | Most functions |
| **Reserved concurrency** | Guarantees AND caps concurrency for a function | Free | Protect critical functions; throttle to protect downstream |
| **Provisioned concurrency** | Pre-initializes execution environments | Additional charge | Eliminate cold starts for latency-sensitive workloads |

### Scaling rate

Lambda scales at **1,000 new execution environments every 10 seconds** per function. For sudden traffic spikes:

- Use provisioned concurrency to absorb initial burst
- Implement retries with exponential backoff and jitter in callers
- Set reserved concurrency to protect downstream services from overload

### Upstream/downstream awareness

Lambda scales automatically -- your dependencies may not. Common bottlenecks:

| Dependency | Risk | Mitigation |
|---|---|---|
| RDS / relational DB | Connection pool exhaustion | Use RDS Proxy |
| API Gateway | 10,000 RPS default throttle | Request quota increase; match Lambda concurrency |
| DynamoDB (provisioned) | Throttled reads/writes | Switch to on-demand or match WCU/RCU to expected concurrency |
| SQS | N/A (scales with Lambda) | -- |
| Third-party APIs | Rate limits | Use reserved concurrency to cap Lambda scaling |

See `references/function-scalability.md` for provisioned concurrency scheduling, throttle tolerance patterns, and concurrency estimation.

## Metrics and Alarms

### Use CloudWatch metrics, not in-function metrics

Never call the CloudWatch `PutMetricData` API from your handler. Instead:

- Use **Embedded Metric Format (EMF)** -- emit metrics through structured logs, zero API call overhead
- Use **Powertools for AWS Lambda Metrics** utility to handle EMF formatting automatically
- Set CloudWatch Alarms on built-in Lambda metrics

### Key metrics to alarm on

| Metric | Alarm condition | What it catches |
|---|---|---|
| `Errors` | > 0 for N minutes | Function failures |
| `Throttles` | > 0 | Hitting concurrency limits |
| `Duration` | p99 > threshold | Latency degradation, downstream slowness |
| `ConcurrentExecutions` | > 80% of reserved | Approaching concurrency ceiling |
| `IteratorAge` (streams) | > 30,000 ms | Falling behind on stream processing |
| `DeadLetterErrors` | > 0 | DLQ delivery failures |

### Observability best practices

| Practice | Why |
|---|---|
| Structured JSON logging | Enables search, filter, and analysis in CloudWatch Logs Insights |
| Correlation IDs across services | Trace requests end-to-end in distributed systems |
| AWS Cost Anomaly Detection | Catches runaway Lambda costs within 24 hours |
| X-Ray tracing | Visualize latency across Lambda and downstream services |

See `references/metrics-and-alarms.md` for EMF details, structured logging guidance, and cost anomaly detection setup.

## Working with Streams

### Batch tuning -- the critical lever

| Setting | Default | Guidance |
|---|---|---|
| `BatchSize` | 100 (Kinesis), 10 (SQS) | Larger batches amortize invocation overhead; test for your workload |
| `MaximumBatchingWindowInSeconds` | 0 | Set up to 5 min to buffer small batches; reduces invocations at cost of latency |
| Payload limit | 6 MB | Batches are capped at 6 MB regardless of `BatchSize` |

### Partial batch response -- avoid reprocessing successes

Enable `ReportBatchItemFailures` to retry **only failed records** instead of the entire batch. Without this, one failed record causes the entire batch to be retried.

### Stream scaling

| Stream type | Scaling lever | Concurrency model |
|---|---|---|
| Kinesis | Add shards | 1 Lambda invocation per shard (default); up to 10 with parallelization factor |
| DynamoDB Streams | Add partitions (indirect) | 1 Lambda invocation per shard |
| SQS | Automatic | Lambda scales pollers up to concurrency limit |

### Idempotency is critical for streams

Event source mappings guarantee **at-least-once** delivery. Duplicate processing will occur. Every stream-processing function must be idempotent.

See `references/stream-events.md` for Kinesis shard management, IteratorAge monitoring, parallelization factor, and partition key design.

## Security

### IAM -- least privilege, always

| Principle | Implementation |
|---|---|
| Narrow execution role | Grant only the specific actions and resources the function needs |
| No wildcards in production | `s3:GetObject` on specific bucket, not `s3:*` on `*` |
| Separate roles per function | Avoid sharing execution roles across functions with different responsibilities |
| Use resource-based policies | Control who can invoke your function |

### Runtime security

| Practice | Why |
|---|---|
| Code signing | Verify deployment artifact integrity; prevent unauthorized code changes |
| VPC placement | Required for accessing private resources; adds cold start latency |
| Security Hub controls | Automated CSPM checks against Lambda configurations |
| GuardDuty Lambda Protection | Monitors network activity for threats (crypto mining, C2 communication) |
| Secrets Manager / Parameter Store | Never hardcode secrets; use environment variable references to secrets |

### Data protection

| Layer | Mechanism |
|---|---|
| In transit | All Lambda APIs use TLS |
| At rest (env vars) | Encrypted with AWS KMS by default; use customer-managed CMK for sensitive data |
| At rest (code) | Stored encrypted in S3 |
| `/tmp` storage | Ephemeral, isolated per execution environment |

See `references/security.md` for VPC configuration trade-offs, code signing setup, and governance strategies.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Initializing SDK clients inside the handler | Move to module/global scope for execution environment reuse |
| Setting timeout to 15 minutes "just in case" | Set to expected duration + reasonable buffer; load test |
| Ignoring cold starts for user-facing APIs | Use provisioned concurrency or optimize package size |
| Not designing for idempotency | Use idempotency keys with DynamoDB or Powertools |
| Recursive invocations (function triggers itself) | Set reserved concurrency to 0 immediately; fix the loop |
| Hardcoding resource names | Use environment variables |
| Wildcard IAM permissions | Grant specific actions on specific resources |
| Not monitoring IteratorAge on streams | Alarm at 30s; add shards or increase parallelization |
| Retrying the full batch on partial failure | Enable `ReportBatchItemFailures` |
| Over-provisioning memory without testing | Use Lambda Power Tuning to find optimal setting |
| Single function handling all API routes (monolith) | Decompose to one function per route/task |
| Writing workflow orchestration logic in a Lambda handler | Use Step Functions for branching, retries, wait states |
| Lambda function synchronously invoking another Lambda | Decouple with SQS or orchestrate with Step Functions |
| Sequential independent operations in one function | Run concurrently or split into event-driven chain |

## Reference Files

- **`references/anti-patterns.md`** -- Lambda monolith, Lambda as orchestrator, synchronous chains, recursive loops, synchronous waiting, decision matrix
- **`references/function-code.md`** -- Handler design, execution environment reuse, idempotency patterns, connection management, recursive invocation prevention
- **`references/function-configuration.md`** -- Memory/CPU tuning, timeout strategy, quotas, IAM policies, SQS integration, cleanup
- **`references/function-scalability.md`** -- Concurrency model, reserved vs provisioned concurrency, scaling rate, upstream/downstream protection, throttle tolerance
- **`references/metrics-and-alarms.md`** -- CloudWatch metrics, EMF, structured logging, alarms, Cost Anomaly Detection, X-Ray tracing
- **`references/stream-events.md`** -- Batch tuning, partial batch response, Kinesis/DynamoDB Streams/SQS scaling, IteratorAge monitoring
- **`references/security.md`** -- IAM least privilege, code signing, VPC trade-offs, data protection, Security Hub, GuardDuty
