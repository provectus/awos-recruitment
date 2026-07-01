# Anti-Patterns in Event-Driven Lambda Architectures

These anti-patterns describe situations where Lambda **feels like the right choice** but leads to suboptimal, costly, or fragile architectures. Recognizing them early avoids expensive rework.

## The Lambda Monolith

### The pattern

A single Lambda function contains all application logic and handles all routes or event types. Common when "lift and shift" migrating from EC2, Elastic Beanstalk, or traditional servers.

```
API Gateway (all routes) --> Single Lambda function --> All downstream resources
```

### Why it feels right

- Familiar -- mirrors the single-server model developers already know
- Simple deployment -- one function, one artifact, one pipeline
- Fewer moving parts initially

### Why it's an anti-pattern

| Problem | Impact |
|---|---|
| **Bloated package size** | Contains all code for all paths; slower cold starts |
| **Overly broad IAM permissions** | Execution role must grant access to every resource for every path; violates least privilege |
| **Risky upgrades** | Any change to one path risks breaking all paths; entire application deploys as one unit |
| **Hard to maintain** | Monolithic code repository increases cognitive burden; multiple developers stepping on each other |
| **Hard to reuse** | Extracting libraries from monoliths is difficult; slows future projects |
| **Hard to test** | Lines of code grow, combinatorial test complexity grows faster |

### What to do instead

Decompose into individual microservices: **one Lambda function per well-defined task**.

```
API Gateway /orders   --> createOrder function   --> Orders table
API Gateway /payments --> processPayment function --> Payments table
API Gateway /users    --> getUser function        --> Users table
```

Each function has:
- Its own minimal deployment package
- Its own narrowly scoped IAM role
- Independent deployment and rollback (canary releases)
- Focused unit tests with smaller input surface

**Migration strategy:** Use the strangler pattern -- extract one route/handler at a time from the monolith into its own function, routing traffic incrementally.

## Lambda as Orchestrator

### The pattern

A Lambda function contains complex branching workflow logic -- conditionals, error handling, retries, wait states, and compensation logic for multi-step business processes.

### Example: payment processing

A payment function must handle:
- Multiple payment types (cash, check, credit card) with different processing flows
- Credit card states (approved, declined, pending, fraud review)
- Partial and full refunds
- Third-party payment processor outages
- Multi-day processing windows

### Why it feels right

- Developers are comfortable writing procedural workflow code
- A single function keeps the "workflow" in one place
- No additional services to learn

### Why it's an anti-pattern

| Problem | Impact |
|---|---|
| **Spaghetti code** | Complex branching, nested error handling, state tracking become unreadable |
| **Fragile in production** | One edge case in workflow logic can break the entire process |
| **15-minute timeout** | Long-running workflows hit Lambda's execution limit |
| **Custom retry logic** | Re-inventing retry, backoff, and compensation patterns that already exist in managed services |
| **Harder to version** | Changing workflow logic requires changing and redeploying code |
| **Harder to visualize** | No built-in way to see workflow state or execution history |

### What to do instead

| Need | Use |
|---|---|
| Multi-step workflows within a bounded context | **AWS Step Functions** -- state machines with built-in error handling, retries, wait states, parallel execution, and visual monitoring. Workflows can run up to 1 year. |
| Coordination across multiple microservices | **Amazon EventBridge** -- serverless event bus that routes events based on rules, decoupling producers from consumers |
| Simple async handoff between two steps | **SQS queue** between Lambda functions |

**Key insight:** If your Lambda function has more orchestration logic (if/else, try/catch, retry loops, state tracking) than business logic, it belongs in Step Functions.

## Lambda Calling Lambda (Synchronous Chains)

### The pattern

Lambda functions invoke other Lambda functions synchronously, forming a chain where each caller waits for the downstream function to return.

```
Create Order --> (waits 2s) --> Process Payment --> (waits 3s) --> Create Invoice
Result: 5s billed x 3 functions = 15s of compute for 5s of work
```

### Why it feels right

- Mirrors synchronous function calls in application code
- Straightforward request/response model
- Each function is small and focused (appears to follow the microservice principle)

### Why it's an anti-pattern

| Problem | Impact |
|---|---|
| **Compounded cost** | All upstream functions run (and bill) while waiting for downstream to complete. 3 chained functions = 3x the duration cost of the slowest |
| **Complex error handling** | Errors in downstream functions must bubble up through every layer. Should a payment error trigger an order rollback? Each function needs custom compensation logic |
| **Tight coupling** | The entire chain is only as available as the slowest, least reliable function. One slow function blocks the entire flow |
| **Wasted concurrency** | Waiting functions consume concurrency slots doing nothing. 3 chained functions = 3x the concurrency consumption |
| **Cascading timeouts** | Parent function timeout must exceed the sum of all downstream timeouts |

### What to do instead

