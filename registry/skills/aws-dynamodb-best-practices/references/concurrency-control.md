# Concurrency Control

> **Note:** Individual write operations such as `UpdateItem` are atomic and always operate on the most recent version of the item, regardless of concurrency. Locking strategies are only needed when your application must read an item and then write it back based on the read value (a read-modify-write cycle), because another process could modify the item between the read and the write.

## Optimistic Locking

Add a `version` attribute to items. On update, use `ConditionExpression` to require the version matches what you read. If another writer changed it, you get `ConditionalCheckFailedException` — re-read and retry.

### When to use

- Low-contention scenarios where conflicts are rare.
- User-facing applications where read-modify-write cycles are common.
- Items where you need to detect (not prevent) concurrent modifications.

### Retry strategy

On conflict, re-read the item, re-apply business logic, and retry. Use exponential backoff with jitter for high-contention items. Cap retries at 3–5 attempts — each retry costs an additional read.

## Pessimistic Locking with DynamoDB Lock Client

The [DynamoDB Lock Client](https://github.com/awslabs/amazon-dynamodb-lock-client) provides heartbeat-based distributed locks using a dedicated DynamoDB table. Locks auto-expire if the holder crashes (configurable lease duration).

### When to use

- Long-running operations where retry-on-conflict is expensive.
- Cross-service coordination (e.g., preventing duplicate processing of a job).
- Critical sections that must be held for seconds or minutes, not milliseconds.

## DynamoDB Transactions

### When to use

- You need **all-or-nothing semantics** across multiple items (up to 100 items / 4 MB).
- You need to combine condition checks with writes in a single atomic operation.
- Moderate contention — transactions prevent concurrent access to involved items for the duration.

### Design considerations

- **Cost: 2x capacity** — each item costs 2 WCU (writes) or 2 RCU (reads) due to prepare + commit phases. Budget accordingly.
- **Keep transactions small** — don't group operations that don't need atomicity. Simpler transactions are more likely to succeed and less likely to conflict.
- **Don't use for bulk ingestion** — use `BatchWriteItem` instead.
- **Cannot target the same item twice** within one transaction (e.g., a `ConditionCheck` and an `Update` on the same key will be rejected).
- **Make retries safe** — pass a `ClientRequestToken` for idempotency (deduplicates within 10 minutes).
- Monitor `TransactionConflict` CloudWatch metric to detect contention hotspots.

## Global Tables and Concurrency

Global tables use **last writer wins** conflict resolution for MREC (eventually consistent) mode:

- Version-based optimistic locking **does not work** across regions — two regions can independently increment the version and both succeed.
- For cross-region consistency, use **MRSC** (strongly consistent) global tables. MRSC supports active-active writes across regions — concurrent writes to the same item are rejected with `ReplicatedWriteConflictException` (retry-safe). No single designated writer region is required.
- Alternatively, partition writes by region (e.g., Region A owns users A-M, Region B owns N-Z) to avoid conflicts entirely.
- **Transactions are not cross-region** — `TransactWriteItems` provides ACID guarantees only within the region where invoked. Other replicas may observe partially completed transactions during replication.

## Decision Matrix

| Scenario | Approach |
|---|---|
| Low-contention read-modify-write | Optimistic locking (version attribute) |
| High-contention single item | Optimistic locking with backoff + jitter |
| Moderate-contention multi-item updates | TransactWriteItems (pessimistic) |
| Long-running exclusive operations | DynamoDB Lock Client |
| Multi-item atomic operations | TransactWriteItems |
| Cross-region writes (MREC) | Design to avoid conflicts (partition by region) |
| Cross-region writes (MRSC) | Active-active with `ReplicatedWriteConflictException` on conflicts |
