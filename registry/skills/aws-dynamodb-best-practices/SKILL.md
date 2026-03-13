---
name: aws-dynamodb-best-practices
description: >-
  AWS DynamoDB best practices for table design and data modeling. Use when designing
  DynamoDB schemas, choosing partition/sort keys, creating secondary indexes, modeling
  relationships, handling time series data, or optimizing query patterns. Triggers on
  tasks involving DynamoDB table creation, key design, GSI/LSI configuration, single-table
  design, adjacency lists, write sharding, or capacity planning. Does not cover DynamoDB
  SDK/API reference or CloudFormation/Terraform resource definitions.
version: 0.1.0
---

# AWS DynamoDB Best Practices

Opinionated conventions for designing and operating DynamoDB tables at scale. For SDK/API usage or infrastructure-as-code definitions, consult the relevant AWS SDK or Terraform documentation instead.

## NoSQL Design Mindset

DynamoDB is not a relational database — schema follows queries, not the other way around. Identify all access patterns before creating tables. Denormalize and duplicate data to avoid cross-table lookups.

See `references/nosql-design-principles.md` for access-pattern-first design, RDBMS migration thinking, and when to use single vs multiple tables.

## Key and Index Design

### Partition key — high cardinality, uniform distribution

| Partition key | Verdict | Why |
|---|---|---|
| `user_id` (UUID) | Excellent | Very high cardinality, uniform traffic |
| `tenant_id` | Needs sharding | Skewed — large tenants dominate |
| `status` (active/inactive) | Bad | Very low cardinality, heavily skewed |
| `date` (YYYY-MM-DD) | Bad for writes | All writes hit "today" |

### Sort key — encode hierarchy broadest to most specific

```
PK: USER#alice    SK: PROFILE         ← user metadata
PK: USER#alice    SK: ORDER#2024-001  ← order (query begins_with(SK, "ORDER#"))
PK: USER#alice    SK: ADDR#home       ← address
```

### GSI vs LSI

**Default to GSI.** Use LSI only when all three apply: you need strongly consistent reads on an alternate sort key, item collection stays under 10 GB, and you can define the index at table creation.

### Query vs Scan

**Always design for Query.** Scan costs RCU proportional to total table size — filters reduce results but not capacity consumed. If you need Scan for a regular access pattern, redesign your keys or add a GSI.

See `references/key-and-index-design.md` for sharding strategies, GSI overloading, sparse indexes, projection strategy, and parallel scan guidelines.

## Data Modeling Patterns

### One-to-many — denormalize into parent partition

```
PK          | SK              | data
ORDER#1     | ORDER#1         | {customer, total, date}
ORDER#1     | ITEM#1          | {product, qty, price}
ORDER#1     | ITEM#2          | {product, qty, price}
```

One `Query` on `PK = ORDER#1` returns the order with all its items.

### Many-to-many — adjacency list pattern

Store bidirectional edges as items. A GSI with `SK` as partition key enables reverse lookups without maintaining duplicate edge items.

### Large items (400 KB limit)

| Strategy | When to use |
|---|---|
| Compression (gzip) | Large attributes you don't filter on (stored as Binary) |
| Vertical partitioning | Split into METADATA / BODY / COMMENTS sort keys — query only what you need |
| S3 offload | Anything over ~100 KB — store pointer in DynamoDB |

See `references/data-modeling-patterns.md` for adjacency list examples, time series table-per-period strategy, and trade-offs.

## Concurrency Control

Individual writes are atomic. Locking is only needed for read-modify-write cycles:

| Scenario | Approach |
|---|---|
| Low-contention read-modify-write | Optimistic locking — version attribute + `ConditionExpression` |
| Multi-item atomic operations | `TransactWriteItems` (up to 100 items / 4 MB, costs 2x WCU) |
| Long-running exclusive operations | DynamoDB Lock Client (heartbeat-based distributed locks) |
| Cross-region writes (MREC) | Design to avoid conflicts — partition by region |

See `references/concurrency-control.md` for retry strategies, transaction design considerations, and global tables concurrency caveats.

## Global Tables

Global tables replicate data across regions for low-latency global access (99.999% availability).

| Need | Choose |
|---|---|
| Low-latency global writes, tolerate eventual consistency | MREC — async replication, last-writer-wins |
| Strong consistency globally, zero RPO | MRSC — sync replication, exactly 3 regions, no transactions/TTL |
| Conditional writes or transactions | MREC with write-to-one-region mode |

**Write modes** are application-level routing (write-to-any, write-to-one, write-to-your-region) — DynamoDB itself always accepts writes in any replica.

See `references/global-tables.md` for MREC vs MRSC design implications, write mode selection, and operational guidance.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Designing schema before access patterns | List all queries first, then design keys |
| Low-cardinality partition key | Composite key or write sharding |
| Using Scan for regular access patterns | Redesign keys or add a GSI |
| Filter expressions to reduce reads | Filters don't reduce RCU — use key conditions |
| Storing large lists in one attribute | Individual items with sort key prefixes |
| `ALL` projection on write-heavy GSI | `KEYS_ONLY` or `INCLUDE` to reduce write amplification |
| Optimistic locking across regions (MREC) | Last-writer-wins silently resolves — partition writes by region |
| Transactions for bulk ingestion | Use `BatchWriteItem` instead |

## Reference Files

- **`references/nosql-design-principles.md`** — Access-pattern-first design, RDBMS vs NoSQL mindset, when to denormalize, when to use multiple tables
- **`references/key-and-index-design.md`** — Partition key evaluation, write sharding, sort key patterns, GSI vs LSI, projections, sparse indexes, GSI overloading, query vs scan optimization
- **`references/data-modeling-patterns.md`** — Adjacency lists, time series, large items, vertical partitioning, S3 offload
- **`references/concurrency-control.md`** — Optimistic/pessimistic locking, transactions, DynamoDB Lock Client, global tables concurrency
- **`references/global-tables.md`** — MREC vs MRSC, write modes, request routing, monitoring, cost model
