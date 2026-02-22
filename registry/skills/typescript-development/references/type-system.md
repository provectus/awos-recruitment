# TypeScript Type System Reference

## Generics

### Basic generics

```typescript
function identity<T>(value: T): T {
  return value;
}

function first<T>(items: T[]): T | undefined {
  return items[0];
}
```

### Constrained generics

```typescript
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key];
}

function merge<T extends object, U extends object>(a: T, b: U): T & U {
  return { ...a, ...b };
}
```

### Generic interfaces and types

```typescript
interface Repository<T> {
  findById(id: string): Promise<T | null>;
  findAll(): Promise<T[]>;
  save(entity: T): Promise<T>;
  delete(id: string): Promise<void>;
}

type Wrapper<T> = {
  value: T;
  timestamp: number;
};
```

### Generic defaults

```typescript
interface PaginatedResult<T, M = Record<string, unknown>> {
  items: T[];
  total: number;
  meta: M;
}

// M defaults to Record<string, unknown> when not specified
const result: PaginatedResult<User> = { items: [], total: 0, meta: {} };
```

## Utility Types

### Built-in utility types

| Type | Description | Example |
|---|---|---|
| `Partial<T>` | All properties optional | `Partial<User>` for update payloads |
| `Required<T>` | All properties required | `Required<Config>` for validated config |
| `Readonly<T>` | All properties readonly | `Readonly<State>` for immutable state |
| `Pick<T, K>` | Subset of properties | `Pick<User, "id" \| "name">` |
| `Omit<T, K>` | Exclude properties | `Omit<User, "password">` |
| `Record<K, V>` | Object with key type K and value type V | `Record<string, number>` |
| `Extract<T, U>` | Members of T assignable to U | `Extract<Status, "active" \| "pending">` |
| `Exclude<T, U>` | Members of T not assignable to U | `Exclude<Status, "deleted">` |
| `NonNullable<T>` | Remove null and undefined | `NonNullable<string \| null>` → `string` |
| `ReturnType<T>` | Return type of function | `ReturnType<typeof fetchUser>` |
| `Parameters<T>` | Parameter types as tuple | `Parameters<typeof fetchUser>` |
| `Awaited<T>` | Unwrap Promise type | `Awaited<Promise<User>>` → `User` |

### Combining utility types

```typescript
// Update payload: all fields optional except id
type UpdateUser = Partial<Omit<User, "id">> & Pick<User, "id">;

// Create payload: everything except auto-generated fields
type CreateUser = Omit<User, "id" | "createdAt" | "updatedAt">;

// Public-safe user: no sensitive fields
type PublicUser = Omit<User, "password" | "email">;
```

## Conditional Types

### Basic conditional types

```typescript
type IsString<T> = T extends string ? true : false;

type StringOrNumber<T> = T extends string ? string : number;
```

### Inferring within conditional types

```typescript
type ElementType<T> = T extends (infer E)[] ? E : T;
// ElementType<string[]> → string
// ElementType<number>   → number

type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;
// UnwrapPromise<Promise<string>> → string

type FunctionReturn<T> = T extends (...args: unknown[]) => infer R ? R : never;
```

### Distributive conditional types

```typescript
type ToArray<T> = T extends unknown ? T[] : never;
// ToArray<string | number> → string[] | number[]

// Prevent distribution with tuple wrapper
type ToArrayNonDist<T> = [T] extends [unknown] ? T[] : never;
// ToArrayNonDist<string | number> → (string | number)[]
```

## Mapped Types

### Basic mapped types

```typescript
type Optional<T> = {
  [K in keyof T]?: T[K];
};

type Immutable<T> = {
  readonly [K in keyof T]: T[K];
};

type Nullable<T> = {
  [K in keyof T]: T[K] | null;
};
```

### Key remapping (as clause)

```typescript
type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K];
};

// Getters<{ name: string; age: number }>
// → { getName: () => string; getAge: () => number }

type EventHandlers<T> = {
  [K in keyof T as `on${Capitalize<string & K>}Change`]: (value: T[K]) => void;
};
```

### Filtering keys

```typescript
type StringKeysOnly<T> = {
  [K in keyof T as T[K] extends string ? K : never]: T[K];
};
```

## Template Literal Types

### Basic template literals

```typescript
type EventName = `${"click" | "focus" | "blur"}Event`;
// "clickEvent" | "focusEvent" | "blurEvent"

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";
type ApiRoute = `/api/${string}`;
type Endpoint = `${HttpMethod} ${ApiRoute}`;
```

### With intrinsic string types