**Option 1: SQS between functions** (when downstream is slower or independent)

```
Create Order --> SQS --> Process Payment --> SQS --> Create Invoice
```

- Each function runs independently, bills only for its own work
- SQS durably persists messages if downstream is slow or fails
- Functions scale independently

**Option 2: Step Functions** (when you need orchestration, error handling, retries)

```
Step Functions state machine:
  1. Create Order
  2. Process Payment (with retry on failure)
  3. Create Invoice (parallel with Send Confirmation)
```

- Built-in error handling and retry per step
- Visual execution history for debugging
- Each Lambda bills only for its own execution time

## Recursive Patterns That Cause Invocation Loops

### The pattern

A Lambda function writes to the same resource that triggered it, creating an infinite invocation loop.

```
S3 put event --> Lambda function --> writes to SAME S3 bucket --> S3 put event --> Lambda ...
```

### Why it feels right

- The function's job is to transform/process data in a bucket or table
- Writing results back to the source is the simplest implementation
- "I'll just filter the trigger to avoid the loop" -- but the filter is wrong or incomplete

### Why it's an anti-pattern

| Problem | Impact |
|---|---|
| **Infinite scaling** | Both Lambda and S3/SQS/SNS auto-scale, so the loop grows exponentially |
| **Runaway cost** | Unbounded invocations accumulate charges until the loop is detected and stopped |
| **Consumes all concurrency** | Loop can consume the entire account's concurrency pool, throttling all other functions |
| **Hard to detect** | May not be obvious until CloudWatch alarms fire or the bill arrives |

### Services at risk

This is not limited to S3. Recursive loops can occur with:
- Amazon S3 (put/delete events)
- Amazon SQS (function sends message back to its source queue)
- Amazon SNS (function publishes to its source topic)
- Amazon DynamoDB (function writes to its source table via DynamoDB Streams)

### What to do instead

**Primary rule:** The resource that triggers a function should be different from the resource the function writes to.

```
Source S3 bucket --> Lambda --> Destination S3 bucket (different bucket)
Source DynamoDB table --> Lambda --> Destination table or S3
```

If you must write back to the same resource:

| Safeguard | How |
|---|---|
| **Positive trigger filter** | Trigger only on a specific prefix/tag/naming convention that the function's output does NOT match |
| **Reserved concurrency** | Set a low cap to limit blast radius during development/testing |
| **CloudWatch alarm** | Alarm on ConcurrentExecutions spike to detect loops early |
| **Lambda recursive loop detection** | Lambda automatically detects and stops some loops between Lambda, SQS, and SNS (limited scope -- do not rely on this as sole protection) |

### Emergency response

If a recursive loop is running:
1. Set the function's reserved concurrency to **0** immediately (Lambda console "Throttle" button)
2. This stops all invocations while you fix the code
3. Fix the trigger/output separation, then restore concurrency

## Synchronous Waiting Within a Single Function

### The pattern

A Lambda function performs multiple independent operations sequentially, waiting for each to complete before starting the next.

```
Sequential: S3 (200ms) + DynamoDB (100ms) + external API (500ms) = 800ms billed
Concurrent: max(200ms, 100ms, 500ms) = 500ms billed
```

### Why it feels right

- Sequential code is easy to write and reason about
- The operations are logically related ("process this order")
- "It's just three API calls, how bad can it be?"

### Why it's an anti-pattern

| Problem | Impact |
|---|---|
| **Compounded latency** | Total duration = sum of all wait times, not the longest |
| **Higher cost** | Billed for the entire duration, including all wait times |
| **Unnecessary coupling** | If operations are independent, sequencing them adds no value |

### What to do instead

**If operations are independent:** run them concurrently within the same function using your language's concurrency primitives.

**If operations are dependent** (B needs A's result): split into separate functions connected by events.

```
Lambda A: Write to S3 --> S3 event triggers --> Lambda B: Write to DynamoDB
```

- Lambda A completes and bills only for its work
- Lambda B runs independently when triggered by the S3 event
- Total cost is often lower, and each function is simpler

## Anti-Pattern Decision Matrix

Use this to quickly identify which anti-pattern you might be falling into:

| Signal | Likely anti-pattern | Alternative |
|---|---|---|
| Single function handles all API routes | Lambda monolith | Decompose to one function per route |
| Function has more if/else/retry than business logic | Lambda as orchestrator | Step Functions |
| Function invokes another function with `invoke()` and waits | Lambda calling Lambda | SQS or Step Functions |
| Function writes to the same resource that triggered it | Recursive loop | Separate source and destination resources |
| Function does 3+ independent API calls sequentially | Synchronous waiting | Concurrent execution or event-driven split |
| Function timeout is set to 15 min "just in case" | Multiple anti-patterns | Measure actual duration; consider decomposition |
| Function's IAM role has broad wildcards | Lambda monolith symptom | Decompose and scope roles per function |
