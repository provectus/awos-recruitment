import * as fs from "node:fs";
import * as path from "node:path";

import { downloadBundle } from "../lib/download.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { resolveServerUrl } from "../lib/server-url.js";
import {
  mergeHookGroups,
  type HookSettingsGroup,
} from "../lib/settings-merge.js";
import type {
  HookDefinition,
  HookFrontmatter,
  InstallResult,
} from "../lib/types.js";

/**
 * Installs one or more hooks by downloading their directories from the AWOS
 * server and copying them into `.claude/hooks/<name>/` in the current working
 * directory, then injecting derived entries into `.claude/settings.json`.
 *
 * Phase 1: hook directory installation. Directories that already exist are
 * silently skipped (a skip is a SUCCESS, not a failure).
 *
 * Phase 2: settings injection. Runs for BOTH `"installed"` and `"skipped"`
 * hooks (the repair requirement) — a skipped hook whose settings entry is
 * missing gets re-injected. Unparseable/invalid `HOOK.md` frontmatter degrades
 * gracefully: the files stay installed, a warning is recorded, and no settings
 * change is made.
 *
 * Exits with code 1 only when some requested hook has `"not-found"` status
 * (the `agent.ts` rule). Installed and skipped hooks exit normally; warnings do
 * NOT change the exit code. A `CliError` from a malformed `settings.json`
 * propagates to the error boundary (exit 1), which is correct.
 */
export async function installHooks(names: string[]): Promise<void> {
  const serverUrl = resolveServerUrl();

  const tempDir = await downloadBundle(
    `${serverUrl}/bundle/hooks`,
    names,
  );

  let results: InstallResult[];
  try {
    // --- Phase 1: Install hook directories -----------------------------------
    results = processHooks(tempDir, names);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  // --- Phase 2: Settings injection -------------------------------------------
  // Runs for both "installed" and "skipped" hooks (repair semantics).
  const settings = injectSettings(results);

  printResults(results);
  printSettingsSummary(settings);

  const hasNotFound = results.some((r) => r.status === "not-found");
  if (hasNotFound) {
    process.exit(1);
  }
}

/**
 * Compares requested names against what was extracted, copies found hook
 * directories into the target location, and returns per-item results.
 *
 * This is a pure function with no console I/O and no `process.exit` calls —
 * callers interpret the results and perform output. `fs.cpSync` preserves file
 * mode bits, so the entrypoint script stays executable end-to-end.
 */
export function processHooks(
  tempDir: string,
  requestedNames: string[],
): InstallResult[] {
  const extractedDirs = new Set(fs.readdirSync(tempDir));
  const results: InstallResult[] = [];

  const hooksBaseDir = path.join(process.cwd(), ".claude", "hooks");

  for (const name of requestedNames) {
    if (!extractedDirs.has(name)) {
      results.push({
        name,
        status: "not-found",
        message: `Error: hook '${name}' not found.`,
      });
      continue;
    }

    const targetDir = path.join(hooksBaseDir, name);

    if (fs.existsSync(targetDir)) {
      results.push({
        name,
        status: "skipped",
        message: `Skipped hook '${name}' — already installed.`,
      });
      continue;
    }

    fs.mkdirSync(hooksBaseDir, { recursive: true });
    const sourceDir = path.join(tempDir, name);
    fs.cpSync(sourceDir, targetDir, { recursive: true });

    results.push({
      name,
      status: "installed",
      message: `Installed hook '${name}' to .claude/hooks/${name}/`,
    });
  }

  return results;
}

/** Accumulated outcome of the Phase-2 settings-injection pass. */
interface SettingsInjectionResult {
  added: number;
  skipped: number;
  warnings: string[];
}

/**
 * For every installed or skipped hook, parses its `HOOK.md` frontmatter, derives
 * the settings groups, and merges them into `.claude/settings.json` per event.
 *
 * A hook with a missing/unparseable/invalid `HOOK.md` (no frontmatter, or a
 * `hooks` field that is absent or not an array) is skipped with a warning — the
 * files stay installed and no settings change is made for it.
 */
function injectSettings(results: InstallResult[]): SettingsInjectionResult {
  const settingsPath = path.join(
    process.cwd(),
    ".claude",
    "settings.json",
  );
  const hooksBaseDir = path.join(process.cwd(), ".claude", "hooks");

  let added = 0;
  let skipped = 0;
  const warnings: string[] = [];

  for (const result of results) {
    if (result.status !== "installed" && result.status !== "skipped") {
      continue;
    }

    const entries = readHookEntries(hooksBaseDir, result.name);
    if (entries === null) {
      warnings.push(
        `Warning: could not parse hook '${result.name}' metadata — settings not updated.`,
      );
      continue;
    }

    const groupsByEvent = groupEntriesByEvent(entries, result.name);

    for (const [event, groups] of groupsByEvent) {
      const merged = mergeHookGroups(settingsPath, event, groups);
      added += merged.added;
      skipped += merged.skipped;
    }
  }

  return { added, skipped, warnings };
}

/**
 * Reads and validates a hook's `HOOK.md` entries. Returns the entries array, or
 * `null` when the file is missing, has no frontmatter, or its `hooks` field is
 * absent or not an array.
 */
function readHookEntries(
  hooksBaseDir: string,
  name: string,
): HookDefinition[] | null {
  const hookFile = path.join(hooksBaseDir, name, "HOOK.md");
  if (!fs.existsSync(hookFile)) {
    return null;
  }

  const content = fs.readFileSync(hookFile, "utf-8");
  const frontmatter = parseFrontmatter(content) as HookFrontmatter | null;

  if (!frontmatter || !Array.isArray(frontmatter.hooks)) {
    return null;
  }

  return frontmatter.hooks;
}

/**
 * Groups a hook's entries by event, building one settings group per entry.
 * `matcher` and `timeout` keys are omitted when unset. The command is always
 * the derived entrypoint path — `$CLAUDE_PROJECT_DIR` stays a literal string
 * that Claude Code expands at runtime.
 */
function groupEntriesByEvent(
  entries: HookDefinition[],
  name: string,
): Map<string, HookSettingsGroup[]> {
  const command = `$CLAUDE_PROJECT_DIR/.claude/hooks/${name}/${name}.sh`;
  const groupsByEvent = new Map<string, HookSettingsGroup[]>();

  for (const entry of entries) {
    const group: HookSettingsGroup = {
      ...(entry.matcher !== undefined && { matcher: entry.matcher }),
      hooks: [
        {
          type: "command",
          command,
          ...(entry.timeout !== undefined && { timeout: entry.timeout }),
        },
      ],
    };

    const existing = groupsByEvent.get(entry.event);
    if (existing) {
      existing.push(group);
    } else {
      groupsByEvent.set(entry.event, [group]);
    }
  }

  return groupsByEvent;
}

/**
 * Prints each install result. Installed and skipped hooks go to stdout
 * (skips are a success); not-found errors go to stderr.
 */
function printResults(results: InstallResult[]): void {
  for (const result of results) {
    if (result.status === "not-found") {
      process.stderr.write(result.message + "\n");
    } else {
      process.stdout.write(result.message + "\n");
    }
  }
}

/**
 * Prints the Phase-2 settings summary: an added/skipped count line to stdout
 * and any per-hook warnings to stderr.
 */
function printSettingsSummary(settings: SettingsInjectionResult): void {
  process.stdout.write(
    `Settings: ${settings.added} entries added, ${settings.skipped} entries skipped (already present)\n`,
  );

  for (const warning of settings.warnings) {
    process.stderr.write(warning + "\n");
  }
}
