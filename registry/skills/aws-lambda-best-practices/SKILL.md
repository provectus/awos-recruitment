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

Lambda excels at event-driven, short-lived, stateless workloads. Evaluate fit before committing.

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

## Function Design

**One function per responsibility.** Scope by event source or business operation. Keep the handler thin: validate input, delegate to business logic (pure functions), return a structured response. Initialize SDK clients and connections at module level -- Lambda reuses the execution environment across invocations.

**Don't:** build a Lambda monolith (all routes in one function), inline business logic in the handler, or create connections inside the handler.

**Idempotency is mandatory.** Lambda guarantees at-least-once invocation -- your function will receive duplicates. Use an idempotency key (request ID, message ID) with DynamoDB or Powertools to prevent reprocessing.

**Don't:** write orchestration logic in Lambda. If your function has more if/else/retry than business logic, move the workflow to Step Functions. Never have Lambda synchronously invoke another Lambda -- use SQS or Step Functions to decouple.

**Don't:** write to the same resource that triggered the function -- this causes recursive invocation loops with exponential cost. If detected, set reserved concurrency to **0** immediately.

See `references/function-code.md` for execution environment reuse details, cold start factors, idempotency implementation, connection management, and environment variables. See `references/anti-patterns.md` for why each anti-pattern feels right but isn't, impact analysis, and migration strategies.

## Function Configuration

### Memory and CPU -- they are linked

Lambda allocates CPU proportional to memory. At **1,769 MB**, a function gets one full vCPU.

| Memory | CPU | Best for |
|---|---|---|
| 128-512 MB | Fractional vCPU | Simple transforms, routing |
| 512-1,769 MB | Up to 1 vCPU | API handlers, moderate processing |
| 1,769-3,008 MB | 1-2 vCPU | Data processing, image manipulation |
| 3,008-10,240 MB | 2-6 vCPU | ML inference, heavy computation |

