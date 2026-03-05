---
name: postgres-best-practices
description: Postgres performance optimization and best practices. Use this skill when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.
---

# Postgres Best Practices

Comprehensive performance optimization guide for Postgres. 31 rules across 8 categories, prioritized by impact — from critical (query performance, connection management) to incremental (advanced features).

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Query Performance | CRITICAL | `query-` |
| 2 | Connection Management | CRITICAL | `conn-` |
| 3 | Security & RLS | CRITICAL | `security-` |
| 4 | Schema Design | HIGH | `schema-` |
| 5 | Concurrency & Locking | MEDIUM-HIGH | `lock-` |
| 6 | Data Access Patterns | MEDIUM | `data-` |
| 7 | Monitoring & Diagnostics | LOW-MEDIUM | `monitor-` |
| 8 | Advanced Features | LOW | `advanced-` |

## How to Use

Each rule file in `references/` contains: explanation, incorrect/correct SQL examples, EXPLAIN output, and context. Read individual files as needed.
