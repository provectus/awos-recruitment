import * as fs from "node:fs";
import * as path from "node:path";
import * as readline from "node:readline/promises";

import { downloadBundle } from "../lib/download.js";
import { backupRoot, displayPath } from "../lib/cache-dir.js";
import { CliError } from "../lib/errors.js";
import { readLock, recordSkillInstalls } from "../lib/lock.js";
import { fetchRegistryHistory, fetchRegistryIndex } from "../lib/registry-index.js";
import { resolveServerUrl } from "../lib/server-url.js";
import { computeSkillStatuses, needsHistory, type SkillStatus } from "../lib/status.js";
import { sendTelemetry, type ClientEvent } from "../lib/telemetry.js";
import { processSkills } from "./skill.js";
import { statusEvents } from "./skill-status.js";

export interface UpdateOptions {
  /** Print what would change and stop. */
  dryRun?: boolean;
  /** Replace skills with local changes without asking. */
  overwrite?: boolean;
  /** Keep skills with local changes without asking. */
  noOverwrite?: boolean;
}

/** What to do with a skill that has local changes and a newer registry version. */
export type ConflictDecision = "overwrite" | "skip" | "backup";


interface PlannedAction {
  status: SkillStatus;
  action: "replace" | "record" | "ask" | "keep" | "report";
  reason: string;
}

/**
 * `skill update [names]`: replaces outdated skills with the registry
 * version and records the result in the lock file. Skills with local
 * changes are only replaced after a decision (prompt, `--overwrite` or
 * `--no-overwrite`); a backup goes to the project's cache folder
 * (`~/.cache/awos-recruitment/projects/…/backups/`), outside the project.
 */
