# TypeScript Type Inference Reference

Patterns for leveraging TypeScript's type inference capabilities.

## Basic Inference

### Variable Inference

```typescript
// TypeScript infers types from initialization
const name = 'John'          // type: string
const age = 30               // type: number
const isActive = true        // type: boolean
const items = [1, 2, 3]      // type: number[]

// Literal types with const
let status = 'active'        // type: string
const mode = 'dark' as const // type: 'dark'

// Object inference
const user = {
  name: 'John',
  age: 30,
}  // type: { name: string; age: number }

// const assertion for readonly literal object
const config = {
  api: '/api/v1',
  timeout: 5000,
} as const
// type: { readonly api: "/api/v1"; readonly timeout: 5000 }
```

### Function Return Inference

```typescript
// Return type inferred from return statements
function add(a: number, b: number) {
  return a + b  // return type: number
}

function getUser(id: string) {
  return { id, name: 'John', active: true }
}  // return type: { id: string; name: string; active: boolean }

// Async function inference
async function fetchData() {
  const response = await fetch('/api/data')
  return response.json() as Promise<Data>
}  // return type: Promise<Data>
```

### Generic Inference

```typescript
// Type parameter inferred from argument
function identity<T>(value: T): T {
  return value
}

const str = identity('hello')  // T inferred as string
const num = identity(42)       // T inferred as number

// Multiple type parameters
function pair<T, U>(first: T, second: U) {
  return [first, second] as const
}

const result = pair('name', 42)  // [T, U] inferred as [string, number]
```

## Contextual Typing

### Callback Parameters

```typescript
// Parameter types inferred from context
const numbers = [1, 2, 3, 4, 5]

// 'num' inferred as number from array type
const doubled = numbers.map(num => num * 2)

// Event handler inference
document.addEventListener('click', event => {
  // 'event' inferred as MouseEvent
  console.log(event.clientX, event.clientY)
})

// Object method inference
const handlers = {
  onClick: (event) => {
    // Without annotation, event is 'any' - context not available
  },
}

// With explicit interface
interface Handlers {
  onClick: (event: MouseEvent) => void
}

const typedHandlers: Handlers = {
  onClick: (event) => {
    // 'event' now inferred as MouseEvent
    console.log(event.button)
  },
}
```

### Satisfies Operator

```typescript
// 'satisfies' checks type while preserving inferred literal types
const palette = {
  red: [255, 0, 0],
  green: '#00ff00',
  blue: [0, 0, 255],
} satisfies Record<string, string | [number, number, number]>

// Type is preserved as literal
palette.red   // [number, number, number], not string | [number, number, number]
palette.green // string

// vs type annotation which would widen
const palette2: Record<string, string | [number, number, number]> = {
  red: [255, 0, 0],
  green: '#00ff00',
  blue: [0, 0, 255],
}
palette2.red  // string | [number, number, number] - lost specificity
```

## Infer Keyword

### Extract Nested Types

```typescript
// Extract element type from array
type ElementType<T> = T extends (infer E)[] ? E : never

type StringElement = ElementType<string[]>  // string
type NumberElement = ElementType<number[]>  // number

// Extract return type
type ReturnOf<T> = T extends (...args: any[]) => infer R ? R : never

type FnReturn = ReturnOf<() => string>  // string

// Extract Promise value
type UnwrapPromise<T> = T extends Promise<infer U> ? U : T

type PromiseValue = UnwrapPromise<Promise<string>>  // string
```

### Complex Infer Patterns

```typescript
// Extract first element of tuple
type First<T> = T extends [infer F, ...any[]] ? F : never

type FirstElement = First<[string, number, boolean]>  // string

// Extract last element
type Last<T> = T extends [...any[], infer L] ? L : never

type LastElement = Last<[string, number, boolean]>  // boolean

// Extract function parameter at specific index
type ParamAt<T, N extends number> = T extends (...args: infer P) => any
  ? P[N]
  : never

type SecondParam = ParamAt<(a: string, b: number) => void, 1>  // number
```

### Infer in Template Literals

```typescript
// Extract parts from string literal
type ExtractRoute<T> = T extends `/${infer Resource}/${infer Id}`
  ? { resource: Resource; id: Id }
  : never

type Route = ExtractRoute<'/users/123'>
// { resource: 'users'; id: '123' }

// Parse event names
type ParseEvent<T> = T extends `on${infer Event}`
  ? Uncapitalize<Event>
  : never

type EventName = ParseEvent<'onClick'>  // 'click'
```

## Control Flow Analysis

### Narrowing

```typescript
function process(value: string | number) {
  if (typeof value === 'string') {
    // TypeScript knows value is string here
    return value.toUpperCase()
  }
  // TypeScript knows value is number here
  return value.toFixed(2)
}

// Truthiness narrowing
function log(value: string | null | undefined) {
  if (value) {
    // value is string (truthy check eliminates null/undefined)
    console.log(value.length)
  }
}

// Equality narrowing
function compare(a: string | number, b: string | boolean) {
  if (a === b) {
    // Both a and b are string (only common type)
    return a.toUpperCase()
  }
}
```

### Type Guards

```typescript
interface Dog {
  bark(): void
}

interface Cat {
  meow(): void
}

// Type predicate
function isDog(animal: Dog | Cat): animal is Dog {
  return 'bark' in animal
}

function makeSound(animal: Dog | Cat) {
  if (isDog(animal)) {
    animal.bark()  // TypeScript knows it's Dog
  } else {
    animal.meow()  // TypeScript knows it's Cat
  }
}

// Assertion function
function assertString(value: unknown): asserts value is string {
  if (typeof value !== 'string') {
    throw new Error('Not a string')
  }
}

function process(value: unknown) {
  assertString(value)
  // TypeScript knows value is string after assertion
  console.log(value.toUpperCase())
}
```

### Discriminated Unions

```typescript
type Result<T> =
  | { success: true; data: T }
  | { success: false; error: Error }

function handle<T>(result: Result<T>) {
  if (result.success) {
    // TypeScript knows result has 'data' property
    console.log(result.data)
  } else {
    // TypeScript knows result has 'error' property
    console.log(result.error.message)
  }
}
```

## Best Practices

### Let Inference Work

```typescript
// Bad: Redundant type annotation
const name: string = 'John'
const numbers: number[] = [1, 2, 3]

// Good: Let inference do its job
const name = 'John'
const numbers = [1, 2, 3]
```

### Annotate When Needed

```typescript
// Good: Annotate function parameters
function greet(name: string): void {
  console.log(`Hello, ${name}`)
}

// Good: Annotate when inference would be too wide
const status: 'active' | 'inactive' = 'active'

// Good: Annotate complex returns
interface User {
  id: string
  name: string
}

function parseUser(json: string): User {
  return JSON.parse(json)
}
```

### Use typeof for Runtime Values

```typescript
const config = {
  api: '/api',
  timeout: 5000,
}

// Derive type from runtime value
type Config = typeof config

function updateConfig(updates: Partial<Config>): void {
  Object.assign(config, updates)
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
  }
}

// Derive User type from function
type User = ReturnType<typeof createUser>

function displayUser(user: User): void {
  console.log(`${user.name} (${user.email})`)
}
```
