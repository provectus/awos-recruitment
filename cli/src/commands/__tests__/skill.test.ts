import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { installSkills } from "../skill.js";

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

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

describe("installSkills", () => {
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
  // 1. Successful install
  // -----------------------------------------------------------------------
  it("copies a found skill into .claude/skills/<name>/", async () => {
    // Prepare a temp dir simulating the extracted bundle.
    const bundleDir = makeTempDir("bundle-");
    const skillSrc = path.join(bundleDir, "my-skill");
    fs.mkdirSync(skillSrc, { recursive: true });
    fs.writeFileSync(
      path.join(skillSrc, "SKILL.md"),
      "# My Skill",
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Prepare a fake cwd.
    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installSkills(["my-skill"]);

    // The skill should have been copied into the expected location.
    const installed = path.join(
      fakeCwd,
      ".claude",
      "skills",
      "my-skill",
      "SKILL.md",
    );
    expect(fs.existsSync(installed)).toBe(true);
    expect(fs.readFileSync(installed, "utf-8")).toBe("# My Skill");

    // process.exit should NOT have been called (no failures).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 2. Not-found
  // -----------------------------------------------------------------------
  it("calls process.exit(1) when a requested skill is not in the bundle", async () => {
    // Return an empty bundle directory -- the skill doesn't exist.
    const bundleDir = makeTempDir("bundle-");
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installSkills(["nonexistent"]);

    expect(process.exit).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // 3. Conflict detection
  // -----------------------------------------------------------------------
  it("calls process.exit(1) and leaves existing files untouched on conflict", async () => {
    // Prepare a bundle with a skill.
    const bundleDir = makeTempDir("bundle-");
    const skillSrc = path.join(bundleDir, "existing-skill");
    fs.mkdirSync(skillSrc, { recursive: true });
    fs.writeFileSync(
      path.join(skillSrc, "SKILL.md"),
      "# New Version",
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Pre-create the skill in the fake cwd to trigger a conflict.
    const fakeCwd = makeTempDir("cwd-");
    const existingDir = path.join(
      fakeCwd,
      ".claude",
      "skills",
      "existing-skill",
    );
    fs.mkdirSync(existingDir, { recursive: true });
    fs.writeFileSync(
      path.join(existingDir, "SKILL.md"),
      "# Original",
      "utf-8",
    );

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installSkills(["existing-skill"]);

    // Should exit with failure.
    expect(process.exit).toHaveBeenCalledWith(1);

    // Original file should be untouched.
    expect(
      fs.readFileSync(
        path.join(existingDir, "SKILL.md"),
        "utf-8",
      ),
    ).toBe("# Original");
  });
});
