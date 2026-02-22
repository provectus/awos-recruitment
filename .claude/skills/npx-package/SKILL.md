---
name: npx Package Development
description: This skill should be used when the user asks to "create an npx package", "build a CLI tool with TypeScript", "set up a Node.js CLI", "publish an npm package", "configure package.json bin field", "add CLI argument parsing", "create an executable npm package", or when writing TypeScript code for a command-line tool distributed via npx. Covers package structure, TypeScript configuration, argument parsing, build pipeline, and npm publishing.
version: 0.1.0
---

# npx Package Development (TypeScript)

This skill covers building CLI tools in TypeScript that are executable via `npx`. An npx package is a standard npm package with a `bin` entry point — `npx` downloads and runs it without global installation.

## Package Structure

```
my-cli/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts          # entry point (bin target)
│   ├── cli.ts            # argument parsing and command routing
│   └── commands/         # command implementations
│       └── install.ts
├── dist/                 # compiled output (gitignored)
└── README.md
```

## package.json Essentials

```json
{
  "name": "my-cli",
  "version": "1.0.0",
  "description": "CLI tool description",
  "type": "module",
  "bin": {
    "my-cli": "./dist/index.js"
  },
  "files": [
    "dist"
  ],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "prepublishOnly": "npm run build"
  },
  "engines": {
    "node": ">=18"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0"
  }
}
```

Key fields:

| Field | Purpose |
|---|---|
| `name` | Package name on npm. Use `@scope/name` for scoped packages |
| `bin` | Maps command names to compiled JS entry points |
| `files` | Whitelist of files included in the published package |
| `type: "module"` | Enable ESM (import/export syntax) |
| `engines` | Minimum Node.js version requirement |
| `prepublishOnly` | Auto-builds before `npm publish` |

## Entry Point with Shebang

The entry point file must start with a Node.js shebang:

```typescript
#!/usr/bin/env node

// src/index.ts
import { run } from "./cli.js";

run(process.argv.slice(2));
```

The shebang (`#!/usr/bin/env node`) tells the OS to execute the file with Node.js. Without it, `npx` execution fails on Unix systems.

**Important:** The shebang must be the very first line — no blank lines or comments above it.

## TypeScript Configuration

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

Key settings:

- `module: "Node16"` + `moduleResolution: "Node16"` — required for proper ESM support in Node.js.
- `outDir: "./dist"` — compiled JS goes to `dist/`, matching the `bin` path in package.json.
- `declaration: true` — emit `.d.ts` files for consumers who import the package programmatically.

**ESM import rule:** When using `type: "module"`, all relative imports must include the `.js` extension, even in `.ts` source files:

```typescript
// Correct
import { run } from "./cli.js";

// Wrong — will fail at runtime
import { run } from "./cli";
```

## Argument Parsing

### Manual parsing (zero dependencies)

For simple CLIs with 1-3 commands:

```typescript
// src/cli.ts
export function run(args: string[]): void {
  const command = args[0];

  switch (command) {
    case "install":
      handleInstall(args.slice(1));
      break;
    case "search":
      handleSearch(args.slice(1));
      break;
    case "--help":
    case "-h":
      printHelp();
      break;
    case "--version":
    case "-v":
      printVersion();
      break;
    default:
      console.error(`Unknown command: ${command}`);
      printHelp();
      process.exit(1);
  }
}
```

### Flag extraction helper

```typescript
function getFlag(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag);
  if (index === -1 || index + 1 >= args.length) return undefined;
  return args[index + 1];
}

// Usage: npx my-cli install --name my-plugin
const name = getFlag(args, "--name");
```

### With a parsing library (for complex CLIs)

For CLIs with many commands, flags, and subcommands, use a library like `commander` or `yargs`. See `references/patterns.md` for detailed examples.

## Output and Exit Codes

### Colored output (zero dependencies)

Node.js supports ANSI escape codes natively:

```typescript
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const bold = (s: string) => `\x1b[1m${s}\x1b[0m`;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;

console.log(green("✓ Installed successfully"));
console.error(red("✗ Installation failed"));
```

### Exit codes

```typescript
process.exit(0);  // success
process.exit(1);  // general error
process.exit(2);  // misuse (bad arguments)
```

Always call `process.exit()` with an appropriate code on failure. A non-zero exit code signals failure to the calling process.

### Stderr vs stdout

- `console.log()` → stdout — for program output (data, results).
- `console.error()` → stderr — for diagnostics (errors, warnings, progress).

## Build and Test Locally

```bash
# Build
npm run build

# Test locally (symlinks the package globally)
npm link
my-cli --help

# Or test with npx directly
npx . install --name my-plugin

# Unlink when done
npm unlink -g my-cli
```

## Publishing to npm

```bash
# Login (one-time)
npm login

# Publish (runs prepublishOnly → build automatically)
npm publish

# Publish scoped package as public
npm publish --access public
```

After publishing, the package is immediately available via:

```bash
npx my-cli install --name my-plugin
```

### Versioning

```bash
npm version patch   # 1.0.0 → 1.0.1
npm version minor   # 1.0.0 → 1.1.0
npm version major   # 1.0.0 → 2.0.0
```

Run `npm version` before `npm publish` — it updates package.json and creates a git tag.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Missing shebang | Add `#!/usr/bin/env node` as first line of entry point |
| Shebang not on first line | Remove blank lines/comments above `#!/usr/bin/env node` |
| Missing `.js` in ESM imports | Add `.js` extension to all relative imports |
| `bin` points to `.ts` file | Point to compiled `.js` in `dist/` |
| `dist/` not in `files` | Add `"files": ["dist"]` to package.json |
| No `prepublishOnly` script | Add `"prepublishOnly": "npm run build"` |
| File not executable on Unix | Run `chmod +x dist/index.js` (usually handled by npm) |

## Additional Resources

### Reference Files

For detailed patterns and advanced configuration, consult:
- **`references/patterns.md`** — Commander/yargs argument parsing, interactive prompts, spinner/progress bars, HTTP requests from CLI, error handling patterns, monorepo setup
- **`references/package-setup.md`** — Advanced package.json fields, scoped packages, bundling with esbuild/tsup, dual CJS/ESM support, CI/CD publishing, npm provenance
