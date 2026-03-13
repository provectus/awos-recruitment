# Key and Index Design

## Partition Key Selection

### Evaluation guide

| Partition key | Cardinality | Traffic distribution | Verdict |
|---|---|---|---|
| `user_id` (UUID) | Very high | Uniform (unless celebrity users) | Excellent |
| `device_id` | High | Generally uniform | Good |
| `tenant_id` | Medium | Skewed (large tenants dominate) | Needs sharding |
| `status` (active/inactive) | Very low | Heavily skewed | Bad |
| `country_code` | Low-medium | Skewed (US/CN dominate) | Bad |
| `date` (YYYY-MM-DD) | Medium | Hot today, cold yesterday | Bad for writes |

### Principles

- **High cardinality** — more distinct values means better distribution.
- **Uniform request rate** — even with many distinct values, a few popular keys create hot spots.
- **Composite keys** — combine attributes to increase cardinality: `tenant_id#user_id` instead of `tenant_id` alone.

## Write Sharding

When a natural key has hot spots, add a suffix to spread writes across logical partitions.

### Random suffix

```
partition_key = f"{date}#{random.randint(0, 9)}"
```

Trade-off: reads must query all suffixes and merge results (scatter-gather).

### Calculated suffix

```
partition_key = f"{date}#{hash(order_id) % 20}"
```

Advantage: if you know the `order_id`, you can calculate which shard to read directly — no scatter-gather for point reads.

### When to shard

| Write rate per key | Recommendation |
|---|---|
| < 1,000 WCU | No sharding needed |
| 1,000–5,000 WCU | 5–10 shards |
| 5,000–20,000 WCU | 20–50 shards |
| > 20,000 WCU | 50+ shards or redesign key |

Adaptive capacity and burst capacity (up to 5 minutes of banked unused throughput) help with short spikes but do not fix sustained hot keys.

### Hot partition anti-patterns

- **Time-based partition keys** — all writes hit "today." Shard with a suffix.
- **Status fields as keys** — most items are "active." Use a sparse GSI instead.
- **Sequential IDs** — monotonically increasing IDs concentrate on latest partition. Use UUIDs or KSUID.
- **Global counters** — a single item receiving all increments. Use sharded counters with periodic aggregation.

## Sort Key Patterns

### Hierarchical composite keys

Encode hierarchy with a delimiter, broadest to most specific:

```
PK: LOCATION
SK: USA#CA#San Francisco#94105
```

| Access pattern | KeyCondition |
|---|---|
| All US locations | `PK = LOCATION AND begins_with(SK, "USA#")` |
| All California | `PK = LOCATION AND begins_with(SK, "USA#CA#")` |
| Specific zip code | `PK = LOCATION AND SK = "USA#CA#San Francisco#94105"` |

Use `#` as delimiter. If values can contain `#`, use `##` or `|`.

### Version control pattern

Store latest at a well-known prefix, historical versions with numbered prefixes:

```
PK: DOC#123
SK: v0_metadata     ← always current version
SK: v1_metadata     ← historical
SK: v2_metadata     ← historical
```

On update: write `v{N+1}_metadata`, then overwrite `v0_metadata` with the same data.

### Entity-type prefixes

In single-table designs, distinguish entity types within a partition:

```
PK: USER#alice    SK: PROFILE         ← user metadata
PK: USER#alice    SK: ORDER#2024-001  ← order
PK: USER#alice    SK: ADDR#home       ← address
```

Query `begins_with(SK, "ORDER#")` to get all orders for a user.

### Key design checklist

- Does the sort key enable the top access patterns as range queries?
- Are hierarchy levels ordered broadest to most specific?
- Is the delimiter safe (not present in data values)?
- For versioned data, is there a predictable key for "latest"?
- For time-based queries, is the timestamp format sortable (ISO 8601)?

## Secondary Indexes

### GSI vs LSI — when to use each

**Default to GSI.** GSIs can be added anytime, have no size limit, and support any partition key. Use LSI only when **all three** conditions apply: you need strongly consistent reads on an alternate sort key, the item collection stays under 10 GB, and you can define the index at table creation time.

### Projection strategy

| Projection | When to use |
|---|---|
| `KEYS_ONLY` | Existence checks, or when you always fetch the full item from the base table anyway |
| `INCLUDE` | High-write tables — reduces index write amplification. Project only the attributes your queries need |
| `ALL` | Read-heavy workloads with low write volume — avoids fetches back to base table |

### Sparse indexes

Use when you need efficient access to a small subset of items — only items with the GSI key attribute appear in the index. Good for: items with a status flag (`is_featured`), "active" subsets, or TTL-like patterns where only current items have a certain attribute.

### GSI overloading

In single-table designs, use generic attribute names (`GSI1PK`, `GSI1SK`) to serve multiple entity types from one GSI:

```
PK: EMP#1   SK: METADATA    GSI1PK: HR          GSI1SK: John Smith
PK: EMP#1   SK: PROJECT#A   GSI1PK: PROJ#A      GSI1SK: EMP#1
PK: PROJ#A  SK: METADATA    GSI1PK: ACTIVE       GSI1SK: 2024-01-01
```

One GSI enables: "all HR employees," "all members of Project A," "active projects by date."

### Write amplification

Every GSI replicates writes from the base table. A table with 3 GSIs turns each write into 4 writes (1 base + 3 GSI). Factor this into cost estimates and capacity planning. `ALL` projection amplifies write cost more than `KEYS_ONLY`.

## Query vs Scan

**Always design for Query.** If you find yourself needing Scan for a regular access pattern, redesign your keys or add a GSI. Scan reads the entire table and costs RCU proportional to total table size — filters reduce results but not the capacity consumed.

### Query optimization

- Use **key conditions** to narrow results, not filter expressions. A filter on a Query still reads all items in the partition — it just discards them after reading.
- Use `ProjectionExpression` to request only the attributes you need.

### Parallel scan guidelines

| Table size | Recommendation |
|---|---|
| < 2 GB | No parallelism |
| 2–20 GB | 1–10 segments |
| 20–100 GB | ~1 segment per 2 GB |
| > 100 GB | Consider S3 export + Athena instead |

### Avoiding capacity spikes from scans

- **Reduce page size** with `Limit` to control items per request.
- **Exponential backoff** on `ProvisionedThroughputExceededException`.
- **Schedule scans** during off-peak hours.
- **Use a replica** — scan a global table replica dedicated to analytics.
