# Data Modeling Patterns

## Adjacency List Pattern

The adjacency list pattern models many-to-many relationships in a single table without joins. Each relationship is stored as an item where both the source and target appear in the key.

### Example: Invoices and bills

An invoice can reference multiple bills, and a bill can appear on multiple invoices. Each entity stores its own attributes; relationship items link them and can carry edge-specific data like the billed amount.

```
PK          | SK          | amount  | due_date   | customer    | vendor    | category
────────────|─────────────|─────────|────────────|─────────────|───────────|──────────
INVOICE#1   | INVOICE#1   |         |            | Acme Corp   |           |           ← invoice metadata
INVOICE#1   | BILL#1      | 250.00  | 2024-02-15 |             |           |           ← edge: invoice → bill
INVOICE#1   | BILL#2      | 180.00  | 2024-03-01 |             |           |           ← edge: invoice → bill
BILL#1      | BILL#1      |         |            |             | CloudCo   | hosting   ← bill metadata
BILL#1      | INVOICE#1   | 250.00  |            |             |           |           ← edge: bill → invoice
BILL#2      | BILL#2      |         |            |             | NetOps    | network   ← bill metadata
BILL#2      | INVOICE#1   | 180.00  |            |             |           |           ← edge: bill → invoice
```

Items in the same partition share PK, so a single `Query` fetches an entity together with all its relationships.

### Access patterns

| Access pattern | Operation | Key condition | Returns |
|---|---|---|---|
| Invoice with all its bills | Query | `PK = INVOICE#1` | Invoice item + edge items to BILL#1, BILL#2 |
| Bill with all its invoices | Query | `PK = BILL#1` | Bill item + edge items to INVOICE#1 |
| Single relationship | GetItem | `PK = INVOICE#1, SK = BILL#1` | One edge item (amount, due_date) |
| All invoices for a bill (via GSI) | Query GSI | `SK = BILL#1` (GSI partition key) | All edge items pointing to that bill |

### GSI for reverse lookups

Create a GSI with `SK` as partition key and `PK` as sort key. This enables querying "all invoices for a given bill" without manually maintaining edge-only back-reference items (like `BILL#1 | INVOICE#1` above). Note that entity partitions (like `BILL#1 | BILL#1` storing bill attributes) still serve a purpose — the GSI only replaces the need for explicit edge items in the reverse direction.

## Time Series Pattern

Time series data has a natural write pattern: current data is hot, historical data is cold.

### Table-per-period strategy

```
events_2024_q1   ← Current quarter: high provisioned throughput
events_2023_q4   ← Previous quarter: reduced throughput
events_2023_q3   ← Older: minimal throughput or on-demand
events_2023_q2   ← Archive candidate: export to S3, delete table
```

### Key practice

Before the current period ends, **prebuild the next period's table** and redirect event traffic to it. This avoids write failures during period transitions.

### Benefits

- **Independent throughput** — current table gets high capacity; old tables get minimal.
- **Easy archival** — export old tables to S3 via DynamoDB Export, then delete.
- **Bulk lifecycle management** — delete entire tables when a period's data expires. For fine-grained per-item expiry within a period, use TTL instead.

### Within-table time series

For smaller datasets, use a single table with timestamp sort keys:

```
PK              | SK                          | data
SENSOR#temp-1   | 2024-01-15T10:30:00.000Z   | {value: 72.5}
SENSOR#temp-1   | 2024-01-15T10:31:00.000Z   | {value: 72.8}
```

Enable **TTL** on a `ttl` attribute to automatically expire old readings.

## Large Items

DynamoDB enforces a **400 KB item size limit**. Use `ReturnConsumedCapacity` on writes to monitor item sizes approaching this limit. Strategies for large data:

### 1. Compression

Gzip or LZO large string/binary attributes before writing. Best when the attribute is large but you don't need to filter on it — compressed values are stored as `Binary` type and **cannot be used in filter expressions**.

### 2. Vertical partitioning

Split a logical item into multiple DynamoDB items:

```
PK      | SK          | data
DOC#1   | METADATA    | {title, author, created_at}        ← small, frequently read
DOC#1   | BODY        | {content: "...long text..."}       ← large, rarely read
DOC#1   | COMMENTS    | {comments: [...]}                  ← medium, append-heavy
```

Query only the parts you need. This reduces RCU for common access patterns.

### 3. S3 offload

Store large payloads in S3 and keep a pointer in DynamoDB:

```
PK      | SK       | s3_key                      | metadata
DOC#1   | FILE     | s3://bucket/docs/1/file.pdf | {size: 5242880, type: "pdf"}
```

Best for: binary files, images, large JSON documents, anything over ~100 KB.

Note: DynamoDB does not support transactions that span DynamoDB and S3. Your application must handle failures — including cleaning up orphaned S3 objects if the DynamoDB write fails (or vice versa).

## One-to-Many Patterns

### Denormalized (preferred for read-heavy)

Store child entities as items in the parent's partition:

```
PK          | SK              | data
ORDER#1     | ORDER#1         | {customer, total, date}
ORDER#1     | ITEM#1          | {product, qty, price}
ORDER#1     | ITEM#2          | {product, qty, price}
ORDER#1     | SHIPMENT#1      | {carrier, tracking}
```

### Normalized with GSI (when children need independent access)

```
PK          | SK          | GSI1PK      | data
ORDER#1     | METADATA    | CUST#alice  | {total, date}
ITEM#1      | METADATA    | ORDER#1     | {product, qty}
ITEM#2      | METADATA    | ORDER#1     | {product, qty}
```

GSI1 (`GSI1PK` as PK) enables "get all items for an order" and "get all orders for a customer."

## Anti-Patterns

- **Defaulting to one table per entity type without considering access patterns** — may miss opportunities to fetch related data in a single query. Multi-table designs are valid when entities have independent access patterns, but should be a deliberate choice.
- **Storing large lists in a single attribute** — hits the 400 KB limit; prefer individual items.
- **Using Scan for relationships** — design keys and indexes to support Query-based access.
- **Over-normalization** — in DynamoDB, some data duplication is expected and beneficial.
