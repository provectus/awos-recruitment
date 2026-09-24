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
  using (user_id = current_setting('app.current_user_id')::bigint);

-- Force RLS even for table owners
alter table orders force row level security;

-- Set user context and query
set app.current_user_id = '123';
select * from orders;  -- Only returns orders for user 123
```

Set the user context inside a transaction when connections are pooled:

```sql
-- `set` is session-scoped: on a pooled connection the value survives into
-- whichever client is handed that connection next. `set local` is discarded
-- at commit or rollback, so it cannot leak.
begin;
set local app.current_user_id = '456';
select * from orders;  -- Only returns orders for user 456
commit;
```

A `for all` policy with only `using` applies the same predicate as `with check`, so inserts and updates that would hand a row to another user are rejected as well. Add an explicit `with check` only when the read and write predicates should differ.

Reference: [Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
