import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import * as readline from "node:readline";

import { downloadBundle } from "../lib/download.js";
import { CliError } from "../lib/errors.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { resolveServerUrl } from "../lib/server-url.js";
import {
  mergeHookGroups,
  type HookSettingsGroup,
} from "../lib/settings-merge.js";
import { HOOK_EVENTS } from "../lib/types.js";
import type { HookDefinition, InstallResult } from "../lib/types.js";

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
export async function installHooks(
  names: string[],
  options: { yes?: boolean } = {},
): Promise<void> {
  const serverUrl = resolveServerUrl();

  const tempDir = await downloadBundle(
    `${serverUrl}/bundle/hooks`,
    names,
  );

  let results: InstallResult[];
  try {
    // --- Consent gate: hooks execute automatically once armed — show what
    // was actually downloaded (not registry metadata) and confirm before
    // any file copy or settings write.
    printHookSummaries(tempDir, names);
    if (!options.yes) {
      const confirmed = await confirmInstall();
      if (!confirmed) {
        process.stdout.write("Aborted — nothing was installed.\n");
        return;
      }
    }

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

  const hasNotFound = results.some(
    (r) => r.status === "not-found" || r.status === "error",
  );
  if (hasNotFound) {
    process.exit(1);
  }
}

/**
 * Prints, for each requested hook, the sha256 of its entrypoint script and
 * the event bindings that are about to be armed. For a hook that is
 * already installed at `.claude/hooks/<name>` in the current working
 * directory, Phase 1 keeps the local files untouched and Phase 2's settings
 * repair reads the LOCAL `HOOK.md` — so the summary must hash and parse the
 * LOCAL copy, not the freshly downloaded bundle, or the operator would be
 * consenting to artifacts that are discarded. Not-yet-installed hooks are
 * summarized from the downloaded bundle as before. Names missing from
 * their source are reported later by processHooks as not-found; they are
 * skipped here.
 */
function printHookSummaries(tempDir: string, names: string[]): void {
  const hooksBaseDir = path.join(process.cwd(), ".claude", "hooks");

  for (const name of names) {
    const alreadyInstalled = fs.existsSync(path.join(hooksBaseDir, name));
    const sourceDir = alreadyInstalled ? hooksBaseDir : tempDir;

    const entrypoint = path.join(sourceDir, name, `${name}.sh`);
    if (!fs.existsSync(entrypoint)) {
      continue;
    }
    const sha256 = createHash("sha256")
      .update(fs.readFileSync(entrypoint))
      .digest("hex");
    process.stdout.write(`Hook '${name}'\n  entrypoint sha256: ${sha256}\n`);
    if (alreadyInstalled) {
      process.stdout.write(
        "  already installed — existing local files kept; settings derive from the local HOOK.md\n",
      );
    }

    const entries = readHookEntries(sourceDir, name);
    for (const entry of entries ?? []) {
      const details: string[] = [];
      if (entry.matcher !== undefined) {
        details.push(`matcher: ${entry.matcher}`);
      }
      if (entry.timeout !== undefined) {
        details.push(`timeout: ${entry.timeout}s`);
      }
      const suffix = details.length > 0 ? ` (${details.join(", ")})` : "";
      process.stdout.write(`  fires on: ${entry.event}${suffix}\n`);
    }
  }
}

/**
 * Interactive confirmation. Non-TTY stdin cannot answer a prompt — fail
 * closed with an instruction to pass --yes (scripts and agents must opt in
 * explicitly).
 */
async function confirmInstall(): Promise<boolean> {
  if (!process.stdin.isTTY) {
    throw new CliError(
      "Error: installing hooks arms scripts that run automatically. " +
        "Re-run with --yes to confirm non-interactively.",
    );
  }
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
  });
  const answer = await new Promise<string>((resolve) =>
    rl.question(
      "Install these hooks and enable them in .claude/settings.json? [y/N] ",
      resolve,
    ),
  );
  rl.close();
  const normalized = answer.trim().toLowerCase();
  return normalized === "y" || normalized === "yes";
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

    // Defense in depth: the server omits entrypoint-less hooks from the
    // bundle, but don't trust that blindly — a copied dir without its
    // <name>.sh would otherwise report "installed" while settings.json
    // ends up pointing at a script that was never written to disk.
    const entrypoint = path.join(targetDir, `${name}.sh`);
    if (!fs.existsSync(entrypoint)) {
      fs.rmSync(targetDir, { recursive: true, force: true });
      results.push({
        name,
        status: "error",
        message: `Error: hook '${name}' bundle is missing its entrypoint — not installed.`,
      });
      continue;
    }

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

/** Narrow an unknown frontmatter entry to a valid HookDefinition. */
function isValidHookEntry(value: unknown): value is HookDefinition {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.event === "string" &&
    (HOOK_EVENTS as readonly string[]).includes(entry.event) &&
    (entry.matcher === undefined || typeof entry.matcher === "string") &&
    (entry.timeout === undefined ||
      (typeof entry.timeout === "number" && entry.timeout > 0))
  );
}

/**
 * Reads and validates a hook's `HOOK.md` entries. Returns the entries array, or
 * `null` when the file is missing, has no frontmatter, or its `hooks` field is
 * absent, not a non-empty array, or contains any entry that fails validation
 * (missing/unknown `event`, wrong-typed `matcher`/`timeout`, etc.).
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
  const frontmatter = parseFrontmatter(content) as { hooks?: unknown } | null;

  const hooks = frontmatter?.hooks;
  if (!Array.isArray(hooks) || hooks.length === 0) {
    return null;
  }
  if (!hooks.every(isValidHookEntry)) {
    return null;
  }

  return hooks;
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
    if (result.status === "not-found" || result.status === "error") {
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
