import * as fs from "node:fs";
import * as path from "node:path";

import { hashDirectory, type LockFile } from "./lock.js";
import type { RegistryIndex } from "./registry-index.js";

export type SkillState =
  | "up-to-date"
  | "outdated"
  | "modified-locally"
  | "removed"
  | "not-in-registry"
  | "no-lock-entry"
  | "missing-locally";

export interface SkillStatus {
  name: string;
  state: SkillState;
  /** One line for humans: changed files, replacement, hints. */
  detail: string;
  /** The registry has a version that differs from the one in the lock file. */
  registryChanged: boolean;
  /** Local files differ from the lock entry (user edits). */
  changedFiles: string[];
  /** Local files equal the registry version but the lock file does not say so yet. */
  adopt: boolean;
  replacement: string | null;
  localHash: string | null;
  lockHash: string | null;
  registryHash: string | null;
}

/** Human labels for the status table. */
export const STATE_LABELS: Record<SkillState, string> = {
  "up-to-date": "up to date",
  outdated: "outdated",
  "modified-locally": "modified locally",
  removed: "removed from registry",
  "not-in-registry": "not in registry",
  "no-lock-entry": "no lock entry",
  "missing-locally": "missing locally",
};

function listSkillDirs(cwd: string): string[] {
  const skillsDir = path.join(cwd, ".claude", "skills");
  if (!fs.existsSync(skillsDir)) {
    return [];
  }
  return fs
    .readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name);
}

function diffFiles(
  a: Record<string, string>,
  b: Record<string, string>,
): string[] {
  const names = new Set([...Object.keys(a), ...Object.keys(b)]);
  return [...names].filter((name) => a[name] !== b[name]).sort();
}

/**
 * Compares every installed skill (lock file plus `.claude/skills/*`) with
 * the registry index. Pure: reads files, writes nothing.
 */
export function computeSkillStatuses(
  cwd: string,
  lock: LockFile | null,
  index: RegistryIndex,
): SkillStatus[] {
  const names = new Set<string>([
    ...Object.keys(lock?.skills ?? {}),
    ...listSkillDirs(cwd),
  ]);

  const statuses: SkillStatus[] = [];
  for (const name of [...names].sort()) {
    const skillDir = path.join(cwd, ".claude", "skills", name);
    const local = fs.existsSync(skillDir) ? hashDirectory(skillDir) : null;
    const lockEntry = lock?.skills[name] ?? null;
    const registry = index.skills[name] ?? null;
    const tombstone = index.removed.skills[name] ?? null;

    const base: SkillStatus = {
      name,
      state: "up-to-date",
      detail: "",
      registryChanged: false,
      changedFiles: [],
      adopt: false,
      replacement: tombstone?.replacement ?? null,
      localHash: local?.hash ?? null,
      lockHash: lockEntry?.hash ?? null,
      registryHash: registry?.hash ?? null,
    };

    if (local === null) {
      statuses.push({
        ...base,
        state: "missing-locally",
        detail: "in the lock file but .claude/skills/ has no such folder",
      });
      continue;
    }

    if (tombstone !== null) {
      const when = tombstone.removed;
      const replacement = tombstone.replacement
        ? `replacement: ${tombstone.replacement}`
        : "no replacement";
      statuses.push({
        ...base,
        state: "removed",
        detail: `removed ${when}; ${replacement}`,
        changedFiles: lockEntry ? diffFiles(lockEntry.files, local.files) : [],
      });
      continue;
    }

    if (registry === null) {
      statuses.push({
        ...base,
        state: "not-in-registry",
        detail: "the registry has no skill with this name",
        changedFiles: lockEntry ? diffFiles(lockEntry.files, local.files) : [],
      });
      continue;
    }

    // Local files equal the registry version: current, whatever the lock says.
    if (local.hash === registry.hash) {
      const adopt = lockEntry === null || lockEntry.hash !== registry.hash;
      statuses.push({
        ...base,
        state: "up-to-date",
        detail: adopt ? "not recorded in the lock file yet; `skill update` records it" : "",
        adopt,
      });
      continue;
    }

    if (lockEntry === null) {
      statuses.push({
        ...base,
        state: "no-lock-entry",
        detail:
          "installed before the lock file; differs from the registry. Reinstall with `skill <name> --force` to adopt the registry version",
      });
      continue;
    }

    const changedFiles = diffFiles(lockEntry.files, local.files);
    const registryChanged = registry.hash !== lockEntry.hash;

    if (changedFiles.length > 0) {
      const count = `${changedFiles.length} file${changedFiles.length === 1 ? "" : "s"} changed`;
      statuses.push({
        ...base,
        state: "modified-locally",
        detail: registryChanged
          ? `${count}; the registry has a newer version`
          : `${count}; the registry is unchanged`,
        registryChanged,
        changedFiles,
      });
      continue;
    }

    statuses.push({
      ...base,
      state: registryChanged ? "outdated" : "up-to-date",
      detail: registryChanged ? `installed ${lockEntry.installed_at.slice(0, 10)}` : "",
      registryChanged,
    });
  }

  return statuses;
}