Use [AWS Lambda Power Tuning](https://github.com/alexcasalboni/aws-lambda-power-tuning) to find the optimal price/performance balance.

### Timeout -- set deliberately, not defensively

Set to p99 duration + 20-50% buffer. For SQS triggers, set SQS Visibility Timeout >= 6x function timeout. API Gateway enforces a 29-second integration timeout.

### Key quotas

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

See `references/function-configuration.md` for memory/CPU tuning strategies, IAM policy guidance, SQS integration, and quota management.

## Function Scalability

### Concurrency model

```
Concurrency = (requests per second) x (average duration in seconds)
```

100 RPS with 200ms average duration = 20 concurrent executions.

### Choosing a concurrency control

| Scenario | Control | How to size |
|---|---|---|
| Most functions, no special needs | **Unreserved** (default) | Shares account pool (1,000 default) |
| Critical function that must always have capacity | **Reserved concurrency** | Peak concurrent executions x 1.3 |
| Protect downstream from overload (DB, API) | **Reserved concurrency** | Match downstream's safe throughput |
| User-facing API with latency SLA | **Provisioned concurrency** | Eliminates cold starts; use auto-scaling |
| Emergency stop for runaway function | **Reserved concurrency = 0** | Halts all invocations immediately |

Lambda scales automatically -- **your dependencies may not.** Use RDS Proxy for relational databases, reserved concurrency to cap scaling to third-party rate limits, and on-demand mode for DynamoDB under Lambda workloads.

**Don't:** let Lambda overwhelm your database. A traffic spike -> 1,000 concurrent functions -> 1,000 simultaneous DB connections -> connection exhaustion -> all functions timeout -> cascade failure. This is the most common Lambda production incident.

See `references/function-scalability.md` for scaling rate, provisioned concurrency scheduling, throttle tolerance patterns, upstream/downstream protection, and cascade failure prevention.

## Metrics and Alarms

Prefer **Embedded Metric Format (EMF)** over `PutMetricData` API calls for custom metrics -- zero latency overhead. Use Powertools for AWS Lambda to handle EMF formatting. Use `PutMetricData` only when you need high-resolution (1-second) metrics or immediate availability.

### Key metrics to alarm on

| Metric | Alarm condition | What it catches |
|---|---|---|
| `Errors` | > 0 for N minutes | Function failures |
| `Throttles` | > 0 | Hitting concurrency limits |
| `Duration` | p99 > threshold | Latency degradation |
| `ConcurrentExecutions` | > 80% of reserved | Approaching ceiling |
| `IteratorAge` (streams) | > 30,000 ms | Falling behind on stream processing |
| `DeadLetterErrors` | > 0 | DLQ delivery failures |

Use structured JSON logging, correlation IDs across services, X-Ray tracing, and Cost Anomaly Detection.

See `references/metrics-and-alarms.md` for EMF details, structured logging guidance, alarm configuration, and cost anomaly detection setup.

## Working with Streams

**Batch tuning** is the critical lever -- larger batches amortize overhead, batching windows buffer small batches. **Always enable `ReportBatchItemFailures`** in production to retry only failed records instead of the entire batch. **Every stream-processing function must be idempotent** -- at-least-once delivery is guaranteed.

| Stream type | Scaling lever | Concurrency model |
|---|---|---|
| Kinesis | Add shards | 1 invocation per shard (default); up to 10 with parallelization factor |
| DynamoDB Streams | Add partitions (indirect) | 1 invocation per shard |
| SQS | Automatic | Lambda scales pollers up to concurrency limit |

See `references/stream-events.md` for batch tuning parameters, partial batch response implementation, Kinesis shard management, IteratorAge monitoring, and SQS FIFO considerations.

## Security

**IAM -- least privilege, always.** One narrowly scoped execution role per function. No wildcards in production. Use resource-based policies to control who can invoke your function.

| Practice | Why |
|---|---|
| Code signing | Verify deployment artifact integrity |
| VPC placement | Required for private resources; minor cold start impact (Hyperplane ENIs) |
| Security Hub controls | Automated CSPM checks against Lambda configurations |
| GuardDuty Lambda Protection | Monitors for threats (crypto mining, C2 communication) |
| Secrets Manager / Parameter Store | Never hardcode secrets |

See `references/security.md` for VPC configuration trade-offs, code signing setup, secrets management patterns, data protection, and governance strategies.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Initializing SDK clients inside the handler | Move to module/global scope for execution environment reuse |
| Setting timeout to 15 minutes "just in case" | Set to p99 duration + reasonable buffer; load test |
| Ignoring cold starts for user-facing APIs | Use provisioned concurrency or optimize package size |
| Not designing for idempotency | Use idempotency keys with DynamoDB or Powertools |
| Recursive invocations (function triggers itself) | Set reserved concurrency to 0 immediately; fix the trigger/output separation |
| Hardcoding resource names | Use environment variables for bucket names, table names, endpoints |
| Wildcard IAM permissions | Grant specific actions on specific resources |
| Not monitoring IteratorAge on streams | Alarm at 30s; add shards or increase parallelization |
| Retrying the full batch on partial failure | Enable `ReportBatchItemFailures` |
| Over-provisioning memory without testing | Use Lambda Power Tuning to find optimal setting |

## Reference Files

- **`references/anti-patterns.md`** -- Lambda monolith, Lambda as orchestrator, synchronous chains, recursive loops, synchronous waiting -- why each feels right, impact analysis, migration strategies
- **`references/function-code.md`** -- Execution environment reuse, cold start factors, idempotency implementation, connection management, RDS Proxy, environment variables
- **`references/function-configuration.md`** -- Memory/CPU tuning strategies, timeout alignment, quotas, IAM policies, SQS integration, cleanup
- **`references/function-scalability.md`** -- Concurrency estimation, reserved vs provisioned concurrency, scaling rate, upstream/downstream protection, cascade failure prevention
- **`references/metrics-and-alarms.md`** -- CloudWatch metrics, EMF implementation, structured logging, alarm configuration, Cost Anomaly Detection, X-Ray tracing
- **`references/stream-events.md`** -- Batch tuning, partial batch response, Kinesis/DynamoDB Streams/SQS scaling, IteratorAge monitoring, SQS FIFO high-throughput mode
- **`references/security.md`** -- IAM least privilege, code signing, VPC trade-offs, secrets management, data protection, Security Hub, GuardDuty, governance
