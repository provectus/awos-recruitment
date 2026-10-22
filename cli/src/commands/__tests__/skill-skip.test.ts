import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { hashDirectory, readLock, writeLock } from "../../lib/lock.js";
import type { RegistryIndex } from "../../lib/registry-index.js";
import { skipSkills } from "../skill-skip.js";

const { mockFetchIndex } = vi.hoisted(() => ({
  mockFetchIndex: vi.fn<(url: string) => Promise<RegistryIndex>>(),
}));

vi.mock("../../lib/registry-index.js", () => ({ fetchRegistryIndex: mockFetchIndex }));

const tempDirs: string[] = [];

function makeCwd(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "skip-"));
  tempDirs.push(dir);
  return dir;
}

function writeSkill(cwd: string, name: string, content: string): string {
  const dir = path.join(cwd, ".claude", "skills", name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "SKILL.md"), content);
  return dir;
}

function indexWith(name: string, hash: string): RegistryIndex {
  return {
    version: 1,
    generated_at: "",
    skills: { [name]: { hash, files: {} } },
    removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
  };
}

describe("skipSkills", () => {
  beforeEach(() => {
    vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    process.env.AWOS_SERVER_URL = "http://127.0.0.1:8000";
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.restoreAllMocks();
    for (const dir of tempDirs) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
    tempDirs.length = 0;
  });

  it("records the registry version to skip in an existing lock entry", async () => {
    const cwd = makeCwd();
    const local = hashDirectory(writeSkill(cwd, "s", "v1"));
    writeLock(cwd, {
      version: 1,
      project_id: "pid",
      skills: { s: { server: "x", installed_at: "2026-10-01T00:00:00Z", ...local } },
    });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(indexWith("s", "v2hash"));

    await skipSkills(["s"]);

    const entry = readLock(cwd)?.skills.s;
    expect(entry?.skip?.hash).toBe("v2hash");
    expect(entry?.installed_at).toBe("2026-10-01T00:00:00Z");
    expect(process.stdout.write).toHaveBeenCalledWith(
      "Skipping 's' until the registry publishes a newer version.\n",
    );
  });

  it("creates a lock entry for a copy installed before the lock file", async () => {
    const cwd = makeCwd();
    const local = hashDirectory(writeSkill(cwd, "s", "march"));
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(indexWith("s", "v2hash"));

    await skipSkills(["s"]);

    const entry = readLock(cwd)?.skills.s;
    expect(entry?.hash).toBe(local.hash);
    expect(entry?.skip?.hash).toBe("v2hash");
  });

  it("does nothing for a skill that is already up to date", async () => {
    const cwd = makeCwd();
    const local = hashDirectory(writeSkill(cwd, "s", "v2"));
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(indexWith("s", local.hash));

    await skipSkills(["s"]);

    expect(readLock(cwd)).toBeNull();
    expect(process.stdout.write).toHaveBeenCalledWith("'s' is already up to date; nothing to skip.\n");
  });

  it("refuses skills that are not installed or not in the registry", async () => {
    const cwd = makeCwd();
    writeSkill(cwd, "mine", "x");
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(indexWith("s", "h"));

    await expect(skipSkills(["nope"])).rejects.toThrow("is not installed");
    await expect(skipSkills(["mine"])).rejects.toThrow("is not in the registry");
  });
});
