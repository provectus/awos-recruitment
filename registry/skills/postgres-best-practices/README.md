# Postgres Best Practices

Performance optimization guidelines for Postgres. 31 rules across 8 categories — from critical (query performance, connection management) to incremental (advanced features).

> This skill is based on the [Supabase Postgres Best Practices](https://github.com/supabase/agent-skills) skill originally created by [Supabase](https://github.com/supabase). Big thanks to the authors for the foundational work.

## Install

```bash
npx @provectusinc/awos-recruitment skill postgres-best-practices
```

## Scope

The rules cover:

- Query performance (missing indexes, composite indexes, covering indexes, index types)
- Connection management (pooling, limits, idle timeouts, prepared statements)
- Security and Row-Level Security (RLS basics, RLS performance, privileges)
- Schema design (data types, constraints, partitioning, primary keys, foreign key indexes)
- Concurrency and locking (short transactions, deadlock prevention, advisory locks, SKIP LOCKED)
- Data access patterns (N+1 queries, pagination, batch inserts, upsert)
- Monitoring and diagnostics (EXPLAIN ANALYZE, pg_stat_statements, VACUUM/ANALYZE)
- Advanced features (full-text search, JSONB indexing)

## Usage

Once installed, the skill activates automatically when Claude Code detects Postgres-related tasks — writing queries, reviewing schema designs, optimizing performance, or configuring connections.

Each rule is a standalone `.md` file in `references/`:

```
references/query-missing-indexes.md
references/conn-pooling.md
```

Every rule file contains:
- Why the pattern matters
- Incorrect SQL example
- Correct SQL example
- EXPLAIN output or metrics (where applicable)
- Additional context and references

## Rule Categories

| Priority | Category | Impact | Rules |
|----------|----------|--------|-------|
| 1 | Query Performance | CRITICAL | 5 |
| 2 | Connection Management | CRITICAL | 4 |
| 3 | Security & RLS | CRITICAL | 3 |
| 4 | Schema Design | HIGH | 6 |
| 5 | Concurrency & Locking | MEDIUM-HIGH | 4 |
| 6 | Data Access Patterns | MEDIUM | 4 |
| 7 | Monitoring & Diagnostics | LOW-MEDIUM | 3 |
| 8 | Advanced Features | LOW | 2 |
