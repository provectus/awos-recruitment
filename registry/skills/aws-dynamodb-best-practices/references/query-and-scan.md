# Query and Scan Best Practices

## Query vs Scan

| Operation | How it works | Capacity cost | When to use |
|---|---|---|---|
| **Query** | Finds items by partition key + optional sort key condition | Proportional to items matched | Primary access method — use for all known-key lookups |
| **Scan** | Reads every item in the table/index | Proportional to total table size | Last resort — analytics, migrations, one-off operations |

A scan on a 10 GB table consumes 10 GB worth of RCU regardless of how many items match your filter. Filters reduce the result set but **not** the capacity consumed.

## Query Optimization

### Use key conditions, not filters

```
# GOOD — reads only matching items
response = table.query(
    KeyConditionExpression=Key("PK").eq("USER#1") & Key("SK").begins_with("ORDER#")
)

# BAD — reads all items for USER#1, then filters (wastes RCU)
response = table.query(
    KeyConditionExpression=Key("PK").eq("USER#1"),
    FilterExpression=Attr("type").eq("ORDER")
)
```

### Projection expressions

Request only the attributes you need to reduce data transfer:

```python
response = table.query(
    KeyConditionExpression=Key("PK").eq("USER#1"),
    ProjectionExpression="order_id, total, #s",
    ExpressionAttributeNames={"#s": "status"}  # "status" is a reserved word
)
```

### Pagination

DynamoDB returns up to 1 MB per query. For large result sets, use `LastEvaluatedKey`:

```python
items = []
last_key = None
while True:
    kwargs = {"KeyConditionExpression": Key("PK").eq("USER#1")}
    if last_key:
        kwargs["ExclusiveStartKey"] = last_key
    response = table.query(**kwargs)
    items.extend(response["Items"])
    last_key = response.get("LastEvaluatedKey")
    if not last_key:
        break
```

## When Scan Is Necessary

Some legitimate scan use cases:

- **Data migration** — moving data between tables or formats.
- **Analytics/reporting** — full-table aggregation (consider exporting to S3 + Athena for large tables).
- **Backfill** — populating a new GSI's projected attributes.

## Parallel Scan

For large tables, split the scan across multiple workers:

```python
import concurrent.futures

def scan_segment(table_name, segment, total_segments):
    table = boto3.resource("dynamodb").Table(table_name)
    items = []
    last_key = None
    while True:
        kwargs = {
            "Segment": segment,
            "TotalSegments": total_segments,
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        response = table.scan(**kwargs)
        items.extend(response["Items"])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
    return items

# Guidelines: ~1 segment per 2 GB of data
total_segments = max(1, table_size_gb // 2)
with concurrent.futures.ThreadPoolExecutor(max_workers=total_segments) as executor:
    futures = [executor.submit(scan_segment, "my-table", i, total_segments)
               for i in range(total_segments)]
```

### Parallel scan guidelines

| Table size | Recommended segments | Notes |
|---|---|---|
| < 2 GB | 1 (no parallelism) | Parallel scan adds overhead on small tables |
| 2–20 GB | 1–10 | Start low, increase if scans are too slow |
| 20–100 GB | 10–50 | ~1 segment per 2 GB |
| > 100 GB | 50+ | Consider S3 export instead |

## Avoiding Capacity Spikes

- **Reduce page size** — use `Limit` to control items per request. Smaller pages consume less burst capacity.
- **Exponential backoff** — when receiving `ProvisionedThroughputExceededException`, wait 50ms, then 100ms, 200ms, etc.
- **Schedule scans** — run full scans during off-peak hours.
- **Use a replica** — scan a global table replica dedicated to analytics instead of the primary.
- **Rate-limit scans** — add a small sleep between pages to cap throughput consumption.
