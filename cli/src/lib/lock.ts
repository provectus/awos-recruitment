import { createHash, randomUUID } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

import { CliError } from "./errors.js";
import type { RegistryIndex } from "./registry-index.js";

/**
 * Lock file written next to installed capabilities. It records what the CLI
 * installed and the content hash of every file, so a later `status` or
 * `update` can tell a current copy from an outdated or locally edited one.
 *
 * The hashing scheme is shared with the server (`registry_index.py`) and
 * must stay in lockstep:
 * - each file: hex sha256 of its bytes;
 * - a capability: hex sha256 over `"<relative path>\0<file sha256>\n"` for
 *   every file, sorted by relative path (POSIX separators).
 */
export const LOCK_FILE_RELATIVE = path.join(
  ".claude",
  "awos-recruitment.lock.json",
);

export const LOCK_VERSION = 1;

export interface LockEntry {
  /** Server the capability was downloaded from. */
  server: string;
  /** ISO-8601 UTC timestamp of the install. */
  installed_at: string;
  /** Combined hash of all files (see module docs). */
  hash: string;
  /** Relative path (POSIX) -> hex sha256 of the file. */
  files: Record<string, string>;
  /** Registry commit of the installed version, when the server knew it. */
  commit?: string;
  /** Date that version appeared in the registry (YYYY-MM-DD). */
  released?: string;
  /** Registry version the user chose not to take (`skill skip`). */
  skip?: { hash: string; at: string };
}

export interface LockFile {
  version: typeof LOCK_VERSION;
  /** Random id for this project; used for telemetry instead of a repo name. */
  project_id: string;
  skills: Record<string, LockEntry>;
}

export interface DirectoryHash {
  hash: string;
  files: Record<string, string>;
}

/** Returns the hex sha256 of a file's bytes. */
export function hashFile(filePath: string): string {
  return createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

/** Folds per-file hashes into one capability hash. */
export function combinedHash(files: Record<string, string>): string {
  const digest = createHash("sha256");
  for (const relPath of Object.keys(files).sort()) {
    digest.update(`${relPath}\0${files[relPath]}\n`);
  }
  return digest.digest("hex");
}

/**
 * Hashes every regular file under `dir` (recursively). Relative paths use
 * `/` separators regardless of platform so hashes match the server's.
 */
export function hashDirectory(dir: string): DirectoryHash {
  const files: Record<string, string> = {};

  const walk = (current: string, relPrefix: string): void => {
    // Code-point order (not locale order) so the written map matches the
    // server's sorted() output and the folded hash.
    const entries = fs
      .readdirSync(current, { withFileTypes: true })
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    for (const entry of entries) {
      const abs = path.join(current, entry.name);
      const rel = relPrefix === "" ? entry.name : `${relPrefix}/${entry.name}`;
      if (entry.isDirectory()) {
        walk(abs, rel);
      } else if (entry.isFile()) {
        files[rel] = hashFile(abs);
      }
    }
  };

  walk(dir, "");
  return { hash: combinedHash(files), files };
}

/** The lock file of `cwd`, or a fresh one with a new project id. */
export function readOrCreateLock(cwd: string): LockFile {
  return readLock(cwd) ?? emptyLock();
}

function emptyLock(): LockFile {
  return { version: LOCK_VERSION, project_id: randomUUID(), skills: {} };
}

/**
 * Reads the lock file from `cwd`. Returns `null` when there is none.
 *
 * @throws CliError when the file exists but is not valid JSON or has an
 *   unexpected shape — a corrupt lock must not be silently overwritten.
 */
export function readLock(cwd: string): LockFile | null {
  const lockPath = path.join(cwd, LOCK_FILE_RELATIVE);
  if (!fs.existsSync(lockPath)) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(fs.readFileSync(lockPath, "utf-8"));
  } catch {
    throw new CliError(
      `Error: ${LOCK_FILE_RELATIVE} is not valid JSON. Fix or remove it and retry.`,
    );
  }

  if (
    typeof parsed !== "object" ||
    parsed === null ||
    (parsed as { version?: unknown }).version !== LOCK_VERSION ||
    typeof (parsed as { project_id?: unknown }).project_id !== "string"
  ) {
    throw new CliError(
      `Error: ${LOCK_FILE_RELATIVE} has an unexpected format. Fix or remove it and retry.`,
    );
  }

  const lock = parsed as LockFile;
  if (typeof lock.skills !== "object" || lock.skills === null) {
    lock.skills = {};
  }
  return lock;
}

/** Writes the lock file with stable key order so diffs stay small. */
export function writeLock(cwd: string, lock: LockFile): void {
  const lockPath = path.join(cwd, LOCK_FILE_RELATIVE);
  fs.mkdirSync(path.dirname(lockPath), { recursive: true });

  const skills: Record<string, LockEntry> = {};
  for (const name of Object.keys(lock.skills).sort()) {
    skills[name] = lock.skills[name];
  }
  const ordered: LockFile = {
    version: lock.version,
    project_id: lock.project_id,
    skills,
  };

  fs.writeFileSync(lockPath, JSON.stringify(ordered, null, 2) + "\n", "utf-8");
}

/**
 * Records freshly installed skills in the lock file, hashing their files
 * from `.claude/skills/<name>/`. Creates the lock file on first use.
 */
export function recordSkillInstalls(
  cwd: string,
  names: string[],
  serverUrl: string,
  index: RegistryIndex | null = null,
): void {
  if (names.length === 0) {
    return;
  }

  const lock = readLock(cwd) ?? emptyLock();
  const installedAt = new Date().toISOString();

  for (const name of names) {
    const skillDir = path.join(cwd, ".claude", "skills", name);
    const { hash, files } = hashDirectory(skillDir);
    const entry: LockEntry = {
      server: serverUrl,
      installed_at: installedAt,
      hash,
      files,
    };
    // A readable version next to the hash, when the installed files are the
    // registry's current version and the server knows its commit.
    const current = index?.skills[name];
    if (current !== undefined && current.hash === hash && current.commit) {
      entry.commit = current.commit;
      if (current.released) {
        entry.released = current.released;
      }
    }
    // A fresh install replaces any earlier skip: no `skip` is carried over.
    lock.skills[name] = entry;
  }

  writeLock(cwd, lock);
}
