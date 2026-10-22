import * as fs from "node:fs";
import * as path from "node:path";

import { CliError } from "../lib/errors.js";
import { hashDirectory, readOrCreateLock, writeLock } from "../lib/lock.js";
import { fetchRegistryIndex } from "../lib/registry-index.js";
import { resolveServerUrl } from "../lib/server-url.js";

/**
 * `skill skip <names>`: remember that the user does not want the registry's
 * current version of these skills. `status`, `update`, the session-start hook
 * and the MCP check stay quiet about them until the registry publishes a
 * newer version. `skill update <name>` still updates a skipped skill.
 */
export async function skipSkills(names: string[]): Promise<void> {
  if (names.length === 0) {
    throw new CliError("Error: no names provided. Usage: awos skill skip <name1> [name2] ...");
  }

  const serverUrl = resolveServerUrl();
  const cwd = process.cwd();
  const index = await fetchRegistryIndex(serverUrl);
  const lock = readOrCreateLock(cwd);
  const now = new Date().toISOString();
  let changed = false;

  for (const name of names) {
    const skillDir = path.join(cwd, ".claude", "skills", name);
    if (!fs.existsSync(skillDir)) {
      throw new CliError(`Error: skill '${name}' is not installed.`);
    }
    const current = index.skills[name];
    if (current === undefined) {
      throw new CliError(`Error: skill '${name}' is not in the registry; there is nothing to skip.`);
    }

    const local = hashDirectory(skillDir);
    if (local.hash === current.hash) {
      process.stdout.write(`'${name}' is already up to date; nothing to skip.\n`);
      continue;
    }

    // A copy installed before the lock file gets an entry for what is on disk.
    const entry = lock.skills[name] ?? {
      server: serverUrl,
      installed_at: now,
      hash: local.hash,
      files: local.files,
    };
    entry.skip = { hash: current.hash, at: now };
    lock.skills[name] = entry;
    changed = true;
    process.stdout.write(`Skipping '${name}' until the registry publishes a newer version.\n`);
  }

  if (changed) {
    writeLock(cwd, lock);
  }
}