export async function skillUpdate(
  names: string[],
  options: UpdateOptions = {},
): Promise<void> {
  if (options.overwrite && options.noOverwrite) {
    throw new CliError("Error: --overwrite and --no-overwrite exclude each other.");
  }

  const serverUrl = resolveServerUrl();
  const cwd = process.cwd();

  const lock = readLock(cwd);
  const index = await fetchRegistryIndex(serverUrl);
  let statuses = computeSkillStatuses(cwd, lock, index);
  if (needsHistory(statuses)) {
    const history = await fetchRegistryHistory(serverUrl);
    statuses = computeSkillStatuses(cwd, lock, index, history);
  }

  if (names.length > 0) {
    const known = new Set(statuses.map((s) => s.name));
    const unknown = names.filter((n) => !known.has(n));
    if (unknown.length > 0) {
      throw new CliError(
        `Error: not installed: ${unknown.join(", ")}. Use 'skill <name>' to install.`,
      );
    }
    const wanted = new Set(names);
    // Naming a skill overrides an earlier `skill skip` for it.
    statuses = statuses
      .filter((s) => wanted.has(s.name))
      .map((s) =>
        s.state === "skipped"
          ? {
              ...s,
              state: s.changedFiles.length > 0 ? ("modified-locally" as const) : ("outdated" as const),
              registryChanged: true,
            }
          : s,
      );
  }

  const plan = planUpdate(statuses);

  if (options.dryRun) {
    process.stdout.write(formatPlan(plan));
    return;
  }

  // --- Decide conflicts --------------------------------------------------------
  const toReplace: { status: SkillStatus; backup: boolean }[] = [];
  const toRecord: string[] = [];
  const events: ClientEvent[] = [];

  for (const item of plan) {
    switch (item.action) {
      case "replace":
        toReplace.push({ status: item.status, backup: false });
        break;
      case "record":
        toRecord.push(item.status.name);
        break;
      case "ask": {
        const { decision, note } = await decideConflict(item.status, options);
        if (decision === "skip") {
          process.stderr.write(
            `Kept local copy of '${item.status.name}' (${item.status.changedFiles.length} changed file(s))${note}.\n`,
          );
        } else {
          toReplace.push({ status: item.status, backup: decision === "backup" });
        }
        break;
      }
      case "keep":
      case "report":
        process.stderr.write(`${item.status.name}: ${item.reason}\n`);
        break;
    }
  }

  // --- Apply -------------------------------------------------------------------
  if (toRecord.length > 0) {
    recordSkillInstalls(cwd, toRecord, serverUrl, index);
    for (const name of toRecord) {
      process.stdout.write(`Recorded '${name}' (already current).\n`);
    }
  }

  if (toReplace.length > 0) {
    const replaceNames = toReplace.map((r) => r.status.name);
    const tempDir = await downloadBundle(`${serverUrl}/bundle/skills`, replaceNames);
    try {
      for (const { status, backup } of toReplace) {
        if (backup) {
          const backupDir = backupSkill(cwd, status.name);
          process.stdout.write(`Backed up '${status.name}' to ${displayPath(backupDir)}/\n`);
        }
      }
      const results = processSkills(tempDir, replaceNames, { force: true });
      const installed = results.filter((r) => r.status === "installed").map((r) => r.name);
      recordSkillInstalls(cwd, installed, serverUrl, index);

      for (const result of results) {
        if (result.status === "installed") {
          process.stdout.write(`Updated '${result.name}'.\n`);
          const item = toReplace.find((r) => r.status.name === result.name);
          events.push({
            event: "capability_updated",
            capability_name: result.name,
            capability_type: "skill",
            properties: {
              had_local_changes: (item?.status.changedFiles.length ?? 0) > 0,
              backup: item?.backup ?? false,
            },
          });
        } else {
          process.stderr.write(result.message + "\n");
        }
      }
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  }

  if (toRecord.length === 0 && toReplace.length === 0) {
    process.stdout.write("Nothing to update.\n");
  }

  const finalLock = readLock(cwd);
  if (finalLock !== null) {
    await sendTelemetry(serverUrl, finalLock.project_id, [
      ...statusEvents(statuses),
      ...events,
    ]);
  }
}

/** Maps each status to the action `update` takes for it. Pure. */
export function planUpdate(statuses: SkillStatus[]): PlannedAction[] {
  return statuses.map((status) => {
    switch (status.state) {
      case "outdated":
        return { status, action: "replace", reason: "registry has a newer version" };
      case "up-to-date":
        return status.adopt
          ? { status, action: "record", reason: "files match the registry; record in lock file" }
          : { status, action: "keep", reason: "up to date" };
      case "skipped":
        return {
          status,
          action: "keep",
          reason: "you skipped this version; name the skill to update it anyway",
        };
      case "modified-locally":
        return status.registryChanged
          ? { status, action: "ask", reason: "local changes and a newer registry version" }
          : { status, action: "keep", reason: "local changes kept; the registry is unchanged" };
      case "removed":
        return {
          status,
          action: "report",
          reason: status.replacement
            ? `removed from the registry; install '${status.replacement}' instead`
            : "removed from the registry; no replacement",
        };
      case "no-lock-entry":
        return {
          status,
          action: "report",
          reason: "version unknown (installed before the lock file); `skill <name> --force` adopts the registry version",
        };
      case "not-in-registry":
        return { status, action: "report", reason: "not in the registry; left untouched" };
      case "missing-locally":
        return { status, action: "report", reason: "folder missing; `skill <name>` reinstalls it" };
    }
  });
}

/** Dry-run output: one line per skill. */
export function formatPlan(plan: PlannedAction[]): string {
  if (plan.length === 0) {
    return "No skills installed in .claude/skills/.\n";
  }
  const verbs: Record<PlannedAction["action"], string> = {
    replace: "would update",
    record: "would record",
    ask: "would ask",
    keep: "would keep",
    report: "would skip",
  };
  const width = Math.max(...plan.map((p) => p.status.name.length));
  return (
    plan
      .map((p) => `${p.status.name.padEnd(width)}  ${verbs[p.action].padEnd(12)}  ${p.reason}`)
      .join("\n") + "\n"
  );
}

/** Copies the current skill folder to `<project cache>/backups/<name>/<timestamp>/`. */
export function backupSkill(cwd: string, name: string): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const target = path.join(backupRoot(cwd), name, stamp);
  fs.mkdirSync(target, { recursive: true });
  fs.cpSync(path.join(cwd, ".claude", "skills", name), target, { recursive: true });
  return target;
}

/**
 * Decides what to do with a locally modified skill. Flags win; without a
 * terminal the local copy is kept; otherwise the operator is asked.
 */
async function decideConflict(
  status: SkillStatus,
  options: UpdateOptions,
): Promise<{ decision: ConflictDecision; note: string }> {
  if (options.overwrite) {
    return { decision: "overwrite", note: "" };
  }
  if (options.noOverwrite) {
    return { decision: "skip", note: "" };
  }
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    return {
      decision: "skip",
      note: "; the registry has a newer version but there is no terminal to ask. Use --overwrite or --no-overwrite",
    };
  }

  const files = status.changedFiles.slice(0, 5).join(", ");
  const more = status.changedFiles.length > 5 ? ", …" : "";
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    for (;;) {
      const answer = (
        await rl.question(
          `'${status.name}' has local changes (${files}${more}) and a newer registry version.\n` +
            "  [o] overwrite  [s] skip  [b] back up and overwrite  > ",
        )
      )
        .trim()
        .toLowerCase();
      if (answer === "o" || answer === "overwrite") return { decision: "overwrite", note: "" };
      if (answer === "s" || answer === "skip" || answer === "") return { decision: "skip", note: "" };
      if (answer === "b" || answer === "backup") return { decision: "backup", note: "" };
    }
  } finally {
    rl.close();
  }
}
