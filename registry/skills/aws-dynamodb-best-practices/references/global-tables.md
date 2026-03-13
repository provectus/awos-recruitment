# Global Tables

## Overview

DynamoDB Global Tables replicate data across multiple AWS regions, providing low-latency reads and writes globally with up to **99.999% availability** (five nines). This document covers version 2 (2019.11.21) global tables.

## MREC vs MRSC

Both modes are **active-active** — DynamoDB accepts reads and writes in any replica region. The consistency mode cannot be changed after table creation.

| Feature | MREC (Multi-Region Eventually Consistent) | MRSC (Multi-Region Strongly Consistent) |
|---|---|---|
| Replication | Asynchronous | Synchronous (to at least one other region) |
| Write latency | Local region latency | Higher (cross-region round-trip) |
| Read consistency | Eventually consistent across regions; strongly consistent only within the region of last write | Strongly consistent globally from any replica |
| Write acceptance | Any replica region | Any replica region (concurrent writes to the same item fail with `ReplicatedWriteConflictException`) |
| Conflict handling | Last writer wins (timestamp-based, silent) | Conflicts rejected — retry succeeds once the other write completes |
| Region requirement | 2+ regions, any DynamoDB region | Exactly 3 regions (2-3 replicas + optional witness), within a single region set |
| Transactions | Supported (atomic within the originating region only) | Not supported |
| TTL | Supported | Not supported |
| Use case | Latency-sensitive global apps | Consistency-critical applications with zero RPO |

## MREC (Eventually Consistent)

### What this means for your design

- Writes are accepted locally and replicated asynchronously (typically < 1 second, no SLA). Your application may read stale data from other regions during the replication window.
- Concurrent writes to the same item in different regions are silently resolved by **last writer wins** — the losing write disappears without error. Design your write routing to minimize this risk.
- Version-based optimistic locking **does not work** across regions — two regions can independently pass the condition check and both succeed.
- Transactions are atomic only within the originating region. Other replicas may observe partial results during replication.

### Best practices

- **Choose a write mode** (see below) to control where writes land and minimize conflict risk.
- **Design for idempotency** — the same write may be replicated and applied multiple times during failover.
- When using **DynamoDB Streams**, be aware each replica generates its own stream, replication order across partitions is not guaranteed, and transactional writes may not replicate together.

## MRSC (Strongly Consistent)

### What this means for your design

- Any replica can accept reads and writes — no designated owner region needed. Strongly consistent reads from **any** replica always return the latest version.
- Concurrent writes to the same item in different regions fail with `ReplicatedWriteConflictException` (retry-safe). This is not silent like MREC — your app knows about conflicts.
- Write and strongly consistent read latency is higher (cross-region round-trip). Eventually consistent reads have no extra latency.
- **Zero RPO** — no data loss during regional failures.

### When to choose MRSC — constraints to factor in

- Requires **exactly 3 regions** within a single region set (US, EU, or AP). Use a **witness** instead of a third replica to save costs if you only need 2 read regions.
- Table must be **empty** when converting. Region topology is fixed after creation.
- **No transactions, no TTL, no LSIs.** If you need any of these, use MREC with a write-to-one-region mode instead.
- Availability depends on quorum — if only one region is reachable, only eventually consistent reads are available.

## Write Modes

Write modes are **application-level routing choices** — DynamoDB itself always accepts writes in any replica. Choose a mode based on your conflict tolerance and latency requirements.

### Write to any region (no primary)

Fully active-active. Any region accepts writes at any time. Works well for:
- **MRSC tables** — safe by default since concurrent conflicting writes are rejected.
- **MREC tables with idempotent writes** — e.g., setting a user's profile (not incrementing a counter), or append-only inserts with deterministic keys.
- **MREC tables where conflict risk is acceptable** — e.g., ad impression tracking where occasional overwrites are tolerable.

### Write to one region (single primary)

All writes route to a single active region. Other regions serve only reads. Suitable for:
- **MREC tables needing conditional writes or transactions** — these require acting against the latest data, which is only guaranteed in the region of last write.
- Simplifies failover: change the active region on failure or on a follow-the-sun schedule.

### Write to your region (mixed primary)

Each item has a home region determined by its data (e.g., a region attribute in the key). Writes for an item go only to its home region. Suitable for:
- **MREC tables with geographically partitioned data** — e.g., EU users write to eu-west-1, US users write to us-east-1.
- Lower latency than single-primary since each region is active for its own data subset.

## Read Routing

Route reads to the **nearest region** for lowest latency. Use Route 53 latency-based routing or CloudFront to direct traffic. Strongly consistent reads on MREC are only consistent within the region of last write; on MRSC, strongly consistent reads work from any replica.

## Operational Guidance

- **MREC replicas can be added/removed anytime.** MRSC topology is fixed at creation — plan your regions carefully upfront.
- **Set alarms on `ReplicationLatency`** (MREC) to detect lag before it affects consistency assumptions. For MRSC, monitor `ReplicatedWriteConflictCount` to detect cross-region contention.
- **Budget for per-region write costs.** Each write is charged in every replica region (rWCU, priced same as WCU per unit). A 3-region table costs 3x the write capacity of single-region, plus cross-region data transfer.

## Decision Guide

| Requirement | Recommendation |
|---|---|
| Low-latency global reads | Global tables (MREC or MRSC) with nearest-region read routing |
| Low-latency global writes, tolerate eventual consistency | MREC with write-to-any or write-to-your-region mode |
| Strong consistency globally, zero RPO | MRSC (3 regions, write-to-any mode) |
| Conditional writes / transactions across items | MREC with write-to-one-region mode (transactions not supported in MRSC) |
| Disaster recovery only (no global users) | MREC global tables with failover routing |
| Cost-sensitive, single-region users | Single-region table (no global tables needed) |
