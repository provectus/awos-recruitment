import * as fs from "node:fs";
import * as path from "node:path";

import { downloadBundle } from "../lib/download.js";
import { readLock, recordSkillInstalls } from "../lib/lock.js";
import { resolveServerUrl } from "../lib/server-url.js";
import type { InstallResult } from "../lib/types.js";

export interface SkillInstallOptions {
  /** Replace a skill that is already installed instead of failing. */
  force?: boolean;
}

/**
 * Installs one or more skills by downloading them from the AWOS server
 * and copying them into `.claude/skills/<name>/` in the current working
 * directory. Every installed skill is recorded in
 * `.claude/awos-recruitment.lock.json` with the hash of its files.
 *
 * Exits with code 1 if any requested skill was not found or already exists
 * (unless `force` is set, which replaces the existing copy).
 */
export async function installSkills(
  names: string[],
  options: SkillInstallOptions = {},
): Promise<void> {
  const serverUrl = resolveServerUrl();

  const tempDir = await downloadBundle(
    `${serverUrl}/bundle/skills`,
    names,
  );

  try {
    const firstInstall = readLock(process.cwd()) === null;
    const results = processSkills(tempDir, names, options);
    recordSkillInstalls(process.cwd(), installedNames(results), serverUrl);
    printResults(results);
    if (firstInstall && installedNames(results).length > 0) {
      printUpdateCheckTip(process.cwd());
    }

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

/** Names of the results that ended up installed (for the lock file). */
export function installedNames(results: InstallResult[]): string[] {
  return results.filter((r) => r.status === "installed").map((r) => r.name);
}

/**
 * Compares requested names against what was extracted, copies found
 * skills into the target directory, and returns per-item results.
 *
 * This function only touches `.claude/skills/` — it does not write to
 * stdout/stderr, does not call `process.exit` and does not update the
 * lock file. Callers are responsible for interpreting the results and
 * performing I/O.
 */
export function processSkills(
  tempDir: string,
  requestedNames: string[],
  options: SkillInstallOptions = {},
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

    const existed = fs.existsSync(targetDir);
    if (existed && !options.force) {
      results.push({
        name,
        status: "conflict",
        message: `Error: skill '${name}' already exists. Use --force to replace it.`,
      });
      continue;
    }

    if (existed) {
      fs.rmSync(targetDir, { recursive: true, force: true });
    }

    const sourceDir = path.join(tempDir, name);
    fs.cpSync(sourceDir, targetDir, { recursive: true });

    results.push({
      name,
      status: "installed",
      message: existed
        ? `Replaced skill '${name}' in .claude/skills/${name}/`
        : `Installed skill '${name}' to .claude/skills/${name}/SKILL.md`,
    });
  }

  return results;
}

/**
 * After the first install in a project, points at the hook that reports
 * outdated skills at session start — unless it is already installed.
 */
function printUpdateCheckTip(cwd: string): void {
  const hookDir = path.join(cwd, ".claude", "hooks", "skill-update-check");
  if (fs.existsSync(hookDir)) {
    return;
  }
  process.stdout.write(
    "\nTip: `npx @provectusinc/awos-recruitment hook skill-update-check` tells you at session start when installed skills are outdated.\n",
  );
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
