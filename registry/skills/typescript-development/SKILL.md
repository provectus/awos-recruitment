---
name: typescript-development
description: Modern TypeScript conventions for library-agnostic code — strict mode, naming, type annotations, the type system (generics, utility types, conditional and mapped types), discriminated unions, error handling, async patterns, immutability, and project structure. Use when the user asks to "write TypeScript code", "create a TypeScript module", "define TypeScript types", "add type annotations", "use generics", "handle errors in TypeScript", "set up tsconfig" or "organize a TypeScript project", or whenever writing any TypeScript that is not tied to a specific library or framework.
---

# TypeScript Development

This skill covers modern TypeScript best practices for writing clean, type-safe code. It focuses on the language itself — no library or framework specifics. Apply these conventions to all TypeScript code in the project.

## Strict Mode

Always enable `strict: true` in `tsconfig.json`. Never disable individual strict flags. This is non-negotiable — it catches entire categories of bugs at compile time.

Key strict behaviors:
- `null` and `undefined` are distinct types (no implicit null)
- Every value must have a known type (no implicit `any`)
- Catch clause variables are `unknown`, not `any`

## Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| Variables, functions | camelCase | `getUserName`, `isActive` |
| Classes | PascalCase | `UserService`, `HttpClient` |
| Interfaces | PascalCase (no `I` prefix) | `User`, not `IUser` |
| Type aliases | PascalCase | `ApiResponse`, `EventMap` |
| Constants | camelCase or UPPER_SNAKE | `maxRetries` or `MAX_RETRIES` |
| Enum-like objects | PascalCase key, camelCase/string values | `Status.Active` |
| Generic parameters | Single uppercase or descriptive | `T`, `TResult`, `K extends keyof T` |
| File names | kebab-case | `user-service.ts`, `api-client.ts` |
| Boolean variables | Prefix with `is`, `has`, `can`, `should` | `isValid`, `hasPermission` |

## Type Annotations

### When to annotate explicitly

- Function parameters — always
- Function return types — always for exported functions, optional for local functions
- Class properties — always
- Variables — only when the type cannot be inferred

```typescript
// Parameters and return: always annotate
function calculateTotal(items: LineItem[], taxRate: number): number {
  return items.reduce((sum, item) => sum + item.price, 0) * (1 + taxRate);
}

// Variable: skip annotation when inferred
const total = calculateTotal(items, 0.1); // inferred as number

// Variable: annotate when not obvious
const cache: Map<string, User> = new Map();
```

### Prefer interfaces for object shapes

```typescript
// Prefer interface for object shapes
interface User {
  id: string;
  name: string;
  email: string;
}

// Use type alias for unions, intersections, mapped types
type Status = "active" | "inactive" | "pending";
type StringKeys<T> = Extract<keyof T, string>;
```

### Avoid `any`

Use `unknown` instead of `any` for values of uncertain type. Narrow with type guards before use:

```typescript
// Bad
function parse(input: any): string { return input.name; }

// Good
function parse(input: unknown): string {
  if (typeof input === "object" && input !== null && "name" in input) {
    return String((input as { name: unknown }).name);
  }
  throw new Error("Invalid input");
}
```

**Acceptable uses of `any`:** Only when interfacing with untyped external code and a proper type cannot be defined. Always add a comment explaining why.

## Discriminated Unions

Model state variants with a shared literal discriminant:

```typescript
type LoadingState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };
```

Always include an exhaustive check using `never`:

```typescript
function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${value}`);
}

function render<T>(state: LoadingState<T>): string {
  switch (state.status) {
    case "idle": return "Ready";
    case "loading": return "Loading...";
    case "success": return String(state.data);
    case "error": return state.error.message;
    default: return assertNever(state);
  }
}
```

## Error Handling

### Catch unknown errors

Under `strict`, a catch variable is already `unknown`. Narrow it before touching it:

```typescript
try {
  await riskyOperation();
} catch (error: unknown) {
  if (error instanceof AppError) {
    handleAppError(error);
  } else {
    handleUnknown(String(error));
  }
}
```

### Custom error classes

Extend `Error`, carry a machine-readable `code`, and reassign `this.name` so stack traces
name the subclass rather than `Error`. The full `AppError` / `NotFoundError` /
`ValidationError` hierarchy is in `references/patterns.md`.

### Result type over exceptions

For expected failure paths, prefer a typed `Result` over throwing:

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };
```

