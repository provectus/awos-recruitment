# Working with Streams

## Event Source Mapping Basics

Lambda uses **event source mappings** to poll streams and queues and invoke your function with batches of records. Lambda manages the polling infrastructure -- you configure batch size, batching window, and error handling.

### Supported stream sources

| Source | Polling model | Ordering guarantee | Retry behavior |
|---|---|---|---|
| Kinesis Data Streams | Shard-based | Per-shard ordering | Retries until record expires or succeeds |
| DynamoDB Streams | Shard-based | Per-shard ordering | Retries until record expires or succeeds |
| SQS Standard | Automatic scaling | No ordering | Returns to queue after visibility timeout |
| SQS FIFO | Message group-based | Per-message-group ordering | Returns to queue after visibility timeout |
| Amazon MSK / Self-managed Kafka | Partition-based | Per-partition ordering | Retries until record expires or succeeds |

## Batch Tuning

### BatchSize

The maximum number of records Lambda sends to your function per invocation.

| Source | Default | Max | Guidance |
|---|---|---|---|
| Kinesis | 100 | 10,000 | Larger batches amortize invocation overhead |
| DynamoDB Streams | 100 | 10,000 | Match to processing capacity |
| SQS | 10 | 10,000 | Balance throughput vs processing time |
| Kafka / MSK | 100 | 10,000 | Match to consumer group throughput |

**All sources:** batch payload is capped at **6 MB** regardless of BatchSize setting.

### MaximumBatchingWindowInSeconds

How long Lambda waits to accumulate records before invoking your function.

| Setting | Effect |
|---|---|
| 0 (default) | Invoke as soon as records are available |
| 1-300 seconds | Buffer records; invoke when batch is full OR window expires |

**When to increase batching window:**

- Low-volume streams where you want to process records in larger batches
- Cost optimization -- fewer invocations = lower cost
- Processing that benefits from batch operations (bulk DB writes)

**When to keep at 0:**

- Latency-sensitive processing
- High-volume streams that naturally fill batches quickly

## Partial Batch Response

### The problem

Without partial batch response, if one record in a batch of 100 fails, Lambda retries the **entire batch of 100**. The 99 successful records get reprocessed.

### The solution

Enable `ReportBatchItemFailures` in the event source mapping. Your function returns only the IDs of failed records. Lambda retries only those records.

### Response format

```json
{
  "batchItemFailures": [
    { "itemIdentifier": "failed-record-sequence-number-or-message-id" }
  ]
}
```

### How identifiers map per source

| Source | Identifier field |
|---|---|
| Kinesis | `kinesis.sequenceNumber` |
| DynamoDB Streams | `dynamodb.SequenceNumber` |
| SQS | `messageId` |

### Best practices for partial batch response

- **Always enable** for production stream processing
- Process records individually, catch errors per-record, collect failed IDs
- Return an empty `batchItemFailures` array on full success
- If your function throws an unhandled exception, the entire batch is retried (partial response not used)

## Kinesis Scaling

### Shard-to-Lambda relationship

By default: **1 concurrent Lambda invocation per shard.** Each shard supports up to 1 MB/s or 1,000 records/s input.

### Parallelization factor

Set `ParallelizationFactor` (1-10) to process each shard with multiple concurrent Lambda invocations:

| Factor | Concurrent invocations per shard | Use case |
|---|---|---|
| 1 (default) | 1 | Simple, ordered processing |
| 2-5 | 2-5 | Higher throughput needed, can handle out-of-order within shard |
| 10 | 10 | Maximum throughput, processing is order-independent |

**Important:** With parallelization factor > 1, records within a shard may be processed out of order. Only use when order doesn't matter or your application handles reordering.

### Adding shards

If parallelization factor at 10 isn't enough:

1. Increase the number of shards in your Kinesis stream
2. Choose a partition key with good distribution (similar to DynamoDB partition key design)
3. Lambda automatically creates new pollers for new shards

### Shard iterator and checkpoint

Lambda tracks the position in each shard automatically. If your function fails:

- Lambda retries the batch from the last successful checkpoint
- Records ahead of the failure are blocked until the failed batch succeeds or is discarded
- Use `BisectBatchOnFunctionError` to split the batch in half and isolate the failing record

## IteratorAge Monitoring

`IteratorAge` measures how far behind your function is from the stream's latest record.

| IteratorAge | Status | Action |
|---|---|---|
| < 1,000 ms | Healthy | None |
| 1,000 - 30,000 ms | Behind | Monitor; may catch up |
| 30,000 - 60,000 ms | Significantly behind | Add shards, increase parallelization, optimize function |
| > 60,000 ms | Critical | Immediate action -- records may expire before processing |

### Alarm configuration

```
Metric: IteratorAge
Statistic: Maximum
Period: 1 minute
Threshold: > 30,000 ms for 3 consecutive periods
Action: Alert oncall
```

### Kinesis record retention

Default retention: **24 hours** (extendable to 365 days at additional cost). If IteratorAge exceeds retention period, records are lost permanently.

## DynamoDB Streams

### Key differences from Kinesis

| Aspect | Kinesis | DynamoDB Streams |
|---|---|---|
| Shard count | You control | Managed by DynamoDB (tied to table partitions) |
| Retention | 24h - 365 days | 24 hours (not configurable) |
| Record content | Your data | Change records (old/new image of DynamoDB items) |
| Parallelization factor | Supported | Supported |

### Common DynamoDB Streams patterns

| Pattern | Description |
|---|---|
| Change data capture (CDC) | Replicate changes to another data store |
| Materialized views | Build read-optimized projections |
| Event sourcing | Publish domain events from table changes |
| Cross-region sync | Replicate data (though Global Tables is simpler) |
| Audit logging | Record all changes for compliance |

## SQS Integration

### SQS Standard vs FIFO with Lambda

| Feature | SQS Standard | SQS FIFO |
|---|---|---|
| Ordering | Best-effort | Strict per message group |
| Lambda scaling | Up to 1,000 concurrent (or reserved limit) | 1 concurrent per message group |
| Throughput | Nearly unlimited | 300 messages/s (3,000 with batching) |
| Duplicates | Possible | Exactly-once delivery |

### Visibility Timeout alignment

```
SQS Visibility Timeout >= 6 x Lambda function timeout
```

This accounts for retries and processing time. If visibility timeout is too short, messages reappear in the queue and cause duplicate processing.

### Dead Letter Queue (DLQ)

Configure a DLQ on the SQS queue (not on the Lambda function) for SQS sources:

- Set `maxReceiveCount` to limit retry attempts (e.g., 3-5)
- After `maxReceiveCount` failures, the message moves to the DLQ
- Monitor DLQ depth as an alarm -- messages there need manual investigation

## Idempotency for Streams

**Every stream-processing function must be idempotent.** Duplicate delivery is guaranteed to happen:

- Kinesis/DynamoDB Streams: batch retries on failure deliver duplicates
- SQS: visibility timeout expiry causes redelivery
- Partial batch response: successfully processed records in a failed batch may be re-delivered depending on checkpoint behavior

See `function-code.md` for idempotency implementation patterns and key selection by event source.
