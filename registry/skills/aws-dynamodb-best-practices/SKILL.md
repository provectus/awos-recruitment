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

Opinionated conventions for designing and operating DynamoDB tables at scale. Covers key design, secondary indexes, data modeling patterns, query optimization, concurrency control, and global tables. For SDK/API usage or infrastructure-as-code definitions, consult the relevant AWS SDK or Terraform documentation instead.

## NoSQL Design Mindset

DynamoDB is not a relational database — designing it like one leads to poor performance and high costs.

### Key principles

- **Access-pattern-first design** — identify all read/write access patterns before creating tables. Schema follows queries, not the other way around.
- **Keep few tables** — most applications should use a single table (or very few). Multiple entity types coexist in the same table.
- **Locality of reference** — store related data together so a single query retrieves everything needed. Denormalization is expected, not a compromise.
- **Data size, shape, and velocity** — NoSQL databases scale horizontally by distributing data across partitions. Design keys to spread load evenly.

### RDBMS vs DynamoDB

| Aspect | RDBMS | DynamoDB |
|---|---|---|
| Schema design | Normalize first, query later | Design for access patterns first |
| Joins | Native SQL joins | No joins — denormalize or use indexes |
| Tables per app | Many (one per entity) | Few (often one, with overloaded keys) |
| Scaling | Vertical (bigger machine) | Horizontal (partition-based) |
| Transactions | Full ACID across tables | ACID within 100 items / 4 MB |

For foundational NoSQL concepts and migration thinking, see `references/nosql-design-principles.md`.

## Partition Key Design

The partition key determines data distribution. Poor key choice creates **hot partitions** and throttling.

### Rules

- **High cardinality** — choose attributes with many distinct values (user ID, device ID, session ID).
- **Uniform distribution** — requests should spread evenly across partition key values.
- **Avoid low-cardinality keys** — status codes, boolean flags, or date-only values concentrate traffic.

| Key choice | Cardinality | Distribution | Verdict |
|---|---|---|---|
| User ID | High | Uniform | Good |
| Device ID | High | Uniform | Good |
| Status (`active`/`inactive`) | Low | Skewed | Bad |
| Day of week | Very low | Skewed | Bad |

### Write sharding

When a natural key is unavoidable but has hot spots, add a calculated suffix:

```
partition_key = f"{order_date}#{hash(order_id) % 10}"
```

This spreads writes across 10 logical partitions per date. Reads require querying all 10 suffixes in parallel and merging results.

Each physical partition supports up to **3,000 RCU** and **1,000 WCU**. Adaptive capacity redistributes unused throughput to hot partitions, and burst capacity banks up to 5 minutes of unused capacity — both help with short spikes but do not fix sustained hot keys.

For detailed sharding strategies and throughput limits, see `references/partition-key-design.md`.

## Sort Key Patterns

Sort keys enable range queries and hierarchical data organization within a partition.

### Hierarchical composite keys

Encode hierarchy levels separated by a delimiter:

```
PK: LOCATION
SK: USA#CA#San Francisco
SK: USA#CA#Los Angeles
SK: USA#NY#New York
```

Query with `begins_with(SK, "USA#CA#")` to get all California cities.

### Version control pattern

Use a `v0_` prefix for the latest version and `v{N}_` for historical versions:

```
PK: DOC#123
SK: v0_metadata     ← always the current version
SK: v1_metadata     ← version 1 (historical)
SK: v2_metadata     ← version 2 (historical)
```

Query `SK = v0_metadata` to always get the latest. Query `begins_with(SK, "v")` to get all versions.

For more sort key patterns and range query examples, see `references/sort-key-patterns.md`.

## Secondary Indexes

### GSI vs LSI

| Feature | GSI (Global) | LSI (Local) |
|---|---|---|
| Key schema | Different PK and SK | Same PK, different SK |
| When to create | Anytime | Table creation only |
| Consistency | Eventually consistent only | Eventually or strongly consistent |
| Throughput | Independent (provisioned separately) | Shares base table throughput |
| Size limit | None | 10 GB per item collection |

### Projection strategies

- **KEYS_ONLY** — smallest index, cheapest. Use when you only need to look up items by alternate key.
- **INCLUDE** — project specific attributes. Good balance of size and utility.
- **ALL** — full copy of items. Largest and most expensive but avoids fetches back to base table.

### Sparse indexes

Only items that contain the index key attributes appear in a GSI. Use this to create efficient filtered views:

```
# Only items with "award" attribute appear in this GSI
GSI PK: award       SK: date
# Query the GSI to find all award-winning items efficiently
```

### GSI overloading

Use generic attribute names (`GSI1PK`, `GSI1SK`) and store different entity types' access patterns in the same GSI:

```
Item: {PK: "EMP#1", SK: "METADATA", GSI1PK: "HR", GSI1SK: "John Smith"}
Item: {PK: "EMP#1", SK: "PROJECT#A", GSI1PK: "PROJ#A", GSI1SK: "EMP#1"}
```

For detailed GSI/LSI guidance and overloading examples, see `references/secondary-indexes.md`.

## Query & Scan Best Practices

### Prefer Query over Scan

- **Query** finds items by primary key — efficient, reads only matching items.
- **Scan** reads the entire table — expensive, consumes capacity proportional to table size.

### When Scan is unavoidable

