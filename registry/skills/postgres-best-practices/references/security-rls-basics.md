# Enable Row Level Security for Multi-Tenant Data

Row Level Security (RLS) enforces data access at the database level, ensuring users only see their own data.

**Incorrect (application-level filtering only):**

```sql
-- Relying only on application to filter
select * from orders where user_id = $current_user_id;

-- Bug or bypass means all data is exposed!
select * from orders;  -- Returns ALL orders
```

**Correct (database-enforced RLS):**

```sql
-- Enable RLS on the table
alter table orders enable row level security;

-- Create policy for users to see only their orders
create policy orders_user_policy on orders
  for all
  using (user_id = (select nullif(current_setting('app.current_user_id', true), '')::bigint));

-- Force RLS even for table owners
alter table orders force row level security;

-- Set user context for this transaction only, then query
begin;
set local app.current_user_id = '123';
select * from orders;  -- Only returns orders for user 123
commit;

-- Parameterised form for application code (SET does not accept bind parameters)
begin;
select set_config('app.current_user_id', $1, true);  -- true = transaction-local
select * from orders;
commit;
```

If the context is not set, the query returns no rows. The policy reads the setting with `missing_ok = true` and `nullif(..., '')` because an unset context looks different depending on the connection: in the same session after `commit`, `current_setting` returns `''` and a bare `::bigint` cast fails with `invalid input syntax for type bigint: ""`; on a connection that never set the parameter (for example another connection from the pool), `current_setting` without `missing_ok` fails with `unrecognized configuration parameter`. The `(select ...)` wrapper evaluates the setting once per query instead of once per row; see `security-rls-performance.md`.

Use `set local` (or `set_config(..., true)`) inside a transaction, not plain `set`. `set` is session-scoped, so under PgBouncer transaction pooling or statement pooling the value survives into whichever client is handed that connection next. Session pooling does not leak it, because PgBouncer runs `DISCARD ALL` when the connection is returned. `set local` is discarded at commit or rollback, so it cannot leak in any mode.

A `for all` policy with only `using` applies the same predicate as `with check`, so inserts and updates that would hand a row to another user are rejected as well. Add an explicit `with check` only when the read and write predicates should differ.

Reference: [Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
