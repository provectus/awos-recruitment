import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import * as path from "node:path";

import { CliError } from "./errors.js";

/**
 * A single command entry inside a hook group's `hooks` array, matching the
 * shape Claude Code expects in `.claude/settings.json`.
 */
export interface HookCommand {
  type: "command";
  command: string;
  timeout?: number;
}

/**
 * A hook group as written under `hooks.<Event>` in `.claude/settings.json`.
 * `matcher` is omitted for events that don't use tool-name matchers.
 */
export interface HookSettingsGroup {
  matcher?: string;
  hooks: HookCommand[];
}

/** Result of a merge: how many incoming groups were appended vs. skipped. */
export interface MergeResult {
  added: number;
  skipped: number;
}

/**
 * Reads (or creates) `.claude/settings.json` and merges the given hook groups
 * under `hooks.<event>` using append-new-group semantics with global dedupe.
 *
 * Behavior:
 * - `ENOENT` → start from an empty object `{}`; other fs errors re-thrown.
 * - Malformed JSON → throw `CliError` and NEVER overwrite the file.
 * - Structure guards: `parsed.hooks` is coerced to `{}` if it is missing or not
 *   a plain (non-array) object; `parsed.hooks[event]` is coerced to `[]` if it
 *   is missing or not an array. All other top-level keys are round-tripped.
 * - Dedupe: an incoming group is PRESENT (→ skipped) when ANY existing group
 *   under the event has the same `matcher` (both-absent counts as equal) AND its
 *   inner `hooks` array contains an entry whose `command` equals the incoming
 *   command. Otherwise the incoming group is appended as-is (→ added). Existing
 *   groups are never mutated.
 * - The file is written only when at least one group was added, so idempotent
 *   re-runs leave the file byte-identical.
 *
 * @returns counts of added and skipped groups.
 */
export function mergeHookGroups(
  settingsPath: string,
  event: string,
  groups: HookSettingsGroup[],
): MergeResult {
  const parsed = readSettings(settingsPath);

  // Structure guard: parsed.hooks must be a plain (non-array) object.
  if (!isPlainObject(parsed.hooks)) {
    parsed.hooks = {};
  }
  const hooks = parsed.hooks as Record<string, unknown>;

  // Structure guard: parsed.hooks[event] must be an array.
  if (!Array.isArray(hooks[event])) {
    hooks[event] = [];
  }
  const eventGroups = hooks[event] as unknown[];

  let added = 0;
  let skipped = 0;

  for (const group of groups) {
    if (isGroupPresent(eventGroups, group)) {
      skipped++;
    } else {
      eventGroups.push(group);
      added++;
    }
  }

  if (added > 0) {
    mkdirSync(path.dirname(settingsPath), { recursive: true });
    writeFileSync(
      settingsPath,
      JSON.stringify(parsed, null, 2) + "\n",
      "utf-8",
    );
  }

  return { added, skipped };
}

/**
 * Reads and parses `settings.json`. Returns `{}` when the file is absent.
 * Throws `CliError` on malformed JSON (without touching the file) and re-throws
 * any other fs error.
 */
function readSettings(settingsPath: string): Record<string, unknown> {
  let raw: string;
  try {
    raw = readFileSync(settingsPath, "utf-8");
  } catch (error: unknown) {
    if (
      error instanceof Error &&
      "code" in error &&
      (error as NodeJS.ErrnoException).code === "ENOENT"
    ) {
      return {};
    }
    throw error;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new CliError(
      "Error: .claude/settings.json contains malformed JSON.",
    );
  }

  // A JSON scalar/array at the root is not a settings object — guard it.
  if (!isPlainObject(parsed)) {
    return {};
  }

  return parsed;
}

/**
 * Determines whether an incoming group is already present among the existing
 * groups: same matcher (both-absent counts as equal) and a shared command in
 * the inner `hooks` array.
 */
function isGroupPresent(
  existingGroups: unknown[],
  incoming: HookSettingsGroup,
): boolean {
  const incomingCommands = collectCommands(incoming.hooks);

  return existingGroups.some((existing) => {
    if (!isPlainObject(existing)) {
      return false;
    }

    if (!matchersEqual(existing.matcher, incoming.matcher)) {
      return false;
    }

    if (!Array.isArray(existing.hooks)) {
      return false;
    }

    return existing.hooks.some(
      (entry) =>
        isPlainObject(entry) &&
        typeof entry.command === "string" &&
        incomingCommands.has(entry.command),
    );
  });
}

/** Collects the `command` strings from a group's inner hooks array. */
function collectCommands(hooks: HookCommand[]): Set<string> {
  const commands = new Set<string>();
  for (const entry of hooks) {
    commands.add(entry.command);
  }
  return commands;
}

/**
 * Matchers are equal when both are absent (undefined) or both are the same
 * string. Any other combination is unequal.
 */
function matchersEqual(a: unknown, b: string | undefined): boolean {
  const normalizedA = a === undefined || a === null ? undefined : a;
  return normalizedA === b;
}

/** True for a non-null, non-array object. */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
