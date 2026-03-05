import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { installMcpServers } from "../mcp.js";

// ---------------------------------------------------------------------------
// Mock downloadBundle -- vi.hoisted ensures the variable is available
// inside the hoisted vi.mock factory.
// ---------------------------------------------------------------------------

const { mockDownloadBundle } = vi.hoisted(() => ({
  mockDownloadBundle: vi.fn<(url: string, names: string[]) => Promise<string>>(),
}));

vi.mock("../../lib/download.js", () => ({
  downloadBundle: mockDownloadBundle,
}));

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

/** Temp directories to clean up after each test. */
const tempDirs: string[] = [];

/** Helper: create a fresh temp dir and register it for cleanup. */
function makeTempDir(prefix: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tempDirs.push(dir);
  return dir;
}

/** Valid YAML content for a context7 MCP server definition. */
const context7Yaml = `\
name: "context7"
description: "Context7 MCP server"
config:
  context7:
    type: stdio
    command: npx
    args:
      - -y
      - "@upstash/context7-mcp@latest"
`;

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

describe("installMcpServers", () => {
  beforeEach(() => {
    // Prevent process.exit from actually killing the test runner.
    vi.spyOn(process, "exit").mockImplementation(
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      (_code?: string | number | null) => undefined as never,
    );

    // Silence stdout / stderr output from printResults.
    vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    vi.spyOn(process.stderr, "write").mockImplementation(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    for (const dir of tempDirs) {
      try {
        fs.rmSync(dir, { recursive: true, force: true });
      } catch {
        // best-effort
      }
    }
    tempDirs.length = 0;
  });

  // -----------------------------------------------------------------------
  // 1. Successful install
  // -----------------------------------------------------------------------
  it("creates .mcp.json with the server entry from a YAML bundle", async () => {
    // Prepare a temp dir simulating the extracted bundle.
    const bundleDir = makeTempDir("mcp-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "context7.yaml"),
      context7Yaml,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Prepare a fake cwd.
    const fakeCwd = makeTempDir("mcp-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installMcpServers(["context7"]);

    // .mcp.json should exist with the server entry.
    const mcpJsonPath = path.join(fakeCwd, ".mcp.json");
    expect(fs.existsSync(mcpJsonPath)).toBe(true);

    const written = JSON.parse(fs.readFileSync(mcpJsonPath, "utf-8"));
    expect(written.mcpServers.context7).toEqual({
      type: "stdio",
      command: "npx",
      args: ["-y", "@upstash/context7-mcp@latest"],
    });

    // process.exit should NOT have been called (no failures).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 2. Not-found
  // -----------------------------------------------------------------------
  it("calls process.exit(1) when a requested server is not in the bundle", async () => {
    // Return an empty bundle directory -- the YAML file doesn't exist.
    const bundleDir = makeTempDir("mcp-bundle-");
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("mcp-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installMcpServers(["nonexistent"]);

    expect(process.exit).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // 3. Conflict detection
  // -----------------------------------------------------------------------
  it("calls process.exit(1) when the server key already exists in .mcp.json", async () => {
    // Prepare a bundle with context7.yaml.
    const bundleDir = makeTempDir("mcp-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "context7.yaml"),
      context7Yaml,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Pre-create .mcp.json with a context7 entry to trigger a conflict.
    const fakeCwd = makeTempDir("mcp-cwd-");
    const mcpJsonPath = path.join(fakeCwd, ".mcp.json");
    const existingConfig = {
      mcpServers: {
        context7: { type: "stdio", command: "old-command" },
      },
    };
    fs.writeFileSync(
      mcpJsonPath,
      JSON.stringify(existingConfig, null, 2) + "\n",
      "utf-8",
    );

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installMcpServers(["context7"]);

    // Should exit with failure due to conflict.
    expect(process.exit).toHaveBeenCalledWith(1);

    // Original entry should be untouched.
    const written = JSON.parse(fs.readFileSync(mcpJsonPath, "utf-8"));
    expect(written.mcpServers.context7).toEqual({
      type: "stdio",
      command: "old-command",
    });
  });
});
