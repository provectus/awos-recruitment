# Secondary Indexes

## GSI vs LSI Comparison

| Feature | GSI (Global Secondary Index) | LSI (Local Secondary Index) |
|---|---|---|
| Partition key | Any attribute (different from base table) | Same as base table |
| Sort key | Any attribute | Different attribute from base table |
| Creation | Anytime (add/remove on existing tables) | Table creation only |
| Read consistency | Eventually consistent only | Eventually or strongly consistent |
| Throughput | Separate provisioned capacity | Shares base table capacity |
| Item collection limit | No limit | 10 GB per partition key value |
| Max per table | 20 | 5 |

### When to use each

- **GSI** — when you need to query by a completely different partition key. Most common choice.
- **LSI** — when you need strongly consistent reads on an alternate sort key and the 10 GB limit is acceptable.

## Projection Strategies

The projection determines which attributes are copied into the index:

| Projection | Index size | Use case | Fetch cost |
|---|---|---|---|
| `KEYS_ONLY` | Smallest | Check existence, get IDs for batch fetch | High (must fetch from base table) |
| `INCLUDE` | Medium | Specific attributes needed for query results | Medium (fetch only missing attributes) |
| `ALL` | Largest | Complete item needed from index queries | None (all data in index) |

### Guidelines

- Start with `ALL` if read-heavy and write volume is low — simpler and avoids extra fetches.
- Use `INCLUDE` for high-write tables — reduces index write amplification.
- Use `KEYS_ONLY` for existence checks or when you always need to fetch the full item anyway.

## Sparse Indexes

Only items containing the GSI's key attributes are projected into the index. Items missing those attributes are **not included**. This creates an efficient filtered view:

### Example: Award winners

```
Base table:
PK       | SK       | name        | award
USER#1   | PROFILE  | Alice       | "Employee of Month"
USER#2   | PROFILE  | Bob         | (not present)
USER#3   | PROFILE  | Charlie     | "Top Performer"

GSI (PK: award, SK: name):
award               | name      | PK
Employee of Month   | Alice     | USER#1
Top Performer       | Charlie   | USER#3
```

Bob has no `award` attribute, so he does not appear in the GSI. Querying the GSI returns only award winners — no filtering needed.

### Use cases for sparse indexes

- Items with a specific flag or status (e.g., `is_featured`, `flagged_for_review`).
- Subset queries that would otherwise require a filter expression on the full table.
- TTL-like patterns where only "active" items have a certain attribute.

## GSI Overloading

In single-table designs, use generically named GSI attributes to serve multiple entity types:

```
PK         | SK           | GSI1PK      | GSI1SK        | data
EMP#1      | METADATA     | HR          | John Smith    | {role, hire_date}
EMP#1      | PROJECT#A    | PROJ#A      | EMP#1         | {role_in_project}
EMP#2      | METADATA     | ENGINEERING | Jane Doe      | {role, hire_date}
PROJ#A     | METADATA     | ACTIVE      | 2024-01-01    | {name, budget}
```

### Queries enabled by GSI1

| Query | GSI1PK | GSI1SK |
|---|---|---|
| All HR employees | `GSI1PK = "HR"` | — |
| Find employee by name | `GSI1PK = "HR"` | `GSI1SK = "John Smith"` |
| All members of Project A | `GSI1PK = "PROJ#A"` | — |
| Active projects by date | `GSI1PK = "ACTIVE"` | `begins_with(GSI1SK, "2024")` |

### Naming convention

Use `GSI1PK`, `GSI1SK`, `GSI2PK`, `GSI2SK`, etc. This makes it clear these are overloaded index attributes, not domain-specific fields.

## Write Amplification

Every GSI replicates writes from the base table. For a table with 3 GSIs, each write becomes 4 writes (1 base + 3 GSI). Consider this when:

- Choosing between more GSIs vs. scan-and-filter approaches.
- Deciding projection types — `ALL` projection amplifies write cost more than `KEYS_ONLY`.
- Estimating costs for write-heavy workloads.

## Item Collection Size Limit (LSI)

When using LSIs, all items sharing the same partition key (across base table and all LSIs) must fit within **10 GB**. Monitor `ItemCollectionSizeLimitExceededException`. If you anticipate large item collections, prefer GSIs which have no such limit.
