# npx Package Patterns

## Argument Parsing with Commander

For CLIs with multiple commands and flags, use `commander`:

```bash
npm install commander
```

```typescript
// src/cli.ts
import { Command } from "commander";

const program = new Command();

program
  .name("my-cli")
  .description("CLI tool for capability discovery")
  .version("1.0.0");

program
  .command("install")
  .description("Install a capability")
  .argument("<name>", "capability name to install")
  .option("-d, --dir <path>", "target directory", ".")
  .option("--dry-run", "preview without installing")
  .action((name: string, opts: { dir: string; dryRun: boolean }) => {
    console.log(`Installing ${name} to ${opts.dir}`);
    if (opts.dryRun) {
      console.log("(dry run — no changes made)");
      return;
    }
    // perform installation...
  });

program
  .command("search")
  .description("Search for capabilities")
  .argument("<query>", "search query")
  .option("-n, --limit <number>", "max results", "10")
  .action((query: string, opts: { limit: string }) => {
    console.log(`Searching for: ${query} (limit: ${opts.limit})`);
  });

export async function run(args: string[]): Promise<void> {
  await program.parseAsync(args, { from: "user" });
}
```

### Commander key patterns

| Pattern | Code |
|---|---|
| Required argument | `.argument("<name>", "description")` |
| Optional argument | `.argument("[name]", "description")` |
| Boolean flag | `.option("--verbose", "enable verbose output")` |
| Flag with value | `.option("-n, --limit <number>", "max results", "10")` |
| Subcommand | `.command("install").action(...)` |
| Global option | `program.option(...)` before subcommands |

## Interactive Prompts

### Built-in readline (zero dependencies)

```typescript
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

async function confirm(message: string): Promise<boolean> {
  const rl = createInterface({ input: stdin, output: stdout });
  const answer = await rl.question(`${message} [y/N] `);
  rl.close();
  return answer.toLowerCase() === "y";
}

// Usage
if (await confirm("Install 3 capabilities?")) {
  performInstall();
}
```

### Selection menu (zero dependencies)

```typescript
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

async function select(message: string, options: string[]): Promise<number> {
  console.log(message);
  options.forEach((opt, i) => console.log(`  ${i + 1}. ${opt}`));

  const rl = createInterface({ input: stdin, output: stdout });
  const answer = await rl.question("Enter number: ");
  rl.close();

  const index = parseInt(answer, 10) - 1;
  if (index >= 0 && index < options.length) {
    return index;
  }
  console.error("Invalid selection");
  process.exit(1);
}
```

## Spinner / Progress Indicator

### Simple spinner (zero dependencies)

```typescript
function createSpinner(message: string) {
  const frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
  let i = 0;

  const interval = setInterval(() => {
    process.stderr.write(`\r${frames[i++ % frames.length]} ${message}`);
  }, 80);

  return {
    stop(finalMessage: string) {
      clearInterval(interval);
      process.stderr.write(`\r✓ ${finalMessage}\n`);
    },
    fail(finalMessage: string) {
      clearInterval(interval);
      process.stderr.write(`\r✗ ${finalMessage}\n`);
    },
  };
}

// Usage
const spinner = createSpinner("Installing...");
await performInstall();
spinner.stop("Installed successfully");
```

## HTTP Requests from CLI

### Using built-in fetch (Node.js 18+)

```typescript
async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

interface SearchResult {
  name: string;
  description: string;
  score: number;
}

const results = await fetchJson<SearchResult[]>(
  `http://server.com/api/search?q=${encodeURIComponent(query)}`
);
```

### With timeout

```typescript
async function fetchWithTimeout<T>(url: string, timeoutMs: number = 10000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}
```

## Error Handling Patterns

### Top-level error boundary

Wrap the entire CLI in a try/catch to ensure clean error output:

```typescript
#!/usr/bin/env node
// src/index.ts
import { run } from "./cli.js";

try {
  await run(process.argv.slice(2));
} catch (error) {
  if (error instanceof Error) {
    console.error(`Error: ${error.message}`);
  } else {
    console.error("An unexpected error occurred");
  }
  process.exit(1);
}
```

### Custom error classes

```typescript
export class CliError extends Error {
  constructor(
    message: string,
    public readonly exitCode: number = 1,
  ) {
    super(message);
    this.name = "CliError";
  }
}

export class NetworkError extends CliError {
  constructor(message: string) {
    super(`Network error: ${message}`, 1);
    this.name = "NetworkError";
  }
}

export class ValidationError extends CliError {
  constructor(message: string) {
    super(message, 2);
    this.name = "ValidationError";
  }
}
```

### Handling in the error boundary

```typescript
try {
  await run(process.argv.slice(2));
} catch (error) {
  if (error instanceof CliError) {
    console.error(red(`✗ ${error.message}`));
    process.exit(error.exitCode);
  }
  console.error(red("✗ An unexpected error occurred"));
  if (process.env.DEBUG) {
    console.error(error);
  }
  process.exit(1);
}
```

## File System Operations

### Read/write JSON config

```typescript
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

async function readJson<T>(path: string): Promise<T> {
  const content = await readFile(path, "utf-8");
  return JSON.parse(content) as T;
}

async function writeJson(path: string, data: unknown): Promise<void> {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, JSON.stringify(data, null, 2) + "\n", "utf-8");
}
```

### Resolve paths relative to cwd

```typescript
import { resolve } from "node:path";

const targetDir = resolve(process.cwd(), opts.dir ?? ".");
```

Always use `resolve()` with `process.cwd()` — never assume the working directory.

## Subprocess Execution

### Run shell commands

```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

async function runCommand(
  command: string,
  args: string[],
): Promise<{ stdout: string; stderr: string }> {
  try {
    return await execFileAsync(command, args, {
      cwd: process.cwd(),
      timeout: 30_000,
    });
  } catch (error) {
    throw new CliError(`Command failed: ${command} ${args.join(" ")}`);
  }
}

// Usage
await runCommand("git", ["clone", repoUrl, targetDir]);
```

Use `execFile` (not `exec`) to avoid shell injection.

## Environment Variables

```typescript
const serverUrl = process.env.AWOS_SERVER_URL ?? "http://localhost:8000";
const debug = process.env.DEBUG === "true";

if (!process.env.REQUIRED_VAR) {
  console.error("Error: REQUIRED_VAR environment variable is not set");
  process.exit(1);
}
```

## Testing CLI Commands

### Integration test with execa

```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const exec = promisify(execFile);

test("install command prints success", async () => {
  const { stdout } = await exec("node", ["./dist/index.js", "install", "test-plugin"]);
  expect(stdout).toContain("Installed successfully");
});

test("unknown command exits with code 1", async () => {
  await expect(
    exec("node", ["./dist/index.js", "unknown"]),
  ).rejects.toMatchObject({ code: 1 });
});
```

### Unit test command handlers

```typescript
// Export handlers separately for unit testing
export function handleInstall(name: string, opts: InstallOptions): Promise<void> {
  // ...
}

// Test
test("handleInstall validates name", async () => {
  await expect(handleInstall("", {})).rejects.toThrow(ValidationError);
});
```
