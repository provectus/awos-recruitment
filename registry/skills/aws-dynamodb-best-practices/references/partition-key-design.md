# Partition Key Design

## Why Partition Keys Matter

DynamoDB distributes data across partitions based on the partition key hash. If many items or requests target the same partition key, that partition becomes a **hot spot** — leading to throttling even when total table capacity is underutilized.

## Choosing Good Partition Keys

### Uniformity evaluation

| Partition key | Cardinality | Traffic distribution | Rating |
|---|---|---|---|
| `user_id` (UUID) | Very high | Uniform (unless celebrity users) | Excellent |
| `device_id` | High | Generally uniform | Good |
| `tenant_id` | Medium | Skewed (large tenants dominate) | Needs sharding |
| `status` (active/inactive) | Very low | Heavily skewed | Bad |
| `country_code` | Low-medium | Skewed (US/CN dominate) | Bad |
| `date` (YYYY-MM-DD) | Medium | Hot today, cold yesterday | Bad for writes |

### Principles

- **High cardinality** — more distinct values means better distribution.
- **Uniform request rate** — even with many values, a few popular keys create hot spots.
- **Composite keys** — combine attributes to increase cardinality: `tenant_id#user_id` instead of `tenant_id` alone.

## Partition Throughput Limits

Each physical partition supports:

| Metric | Limit |
|---|---|
| Read capacity | 3,000 RCU |
| Write capacity | 1,000 WCU |
| Storage | 10 GB |

**Adaptive capacity** automatically redistributes throughput to hot partitions using unused capacity from other partitions. This handles short bursts but cannot fix sustained skew.

## Write Sharding Strategies

### Random suffix

Append a random number to spread writes:

```
partition_key = f"{date}#{random.randint(0, 9)}"
# Creates 10 logical partitions per date
```

**Trade-off:** Reads must query all 10 suffixes and merge results.

### Calculated suffix

Use a deterministic hash of a known attribute:

```
partition_key = f"{date}#{hash(order_id) % 20}"
```

**Advantage:** If you know the `order_id`, you can calculate which shard to read from directly — no scatter-gather needed for point reads.

### Suffix count guidelines

| Write rate per key | Recommended shards |
|---|---|
| < 1,000 WCU | No sharding needed |
| 1,000–5,000 WCU | 5–10 shards |
| 5,000–20,000 WCU | 20–50 shards |
| > 20,000 WCU | 50+ shards or redesign key |

## Hot Partition Anti-Patterns

1. **Time-based partition keys** — all writes hit "today" partition. Shard by adding a suffix.
2. **Status fields** — most items are "active." Use a GSI with a sparse index instead.
3. **Sequential IDs** — monotonically increasing IDs concentrate on the latest partition. Use UUIDs or KSUID.
4. **Global counters** — a single item receiving all increments. Use sharded counters with periodic aggregation.

## Burst Capacity

DynamoDB saves unused capacity for up to 5 minutes and can burst up to 300 seconds of unused capacity. This helps with:

- Occasional spikes in traffic to a specific partition key.
- Uneven access patterns that shift throughout the day.

Burst capacity is not a substitute for proper key design — it only smooths temporary spikes.
