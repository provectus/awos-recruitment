import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { installHooks } from "../hook.js";

// ---------------------------------------------------------------------------
// Mock downloadBundle -- vi.hoisted ensures the variable is available
// inside the hoisted vi.mock factory.
// ---------------------------------------------------------------------------

const { mockDownloadBundle } = vi.hoisted(() => ({
  mockDownloadBundle: vi.fn<(url: string, names: string[]) => Promise<string>>(),
}));

vi.mock("../../lib/download.js", () => ({
  downloadBundle: mockDownloadBundle,
}));

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

/**
 * Helper: stage an extracted-bundle temp dir containing a single hook named
 * `docs-that-work-gate` with a HOOK.md and an executable entrypoint script.
 * Returns the bundle dir path.
 */
function stageDocsGateBundle(): string {
  const bundleDir = makeTempDir("bundle-");
  const hookSrc = path.join(bundleDir, "docs-that-work-gate");
  fs.mkdirSync(hookSrc, { recursive: true });
  fs.writeFileSync(
    path.join(hookSrc, "HOOK.md"),
    "# Docs That Work Gate",
    "utf-8",
  );
  const scriptPath = path.join(hookSrc, "docs-that-work-gate.sh");
  fs.writeFileSync(scriptPath, "#!/usr/bin/env bash\nexit 0\n", "utf-8");
  fs.chmodSync(scriptPath, 0o755);
  return bundleDir;
}

/**
 * Helper: stage a bundle for a hook with a real YAML frontmatter HOOK.md.
 * Returns the bundle dir path. `hooksYaml` is inserted verbatim under the
 * `hooks:` frontmatter key.
 */
