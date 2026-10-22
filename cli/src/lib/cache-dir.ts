import { createHash } from "node:crypto";
import * as os from "node:os";
import * as path from "node:path";

/**
 * Per-project working folder outside the project:
 * `${XDG_CACHE_HOME:-~/.cache}/awos-recruitment/projects/<folder>-<hash>/`.
 *
 * Backups and the registry copy for a merge live here, not in `.claude/`:
 * files written inside the project end up in git, and Claude Code prints
 * every file a command changes in the project, which buried the answer.
 */
export function projectCacheDir(cwd: string): string {
  const base = process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache");
  const resolved = path.resolve(cwd);
  const key = createHash("sha256").update(resolved).digest("hex").slice(0, 10);
  return path.join(base, "awos-recruitment", "projects", `${path.basename(resolved)}-${key}`);
}

/** Where `skill update` and `skill diff --keep` back up a skill: `<cache>/backups/<name>/<timestamp>/`. */
export function backupRoot(cwd: string): string {
  return path.join(projectCacheDir(cwd), "backups");
}

/** Where `skill diff --keep` saves the registry version for a merge: `<cache>/incoming/<name>/`. */
export function incomingRoot(cwd: string): string {
  return path.join(projectCacheDir(cwd), "incoming");
}

/** A path for messages: `~/…` when it is under the home folder. */
export function displayPath(p: string): string {
  const home = os.homedir();
  return p.startsWith(home + path.sep) ? `~${p.slice(home.length)}` : p;
}
