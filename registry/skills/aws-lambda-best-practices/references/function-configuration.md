# Function Configuration

## Memory and CPU Tuning

### The memory-CPU relationship

Lambda allocates CPU power proportional to configured memory:

| Memory | Approximate CPU | vCPU equivalent |
|---|---|---|
| 128 MB | ~7% of a vCPU | 0.07 |
| 256 MB | ~14% of a vCPU | 0.14 |
| 512 MB | ~28% of a vCPU | 0.28 |
| 1,024 MB | ~56% of a vCPU | 0.56 |
| 1,769 MB | 1 full vCPU | 1.0 |
| 3,538 MB | 2 vCPU | 2.0 |
| 5,307 MB | 3 vCPU | 3.0 |
| 10,240 MB | ~6 vCPU | ~5.8 |

### Finding optimal memory

More memory doesn't always mean more cost. A function at 256 MB running for 1,000ms costs the same as the same function at 512 MB running for 500ms -- but finishes twice as fast.

**Use AWS Lambda Power Tuning:**

1. Deploy the [Power Tuning state machine](https://github.com/alexcasalboni/aws-lambda-power-tuning) in your account
2. Run it against your function with a representative payload
3. It tests multiple memory configurations and produces a cost-vs-speed graph
4. Pick the knee of the curve -- best price/performance balance

### When to go higher

| Signal | Action |
|---|---|
| `Max Memory Used` close to configured memory | Increase memory (risk of OOM) |
| Duration decreases linearly with more memory | Function is CPU-bound; more memory = more CPU |
| Duration doesn't change with more memory | Function is I/O-bound (waiting on network); more memory won't help |
| Billed Duration >> actual Duration | You're paying for unused capacity; consider reducing |

### Monitoring memory usage

Every invocation logs a `REPORT` line:

```
REPORT RequestId: abc123  Duration: 45.00 ms  Billed Duration: 46 ms  Memory Size: 256 MB  Max Memory Used: 82 MB
```

Track `Max Memory Used` over time. If it consistently stays far below configured memory, you're over-provisioned.

## Timeout Strategy

### Setting the right timeout

| Principle | Details |
|---|---|
| Measure actual duration under load | Not just happy-path; include downstream latency |
| Add a buffer (20-50%) above measured p99 | Accounts for variance without excessive waste |
| Never use the max (900s) as a default | A stuck function at 15 min timeout accumulates cost and concurrency |
| Align with upstream expectations | API Gateway has a 29-second integration timeout |
| Align with downstream expectations | SQS Visibility Timeout must exceed function timeout |

### SQS Visibility Timeout alignment

When Lambda processes SQS messages:

```
Function timeout < SQS Visibility Timeout
```

If the function times out before the visibility timeout expires, the message remains invisible. If the function timeout exceeds visibility timeout, the message becomes visible again and triggers a duplicate invocation.

**Recommended:** Set SQS Visibility Timeout to **6x your function timeout** (AWS recommendation).

### API Gateway integration timeout

API Gateway enforces a **29-second** maximum integration timeout. If your Lambda function needs more than 29 seconds:

- Refactor to async pattern: API Gateway -> Lambda (start job) -> Step Functions or SQS -> Lambda (process)
- Use Lambda response streaming for long-running responses

## Quotas Reference

### Hard limits (cannot be increased)

| Resource | Limit |
|---|---|
| Maximum execution time | 900 seconds (15 minutes) |
| Synchronous payload (request) | 6 MB |
| Synchronous payload (response) | 6 MB (200 MB streamed) |
| Asynchronous payload | 1 MB |
| Deployment package (zipped) | 50 MB via API (use S3 for larger) |
| Deployment package (unzipped) | 250 MB (including layers) |
| Container image | 10 GB |
| Environment variables | 4 KB total |
| Layers | 5 per function |
| File descriptors | 1,024 |
| Processes/threads | 1,024 |

### Soft limits (can be increased via Service Quotas)

| Resource | Default | Typical increase |
|---|---|---|
| Concurrent executions | 1,000 | Tens of thousands |
| Function code storage | 75 GB | Terabytes |
| ENIs per VPC | 500 | Thousands |

### New accounts

New AWS accounts start with **reduced** concurrency and memory quotas. AWS raises these automatically based on usage. If you need immediate capacity, request increases through Service Quotas.

## IAM Execution Role

### Least privilege checklist

- Grant only the specific API actions needed (e.g., `dynamodb:GetItem`, not `dynamodb:*`)
- Restrict resources to specific ARNs (e.g., the specific table, not `*`)
- Use IAM conditions where appropriate (e.g., `aws:RequestedRegion`)
- One role per function (or per group of functions with identical needs)
- Audit roles with IAM Access Analyzer to identify unused permissions

### Common execution role permissions

| Function type | Typical permissions |
|---|---|
| API handler | DynamoDB CRUD on specific table, CloudWatch Logs |
| S3 processor | S3 GetObject on source bucket, PutObject on destination bucket |
| SQS consumer | SQS ReceiveMessage, DeleteMessage, GetQueueAttributes |
| Kinesis consumer | Kinesis GetRecords, GetShardIterator, DescribeStream, ListShards |

### Managed policies to avoid in production

- `AWSLambdaFullAccess` -- overly broad
- `AdministratorAccess` -- never attach to a Lambda execution role
- `AmazonS3FullAccess` -- grants access to all buckets

## Function Lifecycle Management

### Cleanup

- **Delete unused functions** -- they count against your code storage quota (75 GB default)
- **Remove old versions** -- each published version consumes storage
- **Prune unused layers** -- layer versions also count against storage
- **Archive** -- if you need to retain code, store it in S3 or a code repository, not as deployed Lambda functions
