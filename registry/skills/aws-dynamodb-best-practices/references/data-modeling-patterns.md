# Data Modeling Patterns

## Adjacency List Pattern

The adjacency list pattern models many-to-many relationships in a single table without joins. Each relationship is stored as an item where both the source and target appear in the key.

### Example: Invoices and bills

```
PK          | SK          | type    | data
INVOICE#1   | INVOICE#1   | Invoice | {date, total, customer}
INVOICE#1   | BILL#1      | Edge    | {amount, due_date}
INVOICE#1   | BILL#2      | Edge    | {amount, due_date}
BILL#1      | BILL#1      | Bill    | {vendor, category}
BILL#1      | INVOICE#1   | Edge    | {amount}
BILL#2      | BILL#2      | Bill    | {vendor, category}
BILL#2      | INVOICE#1   | Edge    | {amount}
```

### Access patterns

| Query | Key condition | Result |
|---|---|---|
| Invoice + all bills | `PK = INVOICE#1` | Invoice metadata + all bill edges |
| Bill + all invoices | `PK = BILL#1` | Bill metadata + all invoice edges |
| Specific relationship | `PK = INVOICE#1, SK = BILL#1` | Single edge item |

### GSI for reverse lookups (alternative to back-references)

Instead of storing explicit back-reference items (like `BILL#1 | INVOICE#1` above), create a GSI with `SK` as partition key and `PK` as sort key. This enables querying "all invoices for a given bill" without manually maintaining bidirectional items. Choose one approach: either back-reference items or a GSI — using both is redundant.

## Time Series Pattern

Time series data has a natural write pattern: current data is hot, historical data is cold.

### Table-per-period strategy

```
events_2024_q1   ← Current quarter: high provisioned throughput
events_2023_q4   ← Previous quarter: reduced throughput
events_2023_q3   ← Older: minimal throughput or on-demand
events_2023_q2   ← Archive candidate: export to S3, delete table
```

### Benefits

- **Independent throughput** — current table gets high capacity; old tables get minimal.
- **Easy archival** — export old tables to S3 via DynamoDB Export, then delete.
- **TTL alternative** — instead of per-item TTL, drop entire tables when data expires.

### Within-table time series

For smaller datasets, use a single table with timestamp sort keys:

```
PK              | SK                          | data
SENSOR#temp-1   | 2024-01-15T10:30:00.000Z   | {value: 72.5}
SENSOR#temp-1   | 2024-01-15T10:31:00.000Z   | {value: 72.8}
```

Enable **TTL** on a `ttl` attribute to automatically expire old readings.

## Large Items

DynamoDB enforces a **400 KB item size limit**. Strategies for large data:

### 1. Compression

Gzip large string or binary attributes before writing:

```python
import gzip
import json

data = gzip.compress(json.dumps(large_payload).encode())
table.put_item(Item={"PK": "DOC#1", "SK": "BODY", "data": data})
```

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

- **One table per entity type** — loses the ability to fetch related data in one query.
- **Storing large lists in a single attribute** — hits the 400 KB limit; prefer individual items.
- **Using Scan for relationships** — design keys and indexes to support Query-based access.
- **Over-normalization** — in DynamoDB, some data duplication is expected and beneficial.
