# TypeScript Project Structure Reference

## tsconfig.json Essentials

### Strict mode (non-negotiable)

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

`strict: true` enables all strict checks at once:

| Flag | What it enforces |
|---|---|
| `strictNullChecks` | `null` and `undefined` are distinct types |
| `noImplicitAny` | Every value must have a known type |
| `strictFunctionTypes` | Contravariant function parameter checks |
| `strictBindCallApply` | Type-safe `bind`, `call`, `apply` |
| `strictPropertyInitialization` | Class properties must be initialized |
| `noImplicitThis` | `this` must have an explicit type |
| `useUnknownInCatchVariables` | Catch clause variables are `unknown` |
| `alwaysStrict` | Emit `"use strict"` in every file |

### Recommended base configuration

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

### Additional safety flags

```json
{
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true
  }
}
```

| Flag | Effect |
|---|---|
| `noUncheckedIndexedAccess` | Array/record indexing returns `T \| undefined` |
| `exactOptionalPropertyTypes` | `undefined` not assignable to optional props unless explicit |
| `noImplicitReturns` | Every code path must return |
| `noFallthroughCasesInSwitch` | Switch cases must break/return |
| `noImplicitOverride` | Require `override` keyword on overridden methods |

## Module Configuration

### ESM setup (type: "module")

In `package.json`:
```json
{
  "type": "module"
}
```

In `tsconfig.json`:
```json
{
  "compilerOptions": {
    "module": "Node16",
    "moduleResolution": "Node16"
  }
}
```

**Critical rule:** All relative imports must include the `.js` extension (even in `.ts` source):

```typescript
// Correct
import { helper } from "./utils.js";

// Wrong — fails at runtime with ESM
import { helper } from "./utils";
```

### CJS setup (legacy)

```json
{
  "compilerOptions": {
    "module": "CommonJS",
    "moduleResolution": "Node10"
  }
}
```

No extension required for relative imports in CJS mode.

## Directory Layout

### Standard project layout

```
project/
├── src/
│   ├── index.ts              # public API / entry point
│   ├── types.ts              # shared type definitions
│   ├── errors.ts             # custom error classes
│   ├── config.ts             # configuration loading
│   ├── domain/               # core business logic
│   │   ├── models.ts
│   │   └── services.ts
│   └── utils/                # pure utility functions
│       ├── strings.ts
│       └── validation.ts
├── dist/                     # compiled output (gitignored)
├── package.json
├── tsconfig.json
└── .gitignore
```

### Organizing types

**Collocated types (preferred):** Define types alongside the code that uses them:

```typescript
// domain/user.ts
export interface User {
  id: string;
  name: string;
  email: string;
}

export function createUser(name: string, email: string): User {
  return { id: generateId(), name, email };
}
```

**Shared types file:** Only extract to a separate `types.ts` when a type is used across multiple modules:

```typescript
// types.ts — only types shared by 3+ modules
export interface Timestamped {
  createdAt: Date;
  updatedAt: Date;
}

export type Id = string;
```

### Barrel exports

Use `index.ts` files to create clean public APIs:

```typescript
// domain/index.ts
export { User, createUser } from "./user.js";
export { Order, createOrder } from "./order.js";
export type { UserFilter } from "./user.js";
```

**Guidelines for barrel exports:**
- Use barrel files at module boundaries (one level deep)
- Avoid deep nesting of barrel files (re-exporting from re-exports)
- Use `export type` for type-only re-exports

## Declaration Files

### When to emit declarations

Set `declaration: true` when the package is consumed by other TypeScript code (libraries, shared packages):

```json
{
  "compilerOptions": {
    "declaration": true,
    "declarationMap": true
  }
}
```

`declarationMap: true` enables "go to source" in editors, pointing to `.ts` instead of `.d.ts`.

### Custom type declarations

For untyped modules or global augmentation:

```typescript
// src/types/global.d.ts
declare module "untyped-module" {
  export function doSomething(input: string): Promise<void>;
}

// Augment global scope
declare global {
  interface Window {
    appConfig: AppConfig;
  }
}
```

Place custom declarations in `src/types/` and ensure the directory is included in `tsconfig.json`'s `include`.

## Import Organization

### Recommended import order

1. Built-in Node.js modules
2. External dependencies (from `node_modules`)
3. Internal absolute imports (aliases)
4. Relative imports

```typescript
// 1. Built-in
import { readFile } from "node:fs/promises";
import { join } from "node:path";

// 2. External (blank line separator)
import { externalHelper } from "external-lib";

// 3. Internal / aliased (blank line separator)
import { db } from "@/database.js";

// 4. Relative (blank line separator)
import { User } from "./models.js";
import { validate } from "./validation.js";
```

### Type-only imports

Use `import type` to ensure types are erased at compile time:

```typescript
import type { User, Order } from "./models.js";
import { createUser } from "./models.js";

// Or inline
import { createUser, type User } from "./models.js";
```

**When to use `import type`:**
- Importing interfaces, type aliases, or enums used only as types
- Prevents circular dependency issues at runtime
- Enforced with `"verbatimModuleSyntax": true` in tsconfig

## Path Aliases

### Setting up aliases

In `tsconfig.json`:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**Note:** Path aliases are a compile-time feature only. The runtime environment (Node.js) does not resolve them. A bundler or path-rewriting tool is required for runtime resolution.

## Gitignore for TypeScript Projects

```gitignore
# Compiled output
dist/

# Dependencies
node_modules/

# TypeScript cache
*.tsbuildinfo

# Environment
.env
.env.local

# OS files
.DS_Store
Thumbs.db
```
