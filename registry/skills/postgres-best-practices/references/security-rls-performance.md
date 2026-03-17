# Optimize RLS Policies for Performance

Poorly written RLS policies can cause severe performance issues. Use subqueries and indexes strategically.

**Incorrect (function called for every row):**

```sql
create policy orders_policy on orders
  using (current_setting('app.current_user_id')::bigint = user_id);  -- called per row!

-- With 1M rows, current_setting() is called 1M times
```

**Correct (wrap functions in SELECT):**

```sql
create policy orders_policy on orders
  using ((select current_setting('app.current_user_id')::bigint) = user_id);  -- Called once, cached

-- 100x+ faster on large tables
```

Use security definer functions for complex checks:

```sql
-- Create helper function (runs as definer, bypasses RLS)
create or replace function is_team_member(team_id bigint)
returns boolean
language sql
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.team_members
    where team_id = $1 and user_id = (select current_setting('app.current_user_id')::bigint)
  );
$$;

-- Use in policy (indexed lookup, not per-row check)
create policy team_orders_policy on orders
  using (is_team_member(team_id));
```

Always add indexes on columns used in RLS policies:

```sql
create index orders_user_id_idx on orders (user_id);
```

Reference: [Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
