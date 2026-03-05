import * as fs from "node:fs";
import * as path from "node:path";

import { downloadBundle } from "../lib/download.js";
import { resolveServerUrl } from "../lib/server-url.js";
import type { InstallResult } from "../lib/types.js";

/**
 * Installs one or more skills by downloading them from the AWOS server
 * and copying them into `.claude/skills/<name>/` in the current working directory.
 *
 * Exits with code 1 if any requested skill was not found or already exists.
 */
export async function installSkills(names: string[]): Promise<void> {
  const serverUrl = resolveServerUrl();

  const tempDir = await downloadBundle(
    `${serverUrl}/bundle/skills`,
    names,
  );

  try {
    const results = processSkills(tempDir, names);
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
 * Compares requested names against what was extracted, copies found
 * skills into the target directory, and returns per-item results.
 *
 * This is a pure function with no side effects — it does not write to
 * stdout/stderr and does not call `process.exit`. Callers are responsible
 * for interpreting the results and performing I/O.
 */
export function processSkills(
  tempDir: string,
  requestedNames: string[],
): InstallResult[] {
  const extractedDirs = new Set(fs.readdirSync(tempDir));
  const results: InstallResult[] = [];

  for (const name of requestedNames) {
    if (!extractedDirs.has(name)) {
      results.push({
        name,
        status: "not-found",
        message: `Error: capability '${name}' not found.`,
      });
      continue;
    }

    const targetDir = path.join(
      process.cwd(),
      ".claude",
      "skills",
      name,
    );

    if (fs.existsSync(targetDir)) {
      results.push({
        name,
        status: "conflict",
        message: `Error: skill '${name}' already exists. Remove it first to reinstall.`,
      });
      continue;
    }

    const sourceDir = path.join(tempDir, name);
    fs.cpSync(sourceDir, targetDir, { recursive: true });

    results.push({
      name,
      status: "installed",
      message: `Installed skill '${name}' to .claude/skills/${name}/SKILL.md`,
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
