# NoSQL Design Principles for DynamoDB

## Why NoSQL Thinking Matters

Relational databases are designed for flexible querying — you normalize data and write queries later. DynamoDB inverts this: you design your schema around the queries you need to run. Applying RDBMS patterns to DynamoDB results in excessive table counts, expensive scans, and poor performance.

## Access-Pattern-First Design

Before creating a single table, list every access pattern your application needs:

1. **Enumerate all read and write operations** — e.g., "get user by ID," "list orders by date," "find all items in a category."
2. **Identify primary key candidates** — which attribute uniquely identifies items? Which attribute enables the most common queries?
3. **Design keys to satisfy patterns** — partition key for equality lookups, sort key for range queries and hierarchical access.
4. **Add secondary indexes only for patterns the primary key cannot serve.**

## Data Size, Shape, and Velocity

NoSQL databases scale by distributing data across partitions. Your design must account for:

| Factor | Impact on design |
|---|---|
| **Size** | Total data determines partition count. More partitions = more parallelism. |
| **Shape** | Item structure varies by entity type. Heterogeneous items coexist in one table. |
| **Velocity** | Read/write rate per key determines if you need sharding or caching. |

## Keep Related Data Together

In RDBMS, normalization separates entities into tables joined at query time. In DynamoDB, there are no joins. Instead:

- **Denormalize** — duplicate data across items to avoid multi-table lookups.
- **Use composite keys** — pack related data into the same partition using sort key prefixes.
- **Item collections** — all items sharing the same partition key form a collection that can be queried in one operation.

### Example: User with orders

```
PK          | SK              | Attributes
USER#alice  | PROFILE         | {name, email, created_at}
USER#alice  | ORDER#2024-001  | {total, status, items}
USER#alice  | ORDER#2024-002  | {total, status, items}
```

One query on `PK = USER#alice` returns the profile and all orders — no joins needed.

## When to Use Multiple Tables

Single-table design is the default recommendation, but consider multiple tables when:

- **Entities have completely independent access patterns** with no cross-entity queries.
- **Wildly different throughput requirements** — e.g., a high-velocity event stream alongside a low-traffic config store.
- **Team boundaries** — separate teams owning separate services may prefer separate tables for operational isolation.

## Migration from RDBMS

When migrating from a relational database:

1. Start with the existing query patterns, not the existing schema.
2. Identify which joins can be replaced by denormalization.
3. Map foreign keys to composite sort keys or GSI relationships.
4. Accept data duplication as a trade-off for read performance.
5. Design update strategies for denormalized data (e.g., DynamoDB Streams + Lambda for propagation).