```typescript
type UpperEvent = Uppercase<"click" | "submit">;
// "CLICK" | "SUBMIT"

type CamelToSnake<S extends string> =
  S extends `${infer Head}${infer Tail}`
    ? Tail extends Uncapitalize<Tail>
      ? `${Lowercase<Head>}${CamelToSnake<Tail>}`
      : `${Lowercase<Head>}_${CamelToSnake<Tail>}`
    : S;
```

## Type Guards

### typeof guards

```typescript
function processValue(value: string | number): string {
  if (typeof value === "string") {
    return value.toUpperCase(); // narrowed to string
  }
  return value.toFixed(2); // narrowed to number
}
```

### instanceof guards

```typescript
function handleError(error: unknown): string {
  if (error instanceof TypeError) {
    return `Type error: ${error.message}`;
  }
  if (error instanceof RangeError) {
    return `Range error: ${error.message}`;
  }
  return "Unknown error";
}
```

### Custom type guard functions

```typescript
interface Dog {
  kind: "dog";
  bark(): void;
}

interface Cat {
  kind: "cat";
  purr(): void;
}

function isDog(animal: Dog | Cat): animal is Dog {
  return animal.kind === "dog";
}

// Assertion function — throws if condition not met
function assertNonNull<T>(value: T | null | undefined, name: string): asserts value is T {
  if (value === null || value === undefined) {
    throw new Error(`Expected ${name} to be defined`);
  }
}
```

### Discriminated unions with type guards

```typescript
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "rectangle"; width: number; height: number }
  | { kind: "triangle"; base: number; height: number };

function area(shape: Shape): number {
  switch (shape.kind) {
    case "circle":
      return Math.PI * shape.radius ** 2;
    case "rectangle":
      return shape.width * shape.height;
    case "triangle":
      return (shape.base * shape.height) / 2;
  }
}
```

## Discriminated Unions

### Pattern

Every member shares a literal `kind` (or `type`, `tag`) property:

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

function processResult<T>(result: Result<T>): T {
  if (result.ok) {
    return result.value; // narrowed to { ok: true; value: T }
  }
  throw result.error; // narrowed to { ok: false; error: Error }
}
```

### Exhaustive matching

```typescript
type Action =
  | { type: "increment"; amount: number }
  | { type: "decrement"; amount: number }
  | { type: "reset" };

function reduce(state: number, action: Action): number {
  switch (action.type) {
    case "increment":
      return state + action.amount;
    case "decrement":
      return state - action.amount;
    case "reset":
      return 0;
    default: {
      const _exhaustive: never = action;
      return _exhaustive;
    }
  }
}
```

## Branded Types

Prevent accidental mixing of structurally identical types:

```typescript
type Brand<T, B extends string> = T & { readonly __brand: B };

type UserId = Brand<string, "UserId">;
type OrderId = Brand<string, "OrderId">;

function createUserId(id: string): UserId {
  return id as UserId;
}

function createOrderId(id: string): OrderId {
  return id as OrderId;
}

function fetchUser(id: UserId): Promise<User> { /* ... */ }

const userId = createUserId("u-123");
const orderId = createOrderId("o-456");

fetchUser(userId);   // OK
// fetchUser(orderId); // Error: OrderId not assignable to UserId
```

## Satisfies Operator

Validate a value matches a type without widening:

```typescript
type Color = "red" | "green" | "blue";
type ColorMap = Record<Color, string | number[]>;

const palette = {
  red: "#ff0000",
  green: [0, 255, 0],
  blue: "#0000ff",
} satisfies ColorMap;

// palette.red is narrowed to string, not string | number[]
const hex: string = palette.red; // OK — no assertion needed
```

## Const Assertions

```typescript
// Without as const — type is { method: string; url: string }
const config1 = { method: "GET", url: "/api" };

// With as const — type is { readonly method: "GET"; readonly url: "/api" }
const config2 = { method: "GET", url: "/api" } as const;

// Array becomes readonly tuple
const statuses = ["active", "inactive", "pending"] as const;
// type: readonly ["active", "inactive", "pending"]

type Status = (typeof statuses)[number];
// "active" | "inactive" | "pending"
```

## Declaration Merging

### Interface merging

```typescript
interface Config {
  host: string;
  port: number;
}

// Later in code or another file — merges with above
interface Config {
  debug: boolean;
}

// Result: Config has host, port, and debug
```

### Module augmentation

```typescript
// Extend an existing module's types
declare module "./types" {
  interface AppConfig {
    newFeatureFlag: boolean;
  }
}
```
