# Concurrency Control

## Optimistic Locking

Use a version attribute to detect concurrent modifications. The write succeeds only if the version matches:

```python
# Read the item
response = table.get_item(Key={"PK": "USER#1", "SK": "PROFILE"})
item = response["Item"]
current_version = item["version"]

# Update with condition
try:
    table.update_item(
        Key={"PK": "USER#1", "SK": "PROFILE"},
        UpdateExpression="SET #name = :name, #ver = :new_ver",
        ConditionExpression="#ver = :cur_ver",
        ExpressionAttributeNames={"#name": "name", "#ver": "version"},
        ExpressionAttributeValues={
            ":name": "Updated Name",
            ":new_ver": current_version + 1,
            ":cur_ver": current_version,
        },
    )
except ClientError as e:
    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
        # Another writer modified the item — re-read and retry
        pass
```

### When to use

- Low-contention scenarios where conflicts are rare.
- User-facing applications where read-modify-write cycles are common.
- Items where you need to detect (not prevent) concurrent modifications.

### Retry strategy

On conflict, re-read the item, re-apply business logic, and retry. Use exponential backoff with jitter for high-contention items.

## Pessimistic Locking with DynamoDB Lock Client

The [DynamoDB Lock Client](https://github.com/awslabs/amazon-dynamodb-lock-client) provides distributed locks using a DynamoDB table:

```python
from python_dynamodb_lock.python_dynamodb_lock import DynamoDBLockClient

lock_client = DynamoDBLockClient(dynamodb_resource, table_name="locks")

lock = lock_client.acquire_lock("resource-123")
try:
    # Critical section — only one holder at a time
    process_resource("resource-123")
finally:
    lock.release()
```

### Characteristics

- **Heartbeat-based** — lock holder sends periodic heartbeats. If heartbeats stop (crash), the lock expires.
- **Lease duration** — configurable timeout after which the lock is released if not renewed.
- **Best for** — long-running operations, cross-service coordination, preventing duplicate processing.

## DynamoDB Transactions

`TransactWriteItems` and `TransactGetItems` provide serializable isolation:

```python
client.transact_write_items(
    TransactItems=[
        {
            "Put": {
                "TableName": "my-table",
                "Item": {"PK": {"S": "ORDER#1"}, "SK": {"S": "METADATA"}, ...},
                "ConditionExpression": "attribute_not_exists(PK)",
            }
        },
        {
            "Update": {
                "TableName": "my-table",
                "Key": {"PK": {"S": "USER#1"}, "SK": {"S": "STATS"}},
                "UpdateExpression": "SET order_count = order_count + :one",
                "ExpressionAttributeValues": {":one": {"N": "1"}},
            }
        },
    ]
)
```

### Transaction limits

| Limit | Value |
|---|---|
| Max items per transaction | 100 |
| Max transaction size | 4 MB |
| Operations supported | Put, Update, Delete, ConditionCheck |
| Consistency | Serializable isolation |
| Cost | 2x WCU (writes), 2x RCU (reads) |

### Idempotency

Pass a `ClientRequestToken` to make transactions idempotent. DynamoDB deduplicates retries within a 10-minute window:

```python
client.transact_write_items(
    TransactItems=[...],
    ClientRequestToken="unique-request-id-12345"
)
```

## Global Tables and Concurrency

Global tables use **last writer wins** conflict resolution for MREC (eventually consistent) mode:

- Version-based optimistic locking **does not work** across regions — two regions can independently increment the version and both succeed.
- For cross-region consistency, use **MRSC** (strongly consistent) global tables with a designated writer region.
- Alternatively, partition writes by region (e.g., Region A owns users A-M, Region B owns N-Z) to avoid conflicts entirely.

## Decision Matrix

| Scenario | Approach |
|---|---|
| Low-contention read-modify-write | Optimistic locking (version attribute) |
| High-contention single item | Optimistic locking with backoff + jitter |
| Long-running exclusive operations | DynamoDB Lock Client |
| Multi-item atomic operations | TransactWriteItems |
| Cross-region writes (MREC) | Design to avoid conflicts (partition by region) |
| Cross-region writes (MRSC) | Single designated writer region |
