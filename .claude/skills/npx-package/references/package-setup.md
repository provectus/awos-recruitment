# npx Package Setup Reference

## Contents

- [Complete package.json](#complete-packagejson) — full manifest for a CLI that also exports a library
- [Key Fields Explained](#key-fields-explained) — `bin`, `files`, `exports`, `engines`
- [Scoped Packages](#scoped-packages) — `@scope/name` and `--access public`
- [Bundling with tsup](#bundling-with-tsup) — single-file builds, shebang via `banner`
- [Dual CJS/ESM Support](#dual-cjsesm-support) — conditional `exports` for `require` and `import`
- [CI/CD Publishing](#cicd-publishing) — GitHub Actions workflow, npm provenance
- [Version Management](#version-management) — `npm version`, pre-release tags
- [.npmignore vs files](#npmignore-vs-files) — why the whitelist wins
- [Verifying the Package](#verifying-the-package) — `npm pack --dry-run`
- [Post-Publish Testing](#post-publish-testing) — smoke-testing the published package with npx

## Complete package.json

```json
{
  "name": "@scope/my-cli",
  "version": "1.0.0",
  "description": "CLI tool for plugin discovery and installation",
  "type": "module",
  "bin": {
    "my-cli": "./dist/index.js"
  },
  "main": "./dist/lib.js",
  "types": "./dist/lib.d.ts",
  "exports": {
    ".": {
      "types": "./dist/lib.d.ts",
      "import": "./dist/lib.js"
    }
  },
  "files": [
    "dist"
  ],
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "test": "vitest",
    "lint": "tsc --noEmit",
    "prepublishOnly": "npm run build"
  },
  "engines": {
    "node": ">=24"
  },
  "keywords": ["cli", "plugins"],
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/org/my-cli"
  },
  "devDependencies": {
    "typescript": "^7",
    "@types/node": "^24",
    "vitest": "^5"
  }
}
```

The devDependency ranges are examples — install with `npm install -D typescript @types/node vitest` to get the latest majors rather than copying these pins. Keep the `@types/node` major equal to the `engines.node` floor.

## Key Fields Explained

### `bin`

Maps CLI command names to entry point files. Supports multiple commands:

```json
{
  "bin": {
    "my-cli": "./dist/index.js",
    "mc": "./dist/index.js"
  }
}
```

Both `npx my-cli` and `npx mc` will work after publishing.

For a single command matching the package name, use the shorthand:

```json
{
  "bin": "./dist/index.js"
}
```

### `files`

Whitelist of files and directories included in the published package. Everything else is excluded. Always include only the compiled output:

```json
{
  "files": ["dist"]
}
```

Verify with `npm pack --dry-run` — inspect the file list before publishing.

### `exports`

Defines the public API for consumers who `import` the package programmatically (not via CLI). Conditions are matched in order, so `types` must come first or TypeScript may never reach it:

```json
{
  "exports": {
    ".": {
      "types": "./dist/lib.d.ts",
      "import": "./dist/lib.js"
    },
    "./utils": {
      "types": "./dist/utils.d.ts",
      "import": "./dist/utils.js"
    }
  }
}
```

### `engines`

Specifies the minimum Node.js version. npm will warn (and `--engine-strict` will block) installations on incompatible versions:

```json
{
  "engines": {
    "node": ">=24"
  }
}
```

Set the floor to the current Node LTS major (check the Node.js release schedule); every supported LTS line ships `fetch`, ESM, and `node:test`. Lower it only if you must support users on an older maintenance LTS line, and match `@types/node` and the tsup `target` to whatever floor you choose.

## Scoped Packages

Scoped packages use the `@scope/name` format:

```json
{
  "name": "@scope/my-cli"
}
```

Publishing scoped packages requires `--access public` (unless a paid org):

```bash
npm publish --access public
```

Users run it with:

```bash
npx @scope/my-cli search "http client"
```

## Bundling with tsup

For packages with dependencies that should be bundled into a single file (faster startup, no `node_modules` needed at runtime):

```bash
npm install -D tsup
```

```json
{
  "scripts": {
    "build": "tsup src/index.ts --format esm --dts"
  }
}
```

```typescript
// tsup.config.ts
import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  dts: true,
  clean: true,
  target: "node24", // match engines.node
  banner: {
    js: "#!/usr/bin/env node",
  },
});
```

**Key benefit:** The `banner` option automatically adds the shebang to the bundled output.

### When to bundle

- Package has runtime dependencies → bundle for faster `npx` cold start.
- Package is a pure CLI with no library exports → bundle for simpler distribution.
- Package is also used as a library → keep unbundled, let consumers tree-shake.

## Dual CJS/ESM Support

If the package must support both `require()` and `import`:

```json
{
  "type": "module",
  "exports": {
    ".": {
      "types": "./dist/lib.d.ts",
      "import": "./dist/lib.js",
      "require": "./dist/lib.cjs"
    }
  }
}
```

With tsup:

```typescript
export default defineConfig({
  entry: ["src/lib.ts"],
  format: ["esm", "cjs"],
  dts: true,
});
```

For CLI-only packages, skip CJS — `type: "module"` with ESM only is simpler and sufficient.

## CI/CD Publishing

### GitHub Actions

```yaml
# .github/workflows/publish.yml
name: Publish
on:
  push:
    tags:
      - "v*"
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      # Pin each action to its latest major
      - uses: actions/checkout@v7
      - uses: actions/setup-node@v7
        with:
          node-version: "lts/*" # current Node LTS; or pin to the engines.node major
          registry-url: "https://registry.npmjs.org"
      - run: npm ci
      - run: npm run build
      - run: npm test
      - run: npm publish --provenance --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### npm Provenance

The `--provenance` flag links the published package to its source commit:

```bash
npm publish --provenance --access public
```

Requires GitHub Actions with `id-token: write` permission. Shows a "Published via GitHub Actions" badge on npmjs.com.

## Version Management

### Manual versioning

```bash
npm version patch -m "Release %s"   # 1.0.0 → 1.0.1
npm version minor -m "Release %s"   # 1.0.0 → 1.1.0
npm version major -m "Release %s"   # 1.0.0 → 2.0.0
git push --follow-tags
```

`npm version` updates package.json, creates a git commit, and tags it.

### Pre-release versions

```bash
npm version prerelease --preid=beta   # 1.0.0 → 1.0.1-beta.0
npm publish --tag beta                 # installs with npx my-cli@beta
```

Use `--tag` to avoid setting the pre-release as the `latest` tag.

## .npmignore vs files

Prefer `files` (whitelist) over `.npmignore` (blacklist):

```json
{
  "files": ["dist"]
}
```

This ensures only compiled output is published. No risk of accidentally including `src/`, `.env`, or test files.

## Verifying the Package

Before publishing, inspect what will be included:

```bash
# List files that would be published
npm pack --dry-run

# Create a tarball locally for inspection
npm pack
tar -tf my-cli-1.0.0.tgz
```

## Post-Publish Testing

After publishing, verify the package works via npx:

```bash
npx --yes my-cli@latest --version
npx --yes my-cli@latest search "test query"
```

The `--yes` flag skips the confirmation prompt for first-time execution.
