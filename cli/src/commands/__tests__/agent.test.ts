import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { installAgents } from "../agent.js";

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

/** Sample agent markdown content (with skills). */
const agentMarkdown = `---
name: code-reviewer
description: Reviews code for best practices
model: claude-sonnet
skills:
  - typescript
---

# Code Reviewer

You are a code review agent.
`;

/** Agent markdown that references two skills. */
const agentWithTwoSkills = `---
name: full-stack-dev
description: Full stack development agent
skills:
  - skill-a
  - skill-b
---

# Full Stack Dev

You are a full stack development agent.
`;

/** Agent markdown with no skills field. */
const agentNoSkills = `---
name: simple-agent
description: An agent with no skills
---

# Simple Agent

You are a simple agent.
`;

/**
 * Helper: create a skill directory inside a temp dir,
 * simulating an extracted skill bundle entry.
 */
function createSkillInDir(dir: string, skillName: string): void {
  const skillDir = path.join(dir, skillName);
  fs.mkdirSync(skillDir, { recursive: true });
  fs.writeFileSync(
    path.join(skillDir, "SKILL.md"),
    `# ${skillName}`,
    "utf-8",
  );
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

describe("installAgents", () => {
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
  it("copies a found agent .md file into .claude/agents/<name>.md", async () => {
    // Prepare a temp dir simulating the extracted bundle.
    const bundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "code-reviewer.md"),
      agentMarkdown,
      "utf-8",
    );

    // The agent frontmatter references the "typescript" skill, so
    // Phase 2 will attempt a second downloadBundle call for skills.
    const skillBundleDir = makeTempDir("skill-bundle-");
    createSkillInDir(skillBundleDir, "typescript");

    mockDownloadBundle
      .mockResolvedValueOnce(bundleDir)
      .mockResolvedValueOnce(skillBundleDir);

    // Prepare a fake cwd.
    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["code-reviewer"]);

    // The agent file should have been copied into the expected location.
    const installed = path.join(
      fakeCwd,
      ".claude",
      "agents",
      "code-reviewer.md",
    );
    expect(fs.existsSync(installed)).toBe(true);
    expect(fs.readFileSync(installed, "utf-8")).toBe(agentMarkdown);

    // process.exit should NOT have been called (no failures).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 2. Skip existing
  // -----------------------------------------------------------------------
  it("skips install when .claude/agents/<name>.md already exists (no error exit)", async () => {
    // Prepare a bundle with an agent.
    const bundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "code-reviewer.md"),
      agentMarkdown,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Pre-create the agent file in the fake cwd to trigger skip.
    const fakeCwd = makeTempDir("agent-cwd-");
    const existingDir = path.join(fakeCwd, ".claude", "agents");
    fs.mkdirSync(existingDir, { recursive: true });
    fs.writeFileSync(
      path.join(existingDir, "code-reviewer.md"),
      "# Original Agent",
      "utf-8",
    );

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["code-reviewer"]);

    // Should NOT exit with failure — skips are informational, not errors.
    expect(process.exit).not.toHaveBeenCalled();

    // Original file should be untouched.
    expect(
      fs.readFileSync(
        path.join(existingDir, "code-reviewer.md"),
        "utf-8",
      ),
    ).toBe("# Original Agent");
  });

  // -----------------------------------------------------------------------
  // 3. Not found
  // -----------------------------------------------------------------------
  it("calls process.exit(1) when a requested agent is not in the bundle", async () => {
    // Return an empty bundle directory -- the agent doesn't exist.
    const bundleDir = makeTempDir("agent-bundle-");
    mockDownloadBundle.mockResolvedValue(bundleDir);

    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["nonexistent"]);

    expect(process.exit).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // 4. Mixed results
  // -----------------------------------------------------------------------
  it("handles mixed results: installed, skipped, and not-found", async () => {
    // Prepare a bundle with two agents (but not "missing-agent").
    const bundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "new-agent.md"),
      "# New Agent",
      "utf-8",
    );
    fs.writeFileSync(
      path.join(bundleDir, "existing-agent.md"),
      "# Existing Agent (new version)",
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Pre-create one agent to trigger skip.
    const fakeCwd = makeTempDir("agent-cwd-");
    const agentsDir = path.join(fakeCwd, ".claude", "agents");
    fs.mkdirSync(agentsDir, { recursive: true });
    fs.writeFileSync(
      path.join(agentsDir, "existing-agent.md"),
      "# Existing Agent (original)",
      "utf-8",
    );

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["new-agent", "existing-agent", "missing-agent"]);

    // Should exit with failure because of the not-found agent.
    expect(process.exit).toHaveBeenCalledWith(1);

    // New agent should be installed.
    expect(
      fs.readFileSync(
        path.join(agentsDir, "new-agent.md"),
        "utf-8",
      ),
    ).toBe("# New Agent");

    // Existing agent should be untouched.
    expect(
      fs.readFileSync(
        path.join(agentsDir, "existing-agent.md"),
        "utf-8",
      ),
    ).toBe("# Existing Agent (original)");
  });

  // -----------------------------------------------------------------------
  // 5. Directory creation
  // -----------------------------------------------------------------------
  it("creates .claude/agents/ directory if it does not exist", async () => {
    // Prepare a bundle with an agent.
    const bundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(bundleDir, "my-agent.md"),
      "# My Agent",
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValue(bundleDir);

    // Fake cwd with NO .claude directory at all.
    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["my-agent"]);

    // The .claude/agents/ directory should have been created.
    const agentsDir = path.join(fakeCwd, ".claude", "agents");
    expect(fs.existsSync(agentsDir)).toBe(true);
    expect(fs.statSync(agentsDir).isDirectory()).toBe(true);

    // The file should be there.
    expect(
      fs.readFileSync(
        path.join(agentsDir, "my-agent.md"),
        "utf-8",
      ),
    ).toBe("# My Agent");
  });

  // =======================================================================
  // Phase 2: Auto-install referenced skills
  // =======================================================================

  // -----------------------------------------------------------------------
  // 6. Skills auto-installed from frontmatter
  // -----------------------------------------------------------------------
  it("auto-installs skills referenced in agent frontmatter", async () => {
    // First call: agent bundle with an agent referencing two skills.
    const agentBundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(agentBundleDir, "full-stack-dev.md"),
      agentWithTwoSkills,
      "utf-8",
    );

    // Second call: skill bundle with both skills.
    const skillBundleDir = makeTempDir("skill-bundle-");
    createSkillInDir(skillBundleDir, "skill-a");
    createSkillInDir(skillBundleDir, "skill-b");

    mockDownloadBundle
      .mockResolvedValueOnce(agentBundleDir)
      .mockResolvedValueOnce(skillBundleDir);

    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["full-stack-dev"]);

    // Agent should be installed.
    const agentFile = path.join(
      fakeCwd,
      ".claude",
      "agents",
      "full-stack-dev.md",
    );
    expect(fs.existsSync(agentFile)).toBe(true);

    // Both skills should be installed.
    const skillAFile = path.join(
      fakeCwd,
      ".claude",
      "skills",
      "skill-a",
      "SKILL.md",
    );
    const skillBFile = path.join(
      fakeCwd,
      ".claude",
      "skills",
      "skill-b",
      "SKILL.md",
    );
    expect(fs.existsSync(skillAFile)).toBe(true);
    expect(fs.existsSync(skillBFile)).toBe(true);

    // downloadBundle should have been called twice: once for agents, once for skills.
    expect(mockDownloadBundle).toHaveBeenCalledTimes(2);
    expect(mockDownloadBundle).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/bundle/agents"),
      ["full-stack-dev"],
    );
    expect(mockDownloadBundle).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/bundle/skills"),
      expect.arrayContaining(["skill-a", "skill-b"]),
    );

    // Skills section header should be printed.
    expect(process.stdout.write).toHaveBeenCalledWith(
      "\nSkills (auto-installed):\n",
    );

    // No exit(1) -- everything succeeded.
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 7. Existing skills are skipped
  // -----------------------------------------------------------------------
  it("skips skills that already exist locally", async () => {
    // Agent bundle with an agent referencing skill-a.
    const agentBundleDir = makeTempDir("agent-bundle-");
    const agentWithOneSkill = `---
name: my-agent
description: A test agent
skills:
  - skill-a
---

# My Agent
`;
    fs.writeFileSync(
      path.join(agentBundleDir, "my-agent.md"),
      agentWithOneSkill,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValueOnce(agentBundleDir);

    // Pre-create skill-a in the fake cwd.
    const fakeCwd = makeTempDir("agent-cwd-");
    const existingSkillDir = path.join(
      fakeCwd,
      ".claude",
      "skills",
      "skill-a",
    );
    fs.mkdirSync(existingSkillDir, { recursive: true });
    fs.writeFileSync(
      path.join(existingSkillDir, "SKILL.md"),
      "# Existing skill-a",
      "utf-8",
    );

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["my-agent"]);

    // downloadBundle should have been called only once (for agents).
    // No second call for skills since all are already present.
    expect(mockDownloadBundle).toHaveBeenCalledTimes(1);

    // Existing skill should be untouched.
    expect(
      fs.readFileSync(
        path.join(existingSkillDir, "SKILL.md"),
        "utf-8",
      ),
    ).toBe("# Existing skill-a");

    // Skills section should still be printed (with skipped info).
    expect(process.stdout.write).toHaveBeenCalledWith(
      "\nSkills (auto-installed):\n",
    );

    // No exit(1).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 8. All skills already present -- no HTTP call for skills
  // -----------------------------------------------------------------------
  it("does not download skills when all referenced skills already exist", async () => {
    // Agent referencing skill-a and skill-b, both already present.
    const agentBundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(agentBundleDir, "full-stack-dev.md"),
      agentWithTwoSkills,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValueOnce(agentBundleDir);

    const fakeCwd = makeTempDir("agent-cwd-");
    // Pre-create both skills.
    for (const skill of ["skill-a", "skill-b"]) {
      const skillDir = path.join(
        fakeCwd,
        ".claude",
        "skills",
        skill,
      );
      fs.mkdirSync(skillDir, { recursive: true });
      fs.writeFileSync(
        path.join(skillDir, "SKILL.md"),
        `# ${skill}`,
        "utf-8",
      );
    }

    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["full-stack-dev"]);

    // Only one downloadBundle call (for agents), none for skills.
    expect(mockDownloadBundle).toHaveBeenCalledTimes(1);

    // No exit(1).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 9. No skills referenced -- no skills section in output
  // -----------------------------------------------------------------------
  it("does not print skills section when agent has no skills field", async () => {
    const agentBundleDir = makeTempDir("agent-bundle-");
    fs.writeFileSync(
      path.join(agentBundleDir, "simple-agent.md"),
      agentNoSkills,
      "utf-8",
    );

    mockDownloadBundle.mockResolvedValueOnce(agentBundleDir);

    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["simple-agent"]);

    // Only one downloadBundle call (for agents).
    expect(mockDownloadBundle).toHaveBeenCalledTimes(1);

    // Skills header should NOT be printed.
    expect(process.stdout.write).not.toHaveBeenCalledWith(
      "\nSkills (auto-installed):\n",
    );

    // No exit(1).
    expect(process.exit).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 10. Referenced skill not found in registry
  // -----------------------------------------------------------------------
  it("reports not-found and exits 1 when a referenced skill is missing from the registry", async () => {
    // Agent references skill-a, but the skill bundle doesn't contain it.
    const agentBundleDir = makeTempDir("agent-bundle-");
    const agentWithOneSkill = `---
name: my-agent
description: A test agent
skills:
  - skill-a
---

# My Agent
`;
    fs.writeFileSync(
      path.join(agentBundleDir, "my-agent.md"),
      agentWithOneSkill,
      "utf-8",
    );

    // Empty skill bundle -- skill-a is not there.
    const skillBundleDir = makeTempDir("skill-bundle-");

    mockDownloadBundle
      .mockResolvedValueOnce(agentBundleDir)
      .mockResolvedValueOnce(skillBundleDir);

    const fakeCwd = makeTempDir("agent-cwd-");
    vi.spyOn(process, "cwd").mockReturnValue(fakeCwd);

    await installAgents(["my-agent"]);

    // Should exit(1) because a referenced skill was not found.
    expect(process.exit).toHaveBeenCalledWith(1);

    // downloadBundle should have been called twice.
    expect(mockDownloadBundle).toHaveBeenCalledTimes(2);
  });
});
