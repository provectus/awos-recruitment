import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { hashDirectory, readLock, writeLock } from "../../lib/lock.js";
import type { RegistryIndex } from "../../lib/registry-index.js";
import { computeSkillStatuses } from "../../lib/status.js";
import { INCOMING_DIR_RELATIVE } from "../skill-diff.js";
import { skillMerged } from "../skill-merged.js";

const { mockFetchIndex } = vi.hoisted(() => ({
  mockFetchIndex: vi.fn<(url: string) => Promise<RegistryIndex>>(),
}));

vi.mock("../../lib/registry-index.js", () => ({ fetchRegistryIndex: mockFetchIndex }));

const tempDirs: string[] = [];

function makeCwd(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "merged-"));
  tempDirs.push(dir);
  return dir;
}

function writeSkill(dir: string, content: string): string {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "SKILL.md"), content);
  return dir;
}

describe("skillMerged", () => {
  beforeEach(() => {
    vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    process.env.AWOS_SERVER_URL = "http://127.0.0.1:8000";
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.restoreAllMocks();
    for (const dir of tempDirs) fs.rmSync(dir, { recursive: true, force: true });
    tempDirs.length = 0;
  });

  it("records the registry version as the base, keeps the edited files and cleans up", async () => {
    const cwd = makeCwd();
    const local = writeSkill(path.join(cwd, ".claude", "skills", "s"), "v2 + my note\n");
    const incoming = writeSkill(path.join(cwd, INCOMING_DIR_RELATIVE, "s"), "v2\n");
    const v2 = hashDirectory(incoming);
    writeLock(cwd, {
      version: 1,
      project_id: "pid",
      skills: { s: { server: "x", installed_at: "t", hash: "v1hash", files: {}, skip: { hash: "v2hash", at: "t" } } },
    });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    const registry: RegistryIndex = {
      version: 1,
      generated_at: "",
      skills: { s: { ...v2, commit: "abc1234", released: "2026-10-21" } },
      removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
    };
    mockFetchIndex.mockResolvedValue(registry);

    await skillMerged(["s"]);

    const entry = readLock(cwd)?.skills.s;
    expect(entry?.hash).toBe(v2.hash);
    expect(entry?.commit).toBe("abc1234");
    expect(entry?.skip).toBeUndefined();
    expect(fs.readFileSync(path.join(local, "SKILL.md"), "utf-8")).toBe("v2 + my note\n");
    expect(fs.existsSync(path.join(cwd, ".claude", "awos-recruitment"))).toBe(false);
    expect(process.stdout.write).toHaveBeenCalledWith(
      "Recorded 's' as merged with the registry version (your own edits kept).\n",
    );

    // status now: current registry version plus local edits, not outdated.
    const [status] = computeSkillStatuses(cwd, readLock(cwd), registry);
    expect(status.state).toBe("modified-locally");
    expect(status.registryChanged).toBe(false);
  });

  it("refuses when skill diff --keep was not run", async () => {
    const cwd = makeCwd();
    writeSkill(path.join(cwd, ".claude", "skills", "s"), "x\n");
    vi.spyOn(process, "cwd").mockReturnValue(cwd);

    await expect(skillMerged(["s"])).rejects.toThrow("Run 'skill diff --keep s' first");
  });
});
