---
name: postgres-best-practices
description: >-
  Postgres performance optimization and best practices. Use when writing or reviewing
  SQL queries, designing schemas, configuring connection pooling, fixing N+1 queries,
  creating indexes, implementing row-level security, diagnosing slow queries with
  EXPLAIN ANALYZE, or optimizing database performance.
---

# Postgres Best Practices

Comprehensive performance optimization guide for Postgres. 31 rules across 8 categories, prioritized by impact — from critical (query performance, connection management) to incremental (advanced features).

## Rule Categories by Priority

| Priority | Category                 | Impact      | Prefix      |
| -------- | ------------------------ | ----------- | ----------- |
| 1        | Query Performance        | CRITICAL    | `query-`    |
| 2        | Connection Management    | CRITICAL    | `conn-`     |
| 3        | Security & RLS           | CRITICAL    | `security-` |
| 4        | Schema Design            | HIGH        | `schema-`   |
| 5        | Concurrency & Locking    | MEDIUM-HIGH | `lock-`     |
| 6        | Data Access Patterns     | MEDIUM      | `data-`     |
| 7        | Monitoring & Diagnostics | LOW-MEDIUM  | `monitor-`  |
| 8        | Advanced Features        | LOW         | `advanced-` |

## Quick Reference

### 1. Query Performance (CRITICAL)

- `query-missing-indexes` - Add indexes on WHERE and JOIN columns
- `query-composite-indexes` - Create composite indexes for multi-column queries
- `query-covering-indexes` - Use covering indexes to avoid table lookups
- `query-partial-indexes` - Use partial indexes for filtered queries
- `query-index-types` - Choose the right index type for your data

### 2. Connection Management (CRITICAL)

- `conn-pooling` - Use connection pooling for all applications
- `conn-limits` - Set appropriate connection limits
- `conn-idle-timeout` - Configure idle connection timeouts
- `conn-prepared-statements` - Use prepared statements correctly with pooling

### 3. Security & RLS (CRITICAL)

- `security-rls-basics` - Enable Row Level Security for multi-tenant data
- `security-rls-performance` - Optimize RLS policies for performance
- `security-privileges` - Apply principle of least privilege

### 4. Schema Design (HIGH)

- `schema-data-types` - Choose appropriate data types
- `schema-constraints` - Add constraints safely in migrations
- `schema-primary-keys` - Select optimal primary key strategy
- `schema-foreign-key-indexes` - Index foreign key columns
- `schema-partitioning` - Partition large tables for better performance
- `schema-lowercase-identifiers` - Use lowercase identifiers for compatibility

### 5. Concurrency & Locking (MEDIUM-HIGH)

- `lock-short-transactions` - Keep transactions short to reduce lock contention
- `lock-deadlock-prevention` - Prevent deadlocks with consistent lock ordering
- `lock-advisory` - Use advisory locks for application-level locking
- `lock-skip-locked` - Use SKIP LOCKED for non-blocking queue processing

### 6. Data Access Patterns (MEDIUM)

- `data-n-plus-one` - Eliminate N+1 queries with batch loading
- `data-pagination` - Use cursor-based pagination instead of OFFSET
- `data-batch-inserts` - Batch INSERT statements for bulk data
- `data-upsert` - Use UPSERT for insert-or-update operations

### 7. Monitoring & Diagnostics (LOW-MEDIUM)

- `monitor-explain-analyze` - Use EXPLAIN ANALYZE to diagnose slow queries
- `monitor-pg-stat-statements` - Enable pg_stat_statements for query analysis
- `monitor-vacuum-analyze` - Maintain table statistics with VACUUM and ANALYZE

### 8. Advanced Features (LOW)

- `advanced-full-text-search` - Use tsvector for full-text search
- `advanced-jsonb-indexing` - Index JSONB columns for efficient querying

## How to Use

Each rule file in `references/` contains: explanation, incorrect/correct SQL examples, EXPLAIN output, and context. Read individual files as needed.
