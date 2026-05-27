# Function Scalability

## Concurrency Model

### How Lambda scales

Lambda creates one execution environment per concurrent request. Concurrency is determined by:

```
Concurrency = (requests per second) x (average duration in seconds)
```

| Scenario | RPS | Avg duration | Concurrency needed |
|---|---|---|---|
| Fast API handler | 1,000 | 50ms | 50 |
| Moderate processing | 500 | 200ms | 100 |
| Heavy computation | 100 | 2s | 200 |
| Slow external API call | 50 | 5s | 250 |

### Scaling rate

Lambda scales at **1,000 new execution environments every 10 seconds** per function. This means:

- At t=0: up to 1,000 environments
- At t=10s: up to 2,000 environments
- At t=20s: up to 3,000 environments

This scaling rate applies per function, regardless of account-level concurrency limits.

### Account concurrency pool

All functions in a region share the account's concurrency pool (1,000 default). If `function-a` consumes 900, only 100 remain for all other functions. This is why reserved concurrency matters.

## Reserved Concurrency

Reserved concurrency sets both a **minimum guarantee** and a **maximum cap** for a function.

### When to use

| Scenario | Reserved concurrency value |
|---|---|
| Critical function that must always have capacity | Set to peak expected concurrency |
| Function that overwhelms downstream (DB, API) | Set to downstream's safe throughput |
| Emergency stop for a runaway function | Set to 0 |
| Non-critical background processing | Leave unreserved (shares the pool) |

### Trade-offs

| Benefit | Cost |
|---|---|
| Guarantees capacity for your function | Reduces available capacity for other functions |
| Caps scaling to protect downstream | Can cause throttling if traffic exceeds reserved amount |
| Free (no additional charges) | Must leave 100 units unreserved for other functions |

### Calculating reserved concurrency

Use CloudWatch `ConcurrentExecutions` metric:

1. Look at peak concurrency over a representative period (1-2 weeks)
2. Add 20-50% buffer above the peak
3. Verify that remaining unreserved pool is sufficient for other functions

### Formula verification

```
Reserved = peak_concurrent_executions x 1.3  (30% buffer)
```

Ensure: `sum(all reserved) <= account_limit - 100`

## Provisioned Concurrency

Provisioned concurrency **pre-initializes** execution environments so they're ready to serve requests immediately (no cold start).

### When to use

| Use case | Provisioned concurrency? |
|---|---|
| User-facing API with latency SLA | Yes |
| Interactive web/mobile backend | Yes |
| Async data pipeline | No (latency-insensitive) |
| Scheduled batch job | Rarely (only if cold start exceeds timeout tolerance) |
| Event-driven with unpredictable spikes | Maybe (combine with auto-scaling) |

### Provisioned concurrency auto-scaling

Use Application Auto Scaling to adjust provisioned concurrency based on a schedule or utilization:

- **Scheduled scaling** -- increase before known traffic peaks (e.g., business hours, marketing campaigns)
- **Target tracking** -- maintain a target utilization (e.g., keep 70% of provisioned concurrency utilized)

### Cost model

- Provisioned concurrency has a per-hour charge for pre-initialized environments
- Requests served by provisioned environments cost less per request than on-demand
- Over-provisioning wastes money; under-provisioning falls back to cold starts
- Use Power Tuning and CloudWatch metrics to right-size

## Throttle Tolerance

When Lambda cannot scale fast enough or hits concurrency limits, it throttles requests.

### Synchronous invocations (API Gateway, SDK calls)

Throttled requests return HTTP 429 (TooManyRequestsException). The caller is responsible for retrying.

**Caller-side strategies:**

- Exponential backoff with jitter
- Circuit breaker pattern for downstream protection
- Queue-based load leveling (put requests in SQS, process at sustainable rate)

### Asynchronous invocations (S3, SNS, EventBridge)

Lambda automatically retries throttled async invocations:

- Retries up to 2 times (configurable)
- Backs off automatically between retries
- After retries are exhausted, sends to Dead Letter Queue (DLQ) or failure destination

### Event source mappings (SQS, Kinesis, DynamoDB Streams)

Lambda manages retries internally:

- SQS: messages return to the queue after visibility timeout, retried until maxReceiveCount, then go to DLQ
- Kinesis/DynamoDB Streams: retries the batch until success or record expiry (bisects batch on failure if configured)

## Upstream/Downstream Protection

### Downstream bottleneck patterns

| Downstream | Problem | Solution |
|---|---|---|
| RDS database | Connection exhaustion | Use RDS Proxy; set reserved concurrency to match connection pool |
| DynamoDB (provisioned) | Write throttling | Switch to on-demand; or match WCU to expected concurrency |
| Third-party API | Rate limit exceeded | Set reserved concurrency to stay within rate limit |
| SQS (as destination) | N/A | SQS scales automatically |
| S3 | Prefix throttling (3,500 PUT/s) | Distribute keys across prefixes |

### Upstream mismatch patterns

| Upstream | Problem | Solution |
|---|---|---|
| API Gateway | 10,000 RPS default > Lambda 1,000 concurrency | Increase Lambda concurrency or add API Gateway throttling |
| ALB | No default request limit | Set Lambda reserved concurrency to protect downstream |
| CloudFront + Lambda@Edge | Global traffic concentration | Use regional edge caches; set appropriate concurrency |

### The cascade failure pattern

```
Traffic spike
  -> Lambda scales to 1,000 concurrent
    -> 1,000 simultaneous DB connections
      -> Database CPU/connection exhaustion
        -> All Lambda functions timeout waiting for DB
          -> Concurrency stays maxed (long-running stuck functions)
            -> New requests throttled
```

**Prevention:** Reserved concurrency + RDS Proxy + appropriate timeout + circuit breakers.