The `ok()` / `err()` constructors and a worked example are in `references/patterns.md`.

## Const Objects Over Enums

Prefer `as const` objects over TypeScript `enum`:

```typescript
const Status = {
  Active: "active",
  Inactive: "inactive",
  Pending: "pending",
} as const;

type Status = (typeof Status)[keyof typeof Status];
```

**Why:** `as const` is erased, but the object literal still emits — as plain data a bundler
can tree-shake, not the self-invoking function an `enum` compiles to. Values stay ordinary
strings, so they interoperate with plain strings and JSON.

## Async Code

- Always specify `Promise<T>` return types on async functions
- Use `Promise.all` for independent concurrent operations
- Use `Promise.allSettled` when partial failure is acceptable
- Never use `void` for async function returns — use `Promise<void>`

```typescript
async function fetchUserData(id: string): Promise<UserData> {
  const [profile, orders] = await Promise.all([
    fetchProfile(id),
    fetchOrders(id),
  ]);
  return { profile, orders };
}
```

## Immutability

- Use `readonly` on properties that should not change after initialization
- Use `readonly T[]` (or `ReadonlyArray<T>`) for array parameters that should not be mutated
- Use `as const` for literal objects and arrays that should be fully immutable
- Prefer spreading over mutation: `{ ...obj, key: newValue }` over `obj.key = newValue`

## Type-Only Imports

Use `import type` for imports used only as types:

```typescript
import type { User } from "./models.js";
import { createUser } from "./models.js";
```

This prevents circular dependency issues and ensures types are erased at compile time.

## ESM Import Rule

When using `"type": "module"` in `package.json` with `"module": "Node16"`, all relative imports must include the `.js` extension — even in `.ts` source files:

```typescript
import { helper } from "./utils.js";   // Correct
import { helper } from "./utils";      // Wrong — fails at runtime
```

## Quick Reference: Common Mistakes

| Mistake | Fix |
|---|---|
| Using `any` | Use `unknown` and narrow with type guards |
| Missing return type on exports | Add explicit return type annotation |
| `enum` for string constants | Use `as const` object + derived union type |
| Mutable function parameters | Mark arrays/objects as `readonly` |
| Bare `catch (error)` | Use `catch (error: unknown)` and narrow |
| Missing `.js` in ESM imports | Add `.js` extension to all relative imports |
| `strict: false` in tsconfig | Always use `strict: true` |
| `I` prefix on interfaces | Drop the prefix: `User`, not `IUser` |
| Optional props for distinct states | Use discriminated unions |
| Type assertions (`as T`) | Prefer type guards and narrowing |

## Additional Resources

### Reference Files

Each topic lives in exactly one file — open the one that owns it:

- **`references/type-system.md`** — how to *write* a type: generics, built-in utility types, conditional types, mapped types, template literal types, type guards and assertion predicates, discriminated unions and exhaustive matching, branded types, the `satisfies` operator, const assertions, declaration merging.
- **`references/type-inference.md`** — what TypeScript works out *without* a type: variable, return and generic inference, contextual typing, the `infer` keyword (nested, tuple and template-literal extraction), control-flow narrowing, and when to annotate instead of letting inference work.
- **`references/patterns.md`** — applied patterns: immutability, the error-class hierarchy and `Result` constructors, async (concurrency, async iterators), builder, typed event emitter, overloads, module and barrel patterns, why const objects beat `enum`, assertion functions, and the `in` / truthiness / `Array.isArray` narrowing idioms.
- **`references/project-structure.md`** — everything outside the code: tsconfig (strict and extra safety flags), ESM/CJS module config, directory layout, organizing types, barrel exports, declaration files, import order, path aliases, gitignore.
