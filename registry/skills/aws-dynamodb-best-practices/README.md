# AWS DynamoDB Best Practices

Table design and data modeling conventions for DynamoDB — access-pattern-first schema design, key and index selection, single-table patterns, concurrency control, and global tables.

## Install

```bash
npx @provectusinc/awos-recruitment skill aws-dynamodb-best-practices
```

## Scope

`SKILL.md` carries the decision tables; the depth lives in `references/`:

- `nosql-design-principles.md` — access-pattern-first design, RDBMS vs NoSQL mindset, single vs multiple tables
- `key-and-index-design.md` — partition key evaluation, write sharding, sort key patterns, GSI vs LSI, projections, sparse indexes, GSI overloading, query vs scan
- `data-modeling-patterns.md` — adjacency lists, time series, large items, vertical partitioning, S3 offload
- `concurrency-control.md` — optimistic/pessimistic locking, transactions, DynamoDB Lock Client, global tables concurrency
- `global-tables.md` — MREC vs MRSC, write modes, request routing, monitoring, cost model

Out of scope by design: DynamoDB SDK/API reference and CloudFormation/Terraform resource definitions.

## Evaluations

These are the prompts to run when the description or the guidance changes. They are kept here (not under `references/`) because the install bundle ships only `SKILL.md` and flat files under `references/` — evaluation material should not land in a user's project.

Run each prompt twice: once with the skill installed and once without, then compare. Trigger evals check whether the description fires on the right tasks; behaviour evals check whether the guidance actually changes the answer.

### Trigger — should load the skill

| # | Prompt | Expected |
|---|---|---|
| T1 | "we're building multi-tenant SaaS billing and i need invoices + line items in dynamo. ~50k invoices per tenant. access patterns are 'one invoice with all its line items' and 'a tenant's invoices sorted by due date'. can you design the table?" | Skill loads. Answer enumerates access patterns first, proposes a single table with `TENANT#<id>` / `INVOICE#<id>` style keys, line items in the invoice partition, and a GSI for the due-date ordering — not a Scan plus filter. |
| T2 | "our orders table is throttling. partition key is order_date (YYYY-MM-DD), roughly 8k writes/sec during business hours. what do we do?" | Skill loads. Answer names the time-based partition key as the hot-partition cause, recommends write sharding with a calculated suffix so point reads stay direct, sizes the shard count against the write rate, and notes adaptive/burst capacity does not fix a sustained hot key. |
| T3 | "table's already live in prod — do I add an LSI or a GSI to query users by email?" | Skill loads. Answer is GSI, because an LSI can only be defined at table creation; mentions sparse-index and projection (`KEYS_ONLY`/`INCLUDE`) trade-offs. |

### Trigger — should **not** load the skill

| # | Prompt | Expected |
|---|---|---|
| N1 | "write me a terraform `aws_dynamodb_table` resource with point-in-time recovery and on-demand billing, plus a GSI block" | Skill stays out of the way — the description excludes infrastructure-as-code resource definitions. Answer comes from Terraform/AWS provider docs. |
| N2 | "my boto3 `query()` throws ValidationException on ExpressionAttributeValues, here's the traceback" | Skill stays out of the way — SDK/API debugging is explicitly out of scope. |

### Behaviour — does the guidance change the answer

| # | Prompt | Expected |
|---|---|---|
| B1 | "review this data access layer" — code whose main read path is `Scan` with a `FilterExpression` on `status` | Flags that filters do not reduce consumed RCU (the scan still reads the whole table) and proposes key conditions or a sparse GSI on `status` instead of tuning the filter. |
| B2 | "each document in our table carries a ~2 MB JSON body and writes are failing" | Names the 400 KB item size limit as the cause and lays out the three strategies with their trade-offs: compression (binary, not filterable), vertical partitioning into METADATA/BODY/COMMENTS, and S3 offload for anything over ~100 KB — including that no transaction spans DynamoDB and S3. |
| B3 | "two services increment the same counter item and we're losing updates; the table is an MREC global table across three regions" | Recommends optimistic locking (version attribute + `ConditionExpression`) for the single-region race, **and** warns that conditional writes do not arbitrate across MREC replicas — last-writer-wins resolves silently, so writes have to be partitioned by region (or routed write-to-one-region). |

Facts asserted in these expectations — the 400 KB item size limit, LSIs being definable only at table creation, filter expressions not reducing consumed capacity, and MREC's last-writer-wins conflict resolution — are checked against the [DynamoDB Developer Guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html).
