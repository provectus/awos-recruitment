# Global Tables

## Overview

DynamoDB Global Tables replicate data across multiple AWS regions, providing low-latency reads and writes globally with up to **99.999% availability** (five nines). This document covers version 2 (2019.11.21) global tables.

## MREC vs MRSC

| Feature | MREC (Multi-Region Eventually Consistent) | MRSC (Multi-Region Strongly Consistent) |
|---|---|---|
| Replication | Asynchronous | Synchronous |
| Write latency | Local region latency | Higher (cross-region round-trip) |
| Read consistency | Eventually consistent across regions | Strongly consistent globally |
| Write location | Any replica region | Designated owner region per item/table |
| Conflict resolution | Last writer wins (timestamp-based) | No conflicts (single writer) |
| Use case | Latency-sensitive global apps | Consistency-critical applications |

## MREC (Eventually Consistent)

### How it works

1. Write lands in the local region.
2. DynamoDB asynchronously replicates to all other replica regions.
3. Replication typically completes within **1 second** but is not guaranteed.
4. Concurrent writes to the same item in different regions resolve via **last writer wins** (based on timestamps).

### Best practices

- **Avoid concurrent writes to the same item** from different regions when possible.
- **Design for idempotency** — the same write may be replicated and applied multiple times during failover.
- Do not rely on version-based optimistic locking across regions — it cannot detect cross-region conflicts.
- Use **DynamoDB Streams** for cross-region event processing, but be aware that each replica generates its own stream.

### Conflict example

```
Region A: UpdateItem(PK="USER#1", SET name="Alice")   at T=100ms
Region B: UpdateItem(PK="USER#1", SET name="Bob")     at T=101ms

Result: name="Bob" (last writer wins, timestamp T=101ms > T=100ms)
```

## MRSC (Strongly Consistent)

### How it works

1. Each item (or the entire table) has a **designated owner region**.
2. Writes are only accepted in the owner region.
3. Writes are synchronously replicated to other regions before acknowledgment.
4. Reads in any region can request strong consistency.

### Write modes

| Mode | Description | Configuration |
|---|---|---|
| **Table-level owner** | All writes go to one region | Set at table level |
| **Item-level owner** | Each item has an owner region attribute | Requires application logic |

### Trade-offs

- **Higher write latency** due to synchronous replication.
- **Reduced availability during regional outages** — if the owner region is down, writes are blocked until failover.
- **No conflict resolution needed** — by design, only one region accepts writes per item.

## Request Routing Strategies

### Read routing

Route reads to the **nearest region** for lowest latency:

```
User in EU → eu-west-1 (nearest replica)
User in US → us-east-1 (nearest replica)
User in Asia → ap-southeast-1 (nearest replica)
```

Use Route 53 latency-based routing or CloudFront to direct traffic.

### Write routing (MREC)

Route writes to the **nearest region**. Accept eventual consistency and last-writer-wins semantics:

```
User in EU → writes to eu-west-1
User in US → writes to us-east-1
```

### Write routing (MRSC)

Route all writes to the **designated owner region**, regardless of user location:

```
All users → writes to us-east-1 (owner region)
All users → reads from nearest replica
```

## Operational Considerations

### Adding/removing replicas

- Adding a replica: DynamoDB creates the replica and backfills existing data. Table remains available during this process.
- Removing a replica: the regional table is deleted. This is irreversible for that region.

### Monitoring

Key CloudWatch metrics for global tables:

| Metric | What it tells you |
|---|---|
| `ReplicationLatency` | Time for changes to replicate to other regions |
| `PendingReplicationCount` | Number of items waiting to be replicated |
| `ConditionalCheckFailedRequests` | Failed conditional writes (possible contention) |

### Cost implications

- Each replica has its own capacity (provisioned or on-demand).
- **Replicated write capacity units (rWCU)** are charged instead of standard WCU — typically **1.5x** the cost of single-region writes.
- Storage is charged per replica.

## Decision Guide

| Requirement | Recommendation |
|---|---|
| Low-latency global reads | Global tables with nearest-region routing |
| Low-latency global writes, can tolerate eventual consistency | MREC with nearest-region writes |
| Strong consistency globally | MRSC with designated owner region |
| Disaster recovery only (no global users) | Global tables with failover routing |
| Cost-sensitive, single-region users | Single-region table (no global tables needed) |
