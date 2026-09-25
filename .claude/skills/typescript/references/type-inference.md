# TypeScript Type Inference Reference

What TypeScript works out on its own, and when to annotate instead.

## Contents

- [Basic Inference](#basic-inference) — variables, function returns, generic arguments
- [Contextual Typing](#contextual-typing) — callback and handler parameters
- [Infer Keyword](#infer-keyword) — extracting nested, tuple, and template-literal types
- [Control Flow Analysis](#control-flow-analysis) — how a branch refines a type
- [Best Practices](#best-practices) — when to let inference work and when to annotate

Type guards, discriminated unions, and the `satisfies` operator live in
`type-system.md`. The `in` / truthiness / `Array.isArray` narrowing idioms live in
`patterns.md`.

## Basic Inference

### Variable Inference

A `const` binding keeps the literal type of its initializer; a `let` binding widens it to
the base type, because a `let` can be reassigned.

```typescript
const userName = "John"; // type: "John"
const age = 30;          // type: 30
const isActive = true;   // type: true

let status = "active";   // type: string — widened, `let` can be reassigned
```

Widening also happens inside array and object literals, whose members are mutable:

```typescript
const items = [1, 2, 3]; // type: number[], not [1, 2, 3]

const user = {
  name: "John",
  age: 30,
}; // type: { name: string; age: number }
```

`as const` is what stops that widening. Note it is redundant on a plain `const` string —
`const mode = "dark"` is already `"dark"`. Reach for it on the literals above:

```typescript
const config = {
  api: "/api/v1",
  timeout: 5000,
} as const;
// type: { readonly api: "/api/v1"; readonly timeout: 5000 }

const levels = ["debug", "info", "warn"] as const;
// type: readonly ["debug", "info", "warn"]
```

### Function Return Inference

```typescript
// Return type inferred from the return statements
function add(a: number, b: number) {
  return a + b; // return type: number
}

function getUser(id: string) {
  return { id, name: "John", active: true };
} // return type: { id: string; name: string; active: boolean }

// Async function inference
async function fetchData(): Promise<Data> {
  const response = await fetch("/api/data");
  return response.json() as Promise<Data>;
}
```

### Generic Inference

```typescript
// Type parameter inferred from the argument
function identity<T>(value: T): T {
  return value;
}

const str = identity("hello"); // T inferred as "hello"
const num = identity(42);      // T inferred as 42

// Multiple type parameters
function pair<T, U>(first: T, second: U) {
  return [first, second] as const;
}

const result = pair("name", 42); // type: readonly [string, number]
```

The two differ because `identity` hands `T` straight back, which keeps the literal,
whereas `pair` places `T` and `U` into a tuple — a mutable member position — so the fresh
literal types widen. Two ways to keep them, both verified against `tsc`:

```typescript
// 1. const type parameters (TypeScript 5.0+)
function pairConst<const T, const U>(first: T, second: U) {
  return [first, second] as const;
}
const a = pairConst("name", 42); // readonly ["name", 42]

// 2. constrain the parameter to a primitive
function pairBound<T extends string, U extends number>(first: T, second: U) {
  return [first, second] as const;
}
const b = pairBound("name", 42); // readonly ["name", 42]
```

## Contextual Typing

A parameter with no annotation gets its type from the position it appears in. When
that position has no type to give, `strict` mode reports an implicit `any` error
rather than silently falling back to `any`.

```typescript
const numbers = [1, 2, 3, 4, 5];

// "num" is inferred as number from the array's element type
const doubled = numbers.map((num) => num * 2);

// Event handler inference
document.addEventListener("click", (event) => {
  // "event" is inferred as MouseEvent
  console.log(event.clientX, event.clientY);
});

// A bare object literal supplies no contextual type, so the parameter must be
// annotated — otherwise: "Parameter 'event' implicitly has an 'any' type. (7006)"
const handlers = {
  onClick: (event: MouseEvent) => {
    console.log(event.button);
  },
};

// Typing the object instead gives every handler its context back
interface Handlers {
  onClick: (event: MouseEvent) => void;
}

const typedHandlers: Handlers = {
  onClick: (event) => {
    // "event" is inferred as MouseEvent — no annotation needed
    console.log(event.button);
  },
};
```

## Infer Keyword

### Extract Nested Types

```typescript
// Extract the element type of an array
type ElementType<T> = T extends (infer E)[] ? E : never;

type StringElement = ElementType<string[]>; // string
type NumberElement = ElementType<number[]>; // number

// Extract a function's return type.
// The placeholder parameter list must be `never[]`. Parameters are checked
// contravariantly under `strictFunctionTypes`, so only a bottom type matches every
// signature; `(...args: unknown[])` fails to match `(a: string) => boolean` and
// silently resolves to `never`. This is the form the TypeScript handbook uses.
type ReturnOf<T> = T extends (...args: never[]) => infer R ? R : never;

type FnReturn = ReturnOf<(a: string) => boolean>; // boolean

// Extract the value of a Promise
type UnwrapPromise<T> = T extends Promise<infer U> ? U : T;

type PromiseValue = UnwrapPromise<Promise<string>>; // string
```

### Complex Infer Patterns

```typescript
// Extract the first element of a tuple.
// `unknown[]` is correct in a tuple rest position — unlike the parameter list above,
// this is an ordinary covariant match.
type First<T> = T extends [infer F, ...unknown[]] ? F : never;

type FirstElement = First<[string, number, boolean]>; // string

// Extract the last element
type Last<T> = T extends [...unknown[], infer L] ? L : never;

type LastElement = Last<[string, number, boolean]>; // boolean

// Extract a function parameter at a specific index.
// `unknown` is fine in the return position — every return type is assignable to it.
type ParamAt<T, N extends number> = T extends (...args: infer P) => unknown
  ? P[N]
  : never;

type SecondParam = ParamAt<(a: string, b: number) => void, 1>; // number
```

### Infer in Template Literals

```typescript
// Extract parts from a string literal
type ExtractRoute<T> = T extends `/${infer Resource}/${infer Id}`
  ? { resource: Resource; id: Id }
  : never;

type Route = ExtractRoute<"/users/123">;
// { resource: "users"; id: "123" }

// Parse event names
type ParseEvent<T> = T extends `on${infer Event}` ? Uncapitalize<Event> : never;

type EventName = ParseEvent<"onClick">; // "click"
```

## Control Flow Analysis

TypeScript re-infers a variable's type along each branch, so a check earlier in the
function changes what is legal later in it.

```typescript
function describe(value: string | number): string {
  if (typeof value === "string") {
    return value.toUpperCase(); // narrowed to string
  }
  return value.toFixed(2); // narrowed to number
}

// Equality narrowing: comparing two unions leaves only the types they share
function compare(a: string | number, b: string | boolean): string | undefined {
  if (a === b) {
    return a.toUpperCase(); // both narrowed to string
  }
  return undefined;
}
```

## Best Practices

### Let Inference Work

```typescript
// Bad: the initializer already says it
const userName: string = "John";
const scores: number[] = [1, 2, 3];

// Good: let inference do its job
const userName = "John";
const scores = [1, 2, 3];
```

### Annotate When Needed

```typescript
// Good: annotate function parameters and the return type
function greet(name: string): void {
  console.log(`Hello, ${name}`);
}

// Good: annotate when inference would be too wide
const status: "active" | "inactive" = "active";

// Good: annotate a return that inference cannot reach — JSON.parse returns any
interface User {
  id: string;
  name: string;
}

function parseUser(json: string): User {
  return JSON.parse(json) as User;
}
```

### Use typeof for Runtime Values

```typescript
const config = {
  api: "/api",
  timeout: 5000,
};

// Derive the type from the runtime value
type Config = typeof config;

function updateConfig(updates: Partial<Config>): void {
  Object.assign(config, updates);
}
```

### Use ReturnType for Function Types

```typescript
function createUser(name: string, email: string) {
  return {
    id: crypto.randomUUID(),
    name,
    email,
    createdAt: new Date(),
  };
}

// Derive the User type from the factory
type User = ReturnType<typeof createUser>;

function displayUser(user: User): void {
  console.log(`${user.name} (${user.email})`);
}
```
