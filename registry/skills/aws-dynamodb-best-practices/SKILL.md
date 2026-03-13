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

DynamoDB is not a relational database — designing it like one leads to poor performance and high costs. Schema follows queries, not the other way around. Identify all access patterns before creating tables.

See `references/nosql-design-principles.md` for access-pattern-first design, RDBMS migration thinking, and when to use single vs multiple tables.

## Key and Index Design

Partition key choice determines data distribution — poor keys create hot partitions. Sort keys enable range queries and hierarchical organization. Secondary indexes serve access patterns the primary key cannot.

Key decisions:
- **Partition key**: high cardinality, uniform distribution. Shard when a natural key has hot spots.
- **Sort key**: encode hierarchy with delimiters, use prefixes for entity types and versioning.
- **GSI vs LSI**: prefer GSI (flexible, no size limit). Use LSI only when strongly consistent reads on an alternate sort key are required.
- **Query vs Scan**: always prefer Query. Scan is a last resort — use parallel scan for large tables, schedule during off-peak.

See `references/key-and-index-design.md` for partition key evaluation, sharding strategies, sort key patterns, GSI overloading, sparse indexes, and query optimization.

## Data Modeling Patterns

DynamoDB data modeling centers on denormalization and item collections. Key patterns:
- **Adjacency list** — many-to-many relationships in a single table.
- **Table-per-period** — time series with independent throughput per period.
- **Vertical partitioning** — split large items across sort keys.
- **S3 offload** — store payloads over ~100 KB in S3 with a DynamoDB pointer.

See `references/data-modeling-patterns.md` for validated patterns with examples, access pattern tables, and trade-offs.

## Concurrency Control

Individual writes are atomic. Locking is only needed for read-modify-write cycles:
- **Optimistic locking** — version attribute + conditional write. Best for low contention.
- **Transactions** — `TransactWriteItems` for multi-item atomicity (up to 100 items / 4 MB, 2x WCU cost).
- **Lock client** — distributed locks for long-running exclusive operations.

See `references/concurrency-control.md` for decision matrix, retry strategies, and global tables concurrency caveats.

## Global Tables

Global tables replicate data across regions for low-latency global access and disaster recovery (99.999% availability SLA).

- **MREC** — async replication, last-writer-wins conflicts. Lower latency, supports transactions.
- **MRSC** — sync replication, active-active, conflicts rejected (`ReplicatedWriteConflictException`). Zero RPO, but requires exactly 3 regions, no transactions, no TTL.
- **Write modes** are application-level routing choices (write-to-any, write-to-one, write-to-your-region) — independent of consistency mode.

See `references/global-tables.md` for MREC vs MRSC trade-offs, write mode selection, and operational guidance.

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
| Cross-region consistency | MRSC global tables (3 regions) |
| Filtered views | Sparse GSI |
| Multiple entity types | Single-table design with GSI overloading |

## Reference Files

- **`references/nosql-design-principles.md`** — Access-pattern-first design, RDBMS vs NoSQL mindset, when to denormalize, when to use multiple tables
- **`references/key-and-index-design.md`** — Partition key evaluation, write sharding, sort key patterns, GSI vs LSI, projections, sparse indexes, GSI overloading, query vs scan optimization
- **`references/data-modeling-patterns.md`** — Adjacency lists, time series, large items, vertical partitioning, S3 offload
- **`references/concurrency-control.md`** — Optimistic/pessimistic locking, transactions, DynamoDB Lock Client, global tables concurrency
- **`references/global-tables.md`** — MREC vs MRSC, write modes, request routing, monitoring, cost model
