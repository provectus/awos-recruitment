# Sort Key Patterns

## Role of the Sort Key

The sort key determines the order of items within a partition and enables **range queries**. Combined with the partition key, it forms the table's composite primary key — each (PK, SK) pair must be unique.

## Hierarchical Composite Keys

Encode hierarchy levels with a delimiter to support queries at any level of specificity:

```
PK: LOCATION
SK: USA#CA#San Francisco#94105
SK: USA#CA#San Francisco#94107
SK: USA#CA#Los Angeles#90001
SK: USA#NY#New York#10001
```

### Query examples

| Access pattern | KeyCondition |
|---|---|
| All US locations | `PK = LOCATION AND begins_with(SK, "USA#")` |
| All California | `PK = LOCATION AND begins_with(SK, "USA#CA#")` |
| San Francisco only | `PK = LOCATION AND begins_with(SK, "USA#CA#San Francisco#")` |
| Specific zip code | `PK = LOCATION AND SK = "USA#CA#San Francisco#94105"` |

### Delimiter choice

Use `#` as a standard delimiter. Avoid characters that appear in your data values. If values can contain `#`, use a multi-character delimiter like `##` or `|`.

## Version Control Pattern

Store the latest version at a well-known sort key and historical versions with numbered prefixes:

```
PK          | SK               | Data
DOC#123     | v0_metadata      | {title: "Latest", body: "..."}
DOC#123     | v0_permissions   | {readers: [...], writers: [...]}
DOC#123     | v1_metadata      | {title: "First draft", body: "..."}
DOC#123     | v2_metadata      | {title: "Revised", body: "..."}
```

- **Get latest:** `SK = v0_metadata`
- **Get specific version:** `SK = v2_metadata`
- **Get all versions:** `begins_with(SK, "v")` then filter or sort by version number
- **Update:** Write new version as `v{N+1}_metadata`, then overwrite `v0_metadata` with the same data

## Entity-Type Prefixes

In single-table designs, use sort key prefixes to distinguish entity types within a partition:

```
PK          | SK              | Type
USER#alice  | PROFILE         | User profile
USER#alice  | ORDER#2024-001  | Order
USER#alice  | ORDER#2024-002  | Order
USER#alice  | ADDR#home       | Address
USER#alice  | ADDR#work       | Address
```

Query `begins_with(SK, "ORDER#")` to get all orders for a user.

## Timestamp-Based Sort Keys

Use ISO 8601 timestamps as sort keys for chronological ordering:

```
PK              | SK                          | Event
DEVICE#sensor1  | 2024-01-15T10:30:00.000Z   | Reading
DEVICE#sensor1  | 2024-01-15T10:31:00.000Z   | Reading
```

- **Latest N items:** Query with `ScanIndexForward=False` and `Limit=N`.
- **Time range:** `SK BETWEEN "2024-01-15T10:00:00Z" AND "2024-01-15T11:00:00Z"`.

## Compound Sort Keys for Multi-Attribute Queries

Combine multiple attributes when you need to query by a prefix subset:

```
SK: STATUS#CREATED_DATE#ORDER_ID
SK: ACTIVE#2024-01-15#ORD-001
SK: ACTIVE#2024-01-16#ORD-002
SK: SHIPPED#2024-01-15#ORD-003
```

Query `begins_with(SK, "ACTIVE#2024-01")` returns all active orders from January 2024. The order of attributes in the sort key matters — put the most common filter first.

## Key Design Checklist

- [ ] Does the sort key enable the top access patterns as range queries?
- [ ] Are hierarchy levels ordered from broadest to most specific?
- [ ] Is the delimiter safe (not present in data values)?
- [ ] For versioned data, is there a predictable key for "latest"?
- [ ] For time-based queries, is the timestamp format sortable (ISO 8601)?
