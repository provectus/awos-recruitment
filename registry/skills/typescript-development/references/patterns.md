# TypeScript Patterns Reference

## Contents

- [Immutability Patterns](#immutability-patterns) — readonly properties, arrays, frozen objects
- [Error Handling Patterns](#error-handling-patterns) — typed error classes, `Result`, `unknown` catches
- [Async Patterns](#async-patterns) — signatures, concurrency, typed async iterators
- [Builder Pattern](#builder-pattern) — chainable typed query builder
- [Type-Safe Event Emitter](#type-safe-event-emitter) — event map keyed by name
- [Overloaded Functions](#overloaded-functions) — standalone and method overloads
- [Module Patterns](#module-patterns) — namespace-like modules, lazy init, type-only exports
- [Enum Alternatives](#enum-alternatives) — why const objects beat `enum`
- [Assertion Functions](#assertion-functions) — `assertDefined`, `assertNever`
- [Narrowing Patterns](#narrowing-patterns) — `in`, truthiness, `Array.isArray`

## Immutability Patterns

### Readonly properties

```typescript
interface Config {
  readonly host: string;
  readonly port: number;
}

// Deep readonly
type DeepReadonly<T> = {
  readonly [K in keyof T]: T[K] extends object ? DeepReadonly<T[K]> : T[K];
};
```

### Readonly arrays and tuples

```typescript
function processItems(items: readonly string[]): void {
  // items.push("new"); // Error: push does not exist on readonly string[]
  const copy = [...items, "new"]; // OK — creates new array
}

// ReadonlyArray<T> is equivalent to readonly T[]
function sum(numbers: ReadonlyArray<number>): number {
  return numbers.reduce((acc, n) => acc + n, 0);
}
```

### Frozen objects

```typescript
const DEFAULTS = Object.freeze({
  timeout: 5000,
  retries: 3,
  baseUrl: "http://localhost",
} as const);
```

## Error Handling Patterns

### Typed error classes

```typescript
class AppError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly statusCode: number = 500,
  ) {
    super(message);
    this.name = "AppError";
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(`${resource} with id ${id} not found`, "NOT_FOUND", 404);
    this.name = "NotFoundError";
  }
}

class ValidationError extends AppError {
  constructor(
    message: string,
    readonly fields: Record<string, string>,
  ) {
    super(message, "VALIDATION_ERROR", 400);
    this.name = "ValidationError";
  }
}
```

### Result type pattern

Represent success/failure without exceptions:

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

function ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

function err<E>(error: E): Result<never, E> {
  return { ok: false, error };
}

// Usage
function parsePort(input: string): Result<number, string> {
  const port = parseInt(input, 10);
  if (isNaN(port) || port < 0 || port > 65535) {
    return err(`Invalid port: ${input}`);
  }
  return ok(port);
}

const result = parsePort("8080");
if (result.ok) {
  console.log(result.value); // number
} else {
  console.error(result.error); // string
}
```

### Unknown in catch blocks

```typescript
try {
  riskyOperation();
} catch (error: unknown) {
  if (error instanceof AppError) {
    handleAppError(error);
  } else if (error instanceof Error) {
    handleGenericError(error);
  } else {
    handleUnknown(String(error));
  }
}
```

## Async Patterns

### Async function signatures

```typescript
async function fetchData(id: string): Promise<Data> {
  const response = await fetch(`/api/data/${id}`);
  if (!response.ok) {
    throw new AppError("Fetch failed", "FETCH_ERROR", response.status);
  }
  return response.json() as Promise<Data>;
}
```

### Concurrent operations

```typescript
// Run in parallel, fail if any fails
const [users, orders] = await Promise.all([
  fetchUsers(),
  fetchOrders(),
]);

// Run in parallel, get individual results
const results = await Promise.allSettled([
  fetchUsers(),
  fetchOrders(),
]);

for (const result of results) {
  if (result.status === "fulfilled") {
    process(result.value);
  } else {
    logError(result.reason);
  }
}
```

### Typed async iterators

```typescript
async function* paginate<T>(
  fetcher: (page: number) => Promise<T[]>,
): AsyncGenerator<T[], void, undefined> {
  let page = 0;
  while (true) {
    const items = await fetcher(page);
    if (items.length === 0) break;
    yield items;
    page++;
  }
}

// Usage
for await (const batch of paginate(fetchUserPage)) {
  processBatch(batch);
}
```

## Builder Pattern

```typescript
class QueryBuilder<T> {
  private filters: Array<(item: T) => boolean> = [];
  private sortKey?: keyof T;
  private sortOrder: "asc" | "desc" = "asc";
  private limitCount?: number;

  where(predicate: (item: T) => boolean): this {
    this.filters.push(predicate);
    return this;
  }

  orderBy(key: keyof T, order: "asc" | "desc" = "asc"): this {
    this.sortKey = key;
    this.sortOrder = order;
    return this;
  }

  limit(count: number): this {
    this.limitCount = count;
    return this;
  }

  execute(items: T[]): T[] {
    let result = items.filter((item) =>
      this.filters.every((f) => f(item)),
    );

    if (this.sortKey !== undefined) {
      const key = this.sortKey;
      const dir = this.sortOrder === "asc" ? 1 : -1;
      result.sort((a, b) => (a[key] > b[key] ? dir : -dir));
    }

    if (this.limitCount !== undefined) {
      result = result.slice(0, this.limitCount);
    }

    return result;
  }
}
```

## Type-Safe Event Emitter

```typescript
type EventMap = Record<string, unknown[]>;

class TypedEmitter<Events extends EventMap> {
  private listeners = new Map<keyof Events, Set<Function>>();

  on<K extends keyof Events>(
    event: K,
    handler: (...args: Events[K]) => void,
  ): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(handler);
  }

  emit<K extends keyof Events>(event: K, ...args: Events[K]): void {
    const handlers = this.listeners.get(event);
    if (handlers) {
      for (const handler of handlers) {
        handler(...args);
      }
    }
  }

  off<K extends keyof Events>(
    event: K,
    handler: (...args: Events[K]) => void,
  ): void {
    this.listeners.get(event)?.delete(handler);
  }
}

// Usage
interface AppEvents extends EventMap {
  userLogin: [userId: string, timestamp: number];
  error: [error: Error];
  shutdown: [];
}

const emitter = new TypedEmitter<AppEvents>();
emitter.on("userLogin", (userId, timestamp) => { /* ... */ });
emitter.emit("userLogin", "u-123", Date.now());
```

## Overloaded Functions

Use function overloads when the return type depends on the input:

```typescript
function parse(input: string, asNumber: true): number;
function parse(input: string, asNumber: false): string;
function parse(input: string, asNumber: boolean): number | string {
  return asNumber ? Number(input) : input;
}

const num = parse("42", true);    // number
const str = parse("42", false);   // string
```

### Method overloads in classes

```typescript
class Formatter {
  format(value: string): string;
  format(value: number): string;
  format(value: Date): string;
  format(value: string | number | Date): string {
    if (typeof value === "string") return value.trim();
    if (typeof value === "number") return value.toFixed(2);
    return value.toISOString();
  }
}
```

## Module Patterns

### Namespace-like modules

```typescript
// math/index.ts — re-export as a namespace-like module
export { add, subtract } from "./arithmetic.js";
export { sin, cos, tan } from "./trigonometry.js";
export { PI, E } from "./constants.js";
```

### Lazy initialization

```typescript
let cachedConnection: Connection | undefined;

export function getConnection(): Connection {
  cachedConnection ??= createConnection();
  return cachedConnection;
}
```

### Type-only exports

```typescript
// Ensure types are erased at runtime — no accidental runtime imports
export type { User, Order, Product } from "./models.js";
export { UserSchema } from "./models.js";
```

## Enum Alternatives

### Const objects over enums

SKILL.md carries the `as const` object pattern itself. What it does not spell out is the
alternative you are replacing and why:

```typescript
// Avoid — an enum emits a runtime object
enum StatusEnum {
  Active = "active",
  Inactive = "inactive",
  Pending = "pending",
}
```

**Why the const object wins:** both forms emit runtime code — the `as const` assertion is
erased, but the object literal itself survives — so the difference is in *what* they emit.
An enum compiles to a self-invoking function that fills a mutable binding, which a bundler
cannot prove is unused; a const object compiles to a plain object literal it can tree-shake.
Its values are ordinary strings, so they interoperate with plain string literals and JSON;
and it avoids the reverse-mapping quirk of numeric enums, where `StatusEnum[0]` is a
legal lookup that yields a key name. Enums also behave inconsistently across `const enum`,
`declare enum`, and `isolatedModules`, which const objects never do.

### Union types for simple cases

```typescript
type Direction = "north" | "south" | "east" | "west";
type LogLevel = "debug" | "info" | "warn" | "error";
```

## Assertion Functions

```typescript
function assertDefined<T>(
  value: T | null | undefined,
  name: string,
): asserts value is T {
  if (value === null || value === undefined) {
    throw new Error(`Expected ${name} to be defined, got ${value}`);
  }
}

function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unexpected value: ${value}`);
}

// Usage — exhaustive switch
function handleStatus(status: Status): string {
  switch (status) {
    case "active": return "Active";
    case "inactive": return "Inactive";
    case "pending": return "Pending";
    default: assertNever(status);
  }
}
```

## Narrowing Patterns

### In operator narrowing

```typescript
interface Fish { swim(): void }
interface Bird { fly(): void }

function move(animal: Fish | Bird): void {
  if ("swim" in animal) {
    animal.swim(); // narrowed to Fish
  } else {
    animal.fly(); // narrowed to Bird
  }
}
```

### Truthiness narrowing

```typescript
function printName(name: string | null | undefined): void {
  if (name) {
    console.log(name.toUpperCase()); // narrowed to string
  }
}
```

### Array.isArray narrowing

```typescript
function normalize(input: string | string[]): string[] {
  return Array.isArray(input) ? input : [input];
}
```