function stageBundleWithFrontmatter(name: string, hooksYaml: string): string {
  const bundleDir = makeTempDir("bundle-");
  const hookSrc = path.join(bundleDir, name);
  fs.mkdirSync(hookSrc, { recursive: true });
  const hookMd = `---\nname: ${name}\ndescription: Test hook\nhooks:\n${hooksYaml}---\n\nBody.\n`;
  fs.writeFileSync(path.join(hookSrc, "HOOK.md"), hookMd, "utf-8");
  const scriptPath = path.join(hookSrc, `${name}.sh`);
  fs.writeFileSync(scriptPath, "#!/usr/bin/env bash\nexit 0\n", "utf-8");
  fs.chmodSync(scriptPath, 0o755);
  return bundleDir;
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

describe("installHooks", () => {
  beforeEach(() => {
    // Prevent process.exit from actually killing the test runner.
    vi.spyOn(process, "exit").mockImplementation(
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      (_code?: string | number | null) => undefined as never,
    );

    // Silence stdout / stderr output from printResults.
    vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    vi.spyOn(process.stderr, "write").mockImplementation(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    for (const dir of tempDirs) {
      try {
        fs.rmSync(dir, { recursive: true, force: true });
      } catch {
        // best-effort
      }
    }
    tempDirs.length = 0;
  });

  // -----------------------------------------------------------------------
  // 1. Successful install of a hook directory
  // -----------------------------------------------------------------------
  it("copies a found hook into .claude/hooks/<name>/", async () => {
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    const installedDir = path.join(
      fakeCwd,
      ".claude",
      "hooks",
      "docs-that-work-gate",
    );
    expect(
      fs.existsSync(path.join(installedDir, "HOOK.md")),
    ).toBe(true);
    expect(
      fs.existsSync(path.join(installedDir, "docs-that-work-gate.sh")),
    ).toBe(true);

    // No failures -> process.exit not called.
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 2. .claude/hooks/ is created when absent
  // -----------------------------------------------------------------------
  it("creates .claude/hooks/ when it does not exist", async () => {
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    // Sanity: .claude/hooks does not exist yet.
    expect(fs.existsSync(path.join(fakeCwd, ".claude", "hooks"))).toBe(
      false,
    );

    await installHooks(["docs-that-work-gate"]);

    expect(fs.existsSync(path.join(fakeCwd, ".claude", "hooks"))).toBe(
      true,
    );
  });

  // -----------------------------------------------------------------------
  // 3. Silent skip on existing hook directory (success, exit not called with 1)
  // -----------------------------------------------------------------------
  it("silently skips an already-installed hook and leaves files untouched", async () => {
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Pre-create the target dir with a marker file that must survive.
    const fakeCwd = makeTempDir("cwd-");
    const existingDir = path.join(
      fakeCwd,
      ".claude",
      "hooks",
      "docs-that-work-gate",
    );
    fs.mkdirSync(existingDir, { recursive: true });
    const marker = path.join(existingDir, "HOOK.md");
    fs.writeFileSync(marker, "# Original", "utf-8");

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    // Pre-existing marker file must be untouched.
    expect(fs.readFileSync(marker, "utf-8")).toBe("# Original");

    // A silent skip is a success -> exit(1) must NOT be called.
    expect(process.exit).not.toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // 4. Not-found -> stderr message + exit(1)
  // -----------------------------------------------------------------------
  it("calls process.exit(1) when a requested hook is not in the bundle", async () => {
    // Empty bundle -> the hook does not exist.
    const bundleDir = makeTempDir("bundle-");
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["nonexistent"]);

    expect(process.stderr.write).toHaveBeenCalledWith(
      "Error: hook 'nonexistent' not found.\n",
    );
    expect(process.exit).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // 5. Exec-bit round-trip regression: staged 0o755 .sh keeps its exec bit
  //    through fs.cpSync into the installed location.
  // -----------------------------------------------------------------------
  it("preserves the executable bit on the installed entrypoint script", async () => {
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    const installedScript = path.join(
      fakeCwd,
      ".claude",
      "hooks",
      "docs-that-work-gate",
      "docs-that-work-gate.sh",
    );
    const mode = fs.statSync(installedScript).mode;
    expect(mode & 0o111).not.toBe(0);
  });

  // -----------------------------------------------------------------------
  // 6. Mixed results: one installed, one not-found -> exit(1) but the
  //    installed hook is still present.
  // -----------------------------------------------------------------------
  it("installs found hooks and still exits 1 when another is not found", async () => {
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate", "nonexistent"]);

    // The found hook is installed.
    expect(
      fs.existsSync(
        path.join(
          fakeCwd,
          ".claude",
          "hooks",
          "docs-that-work-gate",
          "HOOK.md",
        ),
      ),
    ).toBe(true);

    // The missing one triggers exit(1).
    expect(process.exit).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // Phase 2: settings injection
  // -----------------------------------------------------------------------

  /** Helper: read + parse the .claude/settings.json under a cwd. */
  function readSettings(cwd: string): Record<string, unknown> {
    const settingsPath = path.join(cwd, ".claude", "settings.json");
    return JSON.parse(fs.readFileSync(settingsPath, "utf-8"));
  }

  // 7. Fresh install creates settings.json with derived command + timeout.
  it("creates settings.json with the derived command and timeout on fresh install", async () => {
    const bundleDir = stageBundleWithFrontmatter(
      "docs-that-work-gate",
      "  - event: PreToolUse\n    matcher: Bash\n    timeout: 10\n",
    );
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    const settings = readSettings(fakeCwd);
    expect(settings).toEqual({
      hooks: {
        PreToolUse: [
          {
            matcher: "Bash",
            hooks: [
              {
                type: "command",
                command:
                  "$CLAUDE_PROJECT_DIR/.claude/hooks/docs-that-work-gate/docs-that-work-gate.sh",
                timeout: 10,
              },
            ],
          },
        ],
      },
    });
    expect(process.exit).not.toHaveBeenCalledWith(1);
  });

  // 8. Matcher-less event omits the matcher key.
  it("omits the matcher key for a matcher-less event", async () => {
    const bundleDir = stageBundleWithFrontmatter(
      "session-hook",
      "  - event: SessionStart\n    timeout: 5\n",
    );
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["session-hook"]);

    const settings = readSettings(fakeCwd);
    const grp = (settings.hooks as Record<string, unknown[]>)
      .SessionStart[0] as Record<string, unknown>;
    expect(grp).not.toHaveProperty("matcher");
    expect(grp.hooks).toEqual([
      {
        type: "command",
        command:
          "$CLAUDE_PROJECT_DIR/.claude/hooks/session-hook/session-hook.sh",
        timeout: 5,
      },
    ]);
  });

  // 9. Timeout omitted when unset.
  it("omits the timeout key when timeout is unset", async () => {
    const bundleDir = stageBundleWithFrontmatter(
      "no-timeout-hook",
      "  - event: PreToolUse\n    matcher: Edit\n",
    );
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["no-timeout-hook"]);

    const settings = readSettings(fakeCwd);
    const grp = (settings.hooks as Record<string, unknown[]>)
      .PreToolUse[0] as Record<string, { command: string }[]>;
    expect(grp.hooks[0]).not.toHaveProperty("timeout");
  });

  // 10. Unrelated existing settings keys and user hooks are preserved.
  it("preserves unrelated settings keys and existing user hooks", async () => {
    const bundleDir = stageBundleWithFrontmatter(
      "docs-that-work-gate",
      "  - event: PreToolUse\n    matcher: Edit|Write\n    timeout: 10\n",
    );
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    // Pre-seed settings with an unrelated key and a user-authored hook group.
    const settingsPath = path.join(fakeCwd, ".claude", "settings.json");
    fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
    const userGroup = {
      matcher: "Bash",
      hooks: [{ type: "command", command: "user-script.sh" }],
    };
    fs.writeFileSync(
      settingsPath,
      JSON.stringify(
        { $schema: "https://x/schema.json", hooks: { PreToolUse: [userGroup] } },
        null,
        2,
      ) + "\n",
      "utf-8",
    );

    await installHooks(["docs-that-work-gate"]);

    const settings = readSettings(fakeCwd);
    expect(settings.$schema).toBe("https://x/schema.json");
    const preToolUse = (settings.hooks as Record<string, unknown[]>)
      .PreToolUse;
    expect(preToolUse).toHaveLength(2);
    expect(preToolUse[0]).toEqual(userGroup);
  });

  // 11. Repair: pre-existing hook dir (skipped) with valid HOOK.md, settings
  //     missing the entry -> entry injected.
  it("repairs settings for a skipped hook whose entry is missing", async () => {
    const name = "docs-that-work-gate";
    const bundleDir = stageBundleWithFrontmatter(
      name,
      "  - event: PreToolUse\n    matcher: Edit|Write\n    timeout: 10\n",
    );
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    // Pre-create the hook dir with valid HOOK.md so Phase 1 skips it.
    const installedDir = path.join(fakeCwd, ".claude", "hooks", name);
    fs.mkdirSync(installedDir, { recursive: true });
    fs.writeFileSync(
      path.join(installedDir, "HOOK.md"),
      `---\nname: ${name}\ndescription: Test\nhooks:\n  - event: PreToolUse\n    matcher: Edit|Write\n    timeout: 10\n---\n\nBody.\n`,
      "utf-8",
    );

    // settings.json exists but has no entry for this hook.
    const settingsPath = path.join(fakeCwd, ".claude", "settings.json");
    fs.writeFileSync(settingsPath, JSON.stringify({}, null, 2) + "\n", "utf-8");

    await installHooks([name]);

    const settings = readSettings(fakeCwd);
    const preToolUse = (settings.hooks as Record<string, unknown[]>)
      .PreToolUse;
    expect(preToolUse).toHaveLength(1);
    expect(process.exit).not.toHaveBeenCalledWith(1);
  });

  // 12. Full idempotency: second run reports 0 added, file byte-identical.
  it("is fully idempotent: a second run leaves settings.json byte-identical", async () => {
    // installHooks deletes the bundle temp dir after each run, so stage a
    // fresh bundle for every download (mirrors the real downloadBundle).
    mockDownloadBundle.mockImplementation(async () =>
      stageBundleWithFrontmatter(
        "docs-that-work-gate",
        "  - event: PreToolUse\n    matcher: Edit|Write\n    timeout: 10\n",
      ),
    );

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    const settingsPath = path.join(fakeCwd, ".claude", "settings.json");
    const afterFirst = fs.readFileSync(settingsPath, "utf-8");

    // Second run: dir exists (skipped in Phase 1), settings already present.
    const stdoutSpy = process.stdout.write as unknown as ReturnType<
      typeof vi.fn
    >;
    stdoutSpy.mockClear();

    await installHooks(["docs-that-work-gate"]);

    const afterSecond = fs.readFileSync(settingsPath, "utf-8");
    expect(afterSecond).toBe(afterFirst);

    // The second run reports 0 entries added.
    expect(process.stdout.write).toHaveBeenCalledWith(
      "Settings: 0 entries added, 1 entries skipped (already present)\n",
    );
  });

  // 13. Unparseable HOOK.md frontmatter -> warning on stderr, exit 0, no
  //     settings.json created.
  it("warns and skips settings for a hook with unparseable frontmatter", async () => {
    // stageDocsGateBundle writes a HOOK.md with NO frontmatter.
    const bundleDir = stageDocsGateBundle();
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installHooks(["docs-that-work-gate"]);

    // Files installed, but no settings.json written.
    expect(
      fs.existsSync(
        path.join(fakeCwd, ".claude", "hooks", "docs-that-work-gate", "HOOK.md"),
      ),
    ).toBe(true);
    expect(
      fs.existsSync(path.join(fakeCwd, ".claude", "settings.json")),
    ).toBe(false);

    expect(process.stderr.write).toHaveBeenCalledWith(
      "Warning: could not parse hook 'docs-that-work-gate' metadata — settings not updated.\n",
    );
    expect(process.exit).not.toHaveBeenCalledWith(1);
  });
});
