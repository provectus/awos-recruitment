import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { hashDirectory } from "../../lib/lock.js";
import type { RegistryIndex } from "../../lib/registry-index.js";
import { backupRoot, incomingRoot } from "../../lib/cache-dir.js";
import { formatSkillDiff, skillDiff } from "../skill-diff.js";

const { mockDownloadBundle, mockFetchIndex } = vi.hoisted(() => ({
  mockDownloadBundle: vi.fn<(url: string, names: string[]) => Promise<string>>(),
  mockFetchIndex: vi.fn<(url: string) => Promise<RegistryIndex>>(),
}));

vi.mock("../../lib/download.js", () => ({ downloadBundle: mockDownloadBundle }));
vi.mock("../../lib/registry-index.js", () => ({ fetchRegistryIndex: mockFetchIndex }));

const tempDirs: string[] = [];

function makeTempDir(prefix: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tempDirs.push(dir);
  return dir;
}

function writeFiles(dir: string, files: Record<string, string>): string {
  for (const [rel, content] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.writeFileSync(path.join(dir, rel), content);
  }
  return dir;
}

function index(skills: RegistryIndex["skills"]): RegistryIndex {
  return { version: 1, generated_at: "", skills, removed: { skills: {}, agents: {}, hooks: {}, mcp: {} } };
}

describe("formatSkillDiff", () => {
  afterEach(() => {
    for (const dir of tempDirs) fs.rmSync(dir, { recursive: true, force: true });
    tempDirs.length = 0;
  });

  it("lists changed, added and removed files with the line diff", () => {
    const local = writeFiles(makeTempDir("l-"), { "SKILL.md": "a\nold\n", "notes.md": "mine\n" });
    const reg = writeFiles(makeTempDir("r-"), { "SKILL.md": "a\nnew\n", "references/x.md": "x\n" });

    const out = formatSkillDiff("s", local, reg, 100);

    expect(out).toContain("=== s: 1 changed, 1 added, 1 removed");
    expect(out).toContain("--- SKILL.md (yours) / +++ SKILL.md (registry)");
    expect(out).toContain("-old");
    expect(out).toContain("+new");
    expect(out).toContain("+++ references/x.md (new file");
    expect(out).toContain("--- notes.md (removed by the update; it is in your copy only)");
  });

  it("cuts long output and says how much is left", () => {
    const local = writeFiles(makeTempDir("l-"), { "SKILL.md": "" });
    const reg = writeFiles(makeTempDir("r-"), { "SKILL.md": Array.from({ length: 50 }, (_, i) => `line ${i}`).join("\n") });

    const out = formatSkillDiff("s", local, reg, 10);

    expect(out).toMatch(/… \d+ more lines not shown/);
  });
});

describe("skillDiff", () => {
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

  it("without names diffs only the skills that differ from the registry", async () => {
    const cwd = makeTempDir("cwd-");
    const same = writeFiles(path.join(cwd, ".claude", "skills", "same"), { "SKILL.md": "v2\n" });
    writeFiles(path.join(cwd, ".claude", "skills", "old"), { "SKILL.md": "v1\n" });
    writeFiles(path.join(cwd, ".claude", "skills", "mine"), { "SKILL.md": "x\n" });
    const bundle = writeFiles(makeTempDir("b-"), { "old/SKILL.md": "v2\n" });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(
      index({ same: hashDirectory(same), old: { hash: "other", files: {} } }),
    );
    mockDownloadBundle.mockResolvedValue(bundle);

    await skillDiff([]);

    expect(mockDownloadBundle).toHaveBeenCalledWith("http://127.0.0.1:8000/bundle/skills", ["old"]);
    expect(process.stdout.write).toHaveBeenCalledWith(expect.stringContaining("=== old: 1 changed"));
  });

  it("says so when everything matches", async () => {
    const cwd = makeTempDir("cwd-");
    const same = writeFiles(path.join(cwd, ".claude", "skills", "same"), { "SKILL.md": "v2\n" });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(index({ same: hashDirectory(same) }));

    await skillDiff([]);

    expect(mockDownloadBundle).not.toHaveBeenCalled();
    expect(process.stdout.write).toHaveBeenCalledWith("All installed registry skills match the registry.\n");
  });

  it("refuses names that are not installed or not in the registry", async () => {
    const cwd = makeTempDir("cwd-");
    writeFiles(path.join(cwd, ".claude", "skills", "mine"), { "SKILL.md": "x\n" });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(index({}));

    await expect(skillDiff(["nope"])).rejects.toThrow("is not installed");
    await expect(skillDiff(["mine"])).rejects.toThrow("is not in the registry");
  });

  it("--keep saves the registry version for a merge and backs up the copy, outside the project", async () => {
    process.env.XDG_CACHE_HOME = makeTempDir("cache-");
    const cwd = makeTempDir("cwd-");
    writeFiles(path.join(cwd, ".claude", "skills", "old"), { "SKILL.md": "v1 + mine\n" });
    const bundle = writeFiles(makeTempDir("b-"), { "old/SKILL.md": "v2\n" });
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(index({ old: { hash: "other", files: {} } }));
    mockDownloadBundle.mockResolvedValue(bundle);

    await skillDiff(["old"], { keep: true });

    expect(fs.readFileSync(path.join(incomingRoot(cwd), "old", "SKILL.md"), "utf-8")).toBe("v2\n");
    expect(incomingRoot(cwd).startsWith(process.env.XDG_CACHE_HOME!)).toBe(true);
    const backups = fs.readdirSync(path.join(backupRoot(cwd), "old"));
    expect(backups).toHaveLength(1);
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "old", "SKILL.md"), "utf-8")).toBe("v1 + mine\n");
    // Nothing new inside the project apart from the skill itself.
    expect(fs.readdirSync(path.join(cwd, ".claude"))).toEqual(["skills"]);
  });
});
