import * as fs from "node:fs";
import * as path from "node:path";

import { incomingRoot } from "../lib/cache-dir.js";
import { CliError } from "../lib/errors.js";
import { hashDirectory, readOrCreateLock, writeLock, type LockEntry } from "../lib/lock.js";
import { fetchRegistryIndex, type RegistryIndex } from "../lib/registry-index.js";
import { resolveServerUrl } from "../lib/server-url.js";

/**
 * `skill merged <names>`: record that the copy in `.claude/skills/<name>/` now
 * contains the registry version saved by `skill diff --keep` (in the project's
 * cache folder), plus the user's
 * own edits. The lock entry's base becomes that registry version, so `status`,
 * `update`, the hook and the MCP check treat the skill as current with local
 * edits instead of outdated. The saved registry version is then removed.
 */
export async function skillMerged(names: string[]): Promise<void> {
  if (names.length === 0) {
    throw new CliError("Error: no names provided. Usage: awos skill merged <name1> [name2] ...");
  }

  const serverUrl = resolveServerUrl();
  const cwd = process.cwd();

  for (const name of names) {
    if (!fs.existsSync(path.join(incomingRoot(cwd), name))) {
      throw new CliError(
        `Error: no saved registry version for '${name}'. Run 'skill diff --keep ${name}' first.`,
      );
    }
    if (!fs.existsSync(path.join(cwd, ".claude", "skills", name))) {
      throw new CliError(`Error: skill '${name}' is not installed.`);
    }
  }

  let index: RegistryIndex | null = null;
  try {
    index = (await fetchRegistryIndex(serverUrl)) ?? null;
  } catch {
    // The commit is a label only; record the merge without it.
  }

  const lock = readOrCreateLock(cwd);
  const now = new Date().toISOString();

  for (const name of names) {
    const incoming = path.join(incomingRoot(cwd), name);
    const base = hashDirectory(incoming);
    const entry: LockEntry = {
      server: serverUrl,
      installed_at: now,
      hash: base.hash,
      files: base.files,
    };
    const current = index?.skills[name];
    if (current !== undefined && current.hash === base.hash && current.commit) {
      entry.commit = current.commit;
      if (current.released) {
        entry.released = current.released;
      }
    }
    lock.skills[name] = entry;
    fs.rmSync(incoming, { recursive: true, force: true });

    const local = hashDirectory(path.join(cwd, ".claude", "skills", name));
    const kept = local.hash === base.hash ? "no edits of your own" : "your own edits kept";
    process.stdout.write(`Recorded '${name}' as merged with the registry version (${kept}).\n`);
  }

  writeLock(cwd, lock);

  // Leave no empty folders behind.
  for (const dir of [incomingRoot(cwd)]) {
    if (fs.existsSync(dir) && fs.readdirSync(dir).length === 0) {
      fs.rmdirSync(dir);
    }
  }
}