- Use **parallel scan** for tables over 20 GB — set `TotalSegments` to approximately 1 segment per 2 GB of data.
- **Reduce page size** with the `Limit` parameter to avoid consuming too much capacity in a single operation.
- **Use exponential backoff** when receiving `ProvisionedThroughputExceededException`.
- Avoid running scans during peak traffic — schedule them during off-peak hours or use a replica.

For query optimization techniques and parallel scan configuration, see `references/query-and-scan.md`.

## Data Modeling Patterns

### Adjacency list pattern

Model many-to-many relationships in a single table using item partitioning:

```
PK          | SK          | Data
INVOICE#1   | INVOICE#1   | Invoice metadata
INVOICE#1   | BILL#1      | Bill details
INVOICE#1   | BILL#2      | Bill details
BILL#1      | BILL#1      | Bill metadata
BILL#1      | INVOICE#1   | Back-reference
```

Query `PK = INVOICE#1` to get invoice with all bills. Use a GSI with `SK` as partition key to query by bill.

### Time series pattern

Use **table-per-period** to manage TTL and throughput independently:

```
events_2024_01   ← high throughput (current month)
events_2023_12   ← reduced throughput (historical)
events_2023_11   ← minimal throughput, or archive to S3
```

### Large items

DynamoDB has a **400 KB item size limit**. For larger data:

1. **Compress** — gzip large attributes before storing.
2. **Vertical partition** — split items into a main item and detail items using sort keys.
3. **S3 offload** — store large payloads in S3 and keep only the S3 key in DynamoDB.

For detailed modeling examples including graph patterns, see `references/data-modeling-patterns.md`.

## Concurrency Control

### Optimistic locking

Use a version attribute and conditional writes to prevent lost updates:

```
UpdateItem(
    Key={"PK": "USER#1", "SK": "PROFILE"},
    UpdateExpression="SET #name = :name, #version = :new_version",
    ConditionExpression="#version = :current_version",
)
# Fails with ConditionalCheckFailedException if another writer updated first
```

### Transactions

`TransactWriteItems` and `TransactGetItems` provide ACID guarantees across up to **100 items** or **4 MB**:

- All-or-nothing — either all operations succeed or none do.
- Idempotent with client tokens — safe to retry.
- Cost: **2x the WCU** of non-transactional writes.

### Global tables caveat

Global tables use **last writer wins** reconciliation by default. Optimistic locking with version numbers does not work across regions — concurrent writes in different regions will not detect conflicts.

For locking patterns and the DynamoDB Lock Client, see `references/concurrency-control.md`.

## Global Tables

Global tables replicate data across AWS regions for low-latency global access and disaster recovery.

### MREC vs MRSC (v2 tables, 2019.11.21+)

| Mode | Consistency | Replication | Write conflicts |
|---|---|---|---|
| **MREC** (Multi-Region Eventually Consistent) | Eventual | Async | Last writer wins |
| **MRSC** (Multi-Region Strongly Consistent) | Strong | Synchronous | Prevented (designated owner region) |

### Write modes

- **Any-region writes (MREC)** — write to any replica, eventual consistency globally. Best for latency-sensitive workloads.
- **Single-region writes (MRSC)** — all writes go to one designated region, strong consistency. Best for conflict-sensitive data.

### Request routing

- Route reads to the nearest region for lowest latency.
- For MREC, route writes to the nearest region. Accept that concurrent writes to the same item in different regions use last-writer-wins.
- For MRSC, route writes to the designated owner region.

Global tables provide **99.999% availability** SLA (five nines) when using multi-region.

For replication architecture and routing strategies, see `references/global-tables.md`.

## Quick Reference

| Scenario | Solution |
|---|---|
| Choosing a partition key | High cardinality, uniform distribution |
| Hot partition | Write sharding with calculated suffix |
| Hierarchical data queries | Composite sort key with delimiter |
| Alternate query pattern | GSI with appropriate projection |
| Many-to-many relationships | Adjacency list pattern |
| Time series data | Table-per-period with varied throughput |
| Items over 400 KB | Compress, vertical partition, or S3 offload |
| Prevent lost updates | Optimistic locking (version + conditional write) |
| Multi-item atomicity | TransactWriteItems (up to 100 items) |
| Global low-latency reads | Global tables with nearest-region routing |
| Cross-region consistency | MRSC global tables |
| Filtered views | Sparse GSI |
| Multiple entity types | Single-table design with GSI overloading |

## Reference Files

For detailed guidance beyond this overview, consult:
- **`references/nosql-design-principles.md`** — RDBMS vs NoSQL mindset, access-pattern-first design, when to denormalize
- **`references/partition-key-design.md`** — Uniform distribution, write sharding strategies, throughput limits per partition
- **`references/sort-key-patterns.md`** — Hierarchical keys, version control, composite key patterns, range queries
- **`references/secondary-indexes.md`** — GSI vs LSI comparison, projections, sparse indexes, GSI overloading
- **`references/query-and-scan.md`** — Query vs Scan, parallel scan guidelines, page size, exponential backoff
- **`references/data-modeling-patterns.md`** — Adjacency lists, time series, large items, S3 offload, 400 KB limit
- **`references/concurrency-control.md`** — Optimistic/pessimistic locking, transactions, DynamoDB Lock Client
- **`references/global-tables.md`** — MREC vs MRSC, write modes, request routing, 99.999% availability
