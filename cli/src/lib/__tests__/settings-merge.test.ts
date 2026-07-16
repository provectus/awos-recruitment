import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, afterEach } from "vitest";

import {
  mergeHookGroups,
  type HookSettingsGroup,
} from "../settings-merge.js";
import { CliError } from "../errors.js";

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

/** Temp directories to clean up after each test. */
const tempDirs: string[] = [];

/** Helper: create a fresh temp dir and register it for cleanup. */
function makeTempDir(prefix: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tempDirs.push(dir);
  return dir;
}

/** Helper: write an object as pretty JSON + trailing newline to a path. */
function writeJson(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + "\n", "utf-8");
}

/** Helper: a single command group with matcher + timeout. */
function group(
  command: string,
  matcher?: string,
  timeout?: number,
): HookSettingsGroup {
  return {
    ...(matcher !== undefined && { matcher }),
    hooks: [
      {
        type: "command",
        command,
        ...(timeout !== undefined && { timeout }),
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------

afterEach(() => {
  for (const dir of tempDirs) {
    try {
      fs.rmSync(dir, { recursive: true, force: true });
    } catch {
      // best-effort
    }
  }
  tempDirs.length = 0;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("mergeHookGroups", () => {
  // -------------------------------------------------------------------------
  // 1. Fresh file creation
  // -------------------------------------------------------------------------
  it("creates settings.json with the correct shape and a trailing newline", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    const g = group("cmd.sh", "Edit|Write", 10);
    const result = mergeHookGroups(settingsPath, "PreToolUse", [g]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    expect(fs.existsSync(settingsPath)).toBe(true);

    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written).toEqual({
      hooks: {
        PreToolUse: [
          {
            matcher: "Edit|Write",
            hooks: [{ type: "command", command: "cmd.sh", timeout: 10 }],
          },
        ],
      },
    });

    const raw = fs.readFileSync(settingsPath, "utf-8");
    expect(raw).toBe(JSON.stringify(written, null, 2) + "\n");
  });

  // -------------------------------------------------------------------------
  // 2. Append to an existing event array without touching user groups
  // -------------------------------------------------------------------------
  it("appends a new group to an existing event array without mutating user groups", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    const userGroup = {
      matcher: "Bash",
      hooks: [{ type: "command", command: "user-script.sh" }],
    };
    writeJson(settingsPath, {
      hooks: { PreToolUse: [userGroup] },
    });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh", "Edit|Write", 10),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });

    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written.hooks.PreToolUse).toHaveLength(2);
    // User group untouched and still first.
    expect(written.hooks.PreToolUse[0]).toEqual(userGroup);
    expect(written.hooks.PreToolUse[1]).toEqual(group("cmd.sh", "Edit|Write", 10));
  });

  // -------------------------------------------------------------------------
  // 3. Dedupe matrix
  // -------------------------------------------------------------------------
  it("skips when matcher and command both match", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      hooks: { PreToolUse: [group("cmd.sh", "Edit|Write", 10)] },
    });
    const before = fs.readFileSync(settingsPath, "utf-8");

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh", "Edit|Write", 10),
    ]);

    expect(result).toEqual({ added: 0, skipped: 1 });
    // Not written — byte-identical.
    expect(fs.readFileSync(settingsPath, "utf-8")).toBe(before);
  });

  it("adds when matcher matches but command differs", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      hooks: { PreToolUse: [group("cmd-a.sh", "Edit|Write")] },
    });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd-b.sh", "Edit|Write"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written.hooks.PreToolUse).toHaveLength(2);
  });

  it("adds when command matches but matcher differs", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      hooks: { PreToolUse: [group("cmd.sh", "Edit")] },
    });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh", "Write"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written.hooks.PreToolUse).toHaveLength(2);
  });

  it("skips when both matchers are absent and command matches", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      hooks: { SessionStart: [group("cmd.sh")] },
    });
    const before = fs.readFileSync(settingsPath, "utf-8");

    const result = mergeHookGroups(settingsPath, "SessionStart", [
      group("cmd.sh"),
    ]);

    expect(result).toEqual({ added: 0, skipped: 1 });
    expect(fs.readFileSync(settingsPath, "utf-8")).toBe(before);
  });

  it("adds when incoming matcher is absent but existing has a matcher", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      hooks: { PreToolUse: [group("cmd.sh", "Edit|Write")] },
    });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written.hooks.PreToolUse).toHaveLength(2);
  });

  // -------------------------------------------------------------------------
  // 4. Malformed JSON → CliError, file untouched
  // -------------------------------------------------------------------------
  it("throws CliError on malformed JSON and does not modify the file", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
    fs.writeFileSync(settingsPath, "{ not valid json !!!", "utf-8");
    const before = fs.readFileSync(settingsPath, "utf-8");

    expect(() =>
      mergeHookGroups(settingsPath, "PreToolUse", [group("cmd.sh")]),
    ).toThrow(CliError);

    try {
      mergeHookGroups(settingsPath, "PreToolUse", [group("cmd.sh")]);
    } catch (error: unknown) {
      expect(error).toBeInstanceOf(CliError);
      expect((error as CliError).message).toContain("malformed JSON");
    }

    // File is left exactly as-is (never overwritten).
    expect(fs.readFileSync(settingsPath, "utf-8")).toBe(before);
  });

  // -------------------------------------------------------------------------
  // 5. Structure guards on weird existing shapes
  // -------------------------------------------------------------------------
  it("replaces a non-object hooks value while preserving other top-level keys", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      $schema: "https://example.com/schema.json",
      hooks: "x",
    });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh", "Edit|Write"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(written.$schema).toBe("https://example.com/schema.json");
    expect(written.hooks.PreToolUse).toHaveLength(1);
  });

  it("guards an array-typed hooks value without crashing", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, { hooks: [] });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(Array.isArray(written.hooks)).toBe(false);
    expect(written.hooks.PreToolUse).toHaveLength(1);
  });

  it("guards a non-array event value without crashing", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, { hooks: { PreToolUse: {} } });

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh"),
    ]);

    expect(result).toEqual({ added: 1, skipped: 0 });
    const written = JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
    expect(Array.isArray(written.hooks.PreToolUse)).toBe(true);
    expect(written.hooks.PreToolUse).toHaveLength(1);
  });

  // -------------------------------------------------------------------------
  // 6. No-op merge leaves the file byte-identical
  // -------------------------------------------------------------------------
  it("leaves the file byte-identical on a no-op (all-skipped) merge", () => {
    const dir = makeTempDir("settings-merge-");
    const settingsPath = path.join(dir, ".claude", "settings.json");

    writeJson(settingsPath, {
      other: { nested: true },
      hooks: { PreToolUse: [group("cmd.sh", "Edit|Write", 10)] },
    });
    const before = fs.readFileSync(settingsPath, "utf-8");

    const result = mergeHookGroups(settingsPath, "PreToolUse", [
      group("cmd.sh", "Edit|Write", 10),
    ]);

    expect(result).toEqual({ added: 0, skipped: 1 });
    expect(fs.readFileSync(settingsPath, "utf-8")).toBe(before);
  });
});
