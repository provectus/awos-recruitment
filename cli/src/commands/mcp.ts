import * as fs from "node:fs";
import * as path from "node:path";

import YAML from "yaml";

import { downloadBundle } from "../lib/download.js";
import { ConflictError } from "../lib/errors.js";
import { mergeIntoMcpJson } from "../lib/json-merge.js";
import { resolveServerUrl } from "../lib/server-url.js";
import type { InstallResult, McpYamlShape } from "../lib/types.js";

/**
 * Installs one or more MCP servers by downloading their YAML definitions
 * from the AWOS server and merging them into `.mcp.json` in the current
 * working directory.
 *
 * Exits with code 1 if any requested server was not found or conflicts.
 */
export async function installMcpServers(names: string[]): Promise<void> {
  const serverUrl = resolveServerUrl();

  const tempDir = await downloadBundle(
    `${serverUrl}/bundle/mcp`,
    names,
  );

  try {
    const results = processMcpServers(tempDir, names);
    printResults(results);

    const hasFailures = results.some(
      (r) => r.status !== "installed",
    );
    if (hasFailures) {
      process.exit(1);
    }
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

/**
 * Compares requested names against what was extracted, parses each YAML
 * file, merges into `.mcp.json`, and returns per-item results.
 */
function processMcpServers(
  tempDir: string,
  requestedNames: string[],
): InstallResult[] {
  const extractedFiles = new Set(
    fs.readdirSync(tempDir).map((f) => f.replace(/\.yaml$/, "")),
  );
  const mcpJsonPath = path.join(process.cwd(), ".mcp.json");
  const results: InstallResult[] = [];

  for (const name of requestedNames) {
    if (!extractedFiles.has(name)) {
      results.push({
        name,
        status: "not-found",
        message: `Error: capability '${name}' not found.`,
      });
      continue;
    }

    const yamlPath = path.join(tempDir, `${name}.yaml`);
    const content = fs.readFileSync(yamlPath, "utf-8");
    const parsed = YAML.parse(content) as McpYamlShape;

    // The config object has exactly one key — the server name.
    const serverKey = Object.keys(parsed.config)[0];
    const serverConfig = parsed.config[serverKey];

    try {
      mergeIntoMcpJson(mcpJsonPath, serverKey, serverConfig);
    } catch (error: unknown) {
      if (error instanceof ConflictError) {
        results.push({
          name,
          status: "conflict",
          message: error.message,
        });
        continue;
      }
      throw error;
    }

    results.push({
      name,
      status: "installed",
      message: `Installed MCP server '${name}' to .mcp.json`,
    });
  }

  return results;
}

/**
 * Prints each install result to stdout (installed) or stderr (errors).
 */
function printResults(results: InstallResult[]): void {
  for (const result of results) {
    if (result.status === "installed") {
      process.stdout.write(result.message + "\n");
    } else {
      process.stderr.write(result.message + "\n");
    }
  }
}
