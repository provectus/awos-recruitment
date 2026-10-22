import * as fs from "node:fs";
import * as path from "node:path";

import { displayPath, incomingRoot } from "../lib/cache-dir.js";
import { downloadBundle } from "../lib/download.js";
import { CliError } from "../lib/errors.js";
import { hashDirectory } from "../lib/lock.js";
import { fetchRegistryIndex } from "../lib/registry-index.js";
import { resolveServerUrl } from "../lib/server-url.js";
import { diffLines } from "../lib/text-diff.js";
import { backupSkill } from "./skill-update.js";

export interface DiffOptions {
  /** Most output lines per skill; the rest is counted, not printed. */
  maxLines?: number;
  /**
   * Keep the registry version in the project's cache folder
   * (`~/.cache/awos-recruitment/projects/…/incoming/<name>/`) and back up the
   * current copy, so an agent can merge the two and then run
   * `skill merged <name>`.
   */
  keep?: boolean;
}

const DEFAULT_MAX_LINES = 300;

/**
 * `skill diff [names]`: show what `skill update` would change, as a diff of
 * the files in the project against the registry's current version. With no
 * names, every installed skill that differs from the registry. The diff does
 * not separate local edits from registry changes: a local edit shows up as a
 * line the update would remove.
 */
export async function skillDiff(names: string[], options: DiffOptions = {}): Promise<void> {
  const serverUrl = resolveServerUrl();
  const cwd = process.cwd();
  const skillsDir = path.join(cwd, ".claude", "skills");
  const maxLines = options.maxLines ?? DEFAULT_MAX_LINES;

  const index = await fetchRegistryIndex(serverUrl);

  let targets: string[];
  if (names.length > 0) {
    for (const name of names) {
      if (!fs.existsSync(path.join(skillsDir, name))) {
        throw new CliError(`Error: skill '${name}' is not installed.`);
      }
      if (index.skills[name] === undefined) {
        throw new CliError(`Error: skill '${name}' is not in the registry; there is nothing to compare.`);
      }
    }
    targets = names;
  } else {
    const installed = fs.existsSync(skillsDir)
      ? fs.readdirSync(skillsDir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name)
      : [];
    targets = installed
      .filter((name) => index.skills[name] !== undefined)
      .filter((name) => hashDirectory(path.join(skillsDir, name)).hash !== index.skills[name].hash)
      .sort();
  }

  if (targets.length === 0) {
    process.stdout.write("All installed registry skills match the registry.\n");
    return;
  }

  const tempDir = await downloadBundle(`${serverUrl}/bundle/skills`, targets);
  try {
    for (const name of targets) {
      process.stdout.write(
        formatSkillDiff(name, path.join(skillsDir, name), path.join(tempDir, name), maxLines),
      );
      if (options.keep) {
        const backup = backupSkill(cwd, name);
        const incoming = path.join(incomingRoot(cwd), name);
        fs.rmSync(incoming, { recursive: true, force: true });
        fs.mkdirSync(path.dirname(incoming), { recursive: true });
        fs.cpSync(path.join(tempDir, name), incoming, { recursive: true });
        process.stdout.write(
          `Registry version of '${name}' saved to ${displayPath(incoming)}/. ` +
            `Your copy is backed up to ${displayPath(backup)}/. ` +
            `Edit .claude/skills/${name}/, then run 'skill merged ${name}'.\n\n`,
        );
      }
    }
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

/** The diff of one skill: a header with counts, then each changed, added or removed file. */
export function formatSkillDiff(
  name: string,
  localDir: string,
  registryDir: string,
  maxLines: number,
): string {
  const local = readFiles(localDir);
  const registry = readFiles(registryDir);
  const paths = [...new Set([...Object.keys(local), ...Object.keys(registry)])].sort();

  const changed = paths.filter((p) => p in local && p in registry && local[p] !== registry[p]);
  const added = paths.filter((p) => !(p in local));
  const removed = paths.filter((p) => !(p in registry));

  const body: string[] = [];
  for (const p of paths) {
    if (changed.includes(p)) {
      const d = diffLines(local[p], registry[p]);
      body.push(`--- ${p} (yours) / +++ ${p} (registry)`);
      body.push(...(d.tooLarge ? [`(too large to compare line by line: ${d.removed} → ${d.added} lines)`] : d.lines));
    } else if (added.includes(p)) {
      const lines = registry[p].split("\n");
      body.push(`+++ ${p} (new file, ${lines.length} lines)`);
      body.push(...lines.map((l) => `+${l}`));
    } else if (removed.includes(p)) {
      body.push(`--- ${p} (removed by the update; it is in your copy only)`);
    }
  }

  const header = `=== ${name}: ${changed.length} changed, ${added.length} added, ${removed.length} removed`;
  const shown = body.slice(0, maxLines);
  const more = body.length - shown.length;
  const tail = more > 0 ? [`… ${more} more lines not shown`] : [];
  return [header, ...shown, ...tail, ""].join("\n") + "\n";
}

/** Relative path (POSIX) → file text, for every file under `dir`. */
function readFiles(dir: string): Record<string, string> {
  const files: Record<string, string> = {};
  const walk = (current: string, prefix: string): void => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const abs = path.join(current, entry.name);
      const rel = prefix === "" ? entry.name : `${prefix}/${entry.name}`;
      if (entry.isDirectory()) {
        walk(abs, rel);
      } else if (entry.isFile()) {
        files[rel] = fs.readFileSync(abs, "utf-8");
      }
    }
  };
  if (fs.existsSync(dir)) {
    walk(dir, "");
  }
  return files;
}
