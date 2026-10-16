import { readLock } from "../lib/lock.js";
import { fetchRegistryIndex } from "../lib/registry-index.js";
import { resolveServerUrl } from "../lib/server-url.js";
import {
  computeSkillStatuses,
  STATE_LABELS,
  type SkillStatus,
} from "../lib/status.js";
import { sendTelemetry, type ClientEvent } from "../lib/telemetry.js";

export interface StatusOptions {
  /** Print the statuses as JSON instead of a table. */
  json?: boolean;
}

/**
 * `skill status`: compares every installed skill with the registry and
 * prints one line per skill. Reads files and the server; writes nothing.
 */
export async function skillStatus(options: StatusOptions = {}): Promise<void> {
  const serverUrl = resolveServerUrl();
  const cwd = process.cwd();

  const lock = readLock(cwd);
  const index = await fetchRegistryIndex(serverUrl);
  const statuses = computeSkillStatuses(cwd, lock, index);

  if (options.json) {
    process.stdout.write(JSON.stringify(statuses, null, 2) + "\n");
  } else {
    process.stdout.write(formatStatusTable(statuses));
  }

  if (lock !== null) {
    await sendTelemetry(serverUrl, lock.project_id, statusEvents(statuses));
  }
}

/** One line per skill plus a summary line. */
export function formatStatusTable(statuses: SkillStatus[]): string {
  if (statuses.length === 0) {
    return "No skills installed in .claude/skills/.\n";
  }

  const nameWidth = Math.max(...statuses.map((s) => s.name.length));
  const labelWidth = Math.max(
    ...statuses.map((s) => STATE_LABELS[s.state].length),
  );

  const lines = statuses.map((s) => {
    const label = STATE_LABELS[s.state];
    if (s.detail === "") {
      return `${s.name.padEnd(nameWidth)}  ${label}`;
    }
    return `${s.name.padEnd(nameWidth)}  ${label.padEnd(labelWidth)}  ${s.detail}`;
  });

  const outdated = statuses.filter((s) => s.state === "outdated").length;
  const adopt = statuses.filter((s) => s.adopt).length;
  const removed = statuses.filter((s) => s.state === "removed").length;

  const summary: string[] = [];
  if (outdated > 0) {
    summary.push(`${outdated} outdated`);
  }
  if (removed > 0) {
    summary.push(`${removed} removed from registry`);
  }
  if (outdated > 0 || adopt > 0) {
    summary.push("run `npx @provectusinc/awos-recruitment skill update`");
  }
  const footer = summary.length > 0 ? `\n${summary.join("; ")}.\n` : "";

  return lines.join("\n") + "\n" + footer;
}

/** Events for one status check: a summary plus one per removed skill in use. */
export function statusEvents(statuses: SkillStatus[]): ClientEvent[] {
  const count = (state: SkillStatus["state"]): number =>
    statuses.filter((s) => s.state === state).length;

  const events: ClientEvent[] = [
    {
      event: "capability_update_checked",
      properties: {
        total: statuses.length,
        outdated: count("outdated"),
        modified_locally: count("modified-locally"),
        removed: count("removed"),
        no_lock_entry: count("no-lock-entry"),
      },
    },
  ];

  for (const s of statuses) {
    if (s.state === "removed") {
      events.push({
        event: "capability_removed_in_use",
        capability_name: s.name,
        capability_type: "skill",
        properties: { has_replacement: s.replacement !== null },
      });
    }
  }

  return events;
}
