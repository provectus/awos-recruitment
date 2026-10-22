import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

import { hashDirectory, readLock, writeLock } from "../../lib/lock.js";
import type { RegistryHistory, RegistryIndex } from "../../lib/registry-index.js";
import { backupRoot } from "../../lib/cache-dir.js";
import { skillUpdate } from "../skill-update.js";

const { mockDownloadBundle, mockFetchIndex, mockFetchHistory, mockSendTelemetry } = vi.hoisted(() => ({
  mockDownloadBundle: vi.fn<(url: string, names: string[]) => Promise<string>>(),
  mockFetchIndex: vi.fn<(url: string) => Promise<RegistryIndex>>(),
  mockFetchHistory: vi.fn<(url: string) => Promise<RegistryHistory>>(),
  mockSendTelemetry: vi.fn(async () => undefined),
}));

vi.mock("../../lib/download.js", () => ({ downloadBundle: mockDownloadBundle }));
vi.mock("../../lib/registry-index.js", () => ({
  fetchRegistryIndex: mockFetchIndex,
  fetchRegistryHistory: mockFetchHistory,
}));
vi.mock("../../lib/telemetry.js", () => ({ sendTelemetry: mockSendTelemetry }));

const tempDirs: string[] = [];

function makeTempDir(prefix: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  tempDirs.push(dir);
  return dir;
}

function writeSkill(root: string, name: string, content: string): string {
  const dir = path.join(root, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "SKILL.md"), content);
  return dir;
}

/** A project with one installed, locked skill at version "v1" and a registry at "v2". */
function setupOutdatedProject(): { cwd: string; index: RegistryIndex; bundle: string } {
  const cwd = makeTempDir("cwd-");
  const skillDir = writeSkill(path.join(cwd, ".claude", "skills"), "s", "v1");
  const local = hashDirectory(skillDir);
  writeLock(cwd, {
    version: 1,
    project_id: "b4252689-6fa4-4675-b630-ecb331160d84",
    skills: { s: { server: "x", installed_at: "2026-10-01T00:00:00Z", ...local } },
  });

  const bundle = makeTempDir("bundle-");
  const newDir = writeSkill(bundle, "s", "v2");
  const index: RegistryIndex = {
    version: 1,
    generated_at: "",
    skills: { s: hashDirectory(newDir) },
    removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
  };
  vi.spyOn(process, "cwd").mockReturnValue(cwd);
  mockFetchIndex.mockResolvedValue(index);
  mockDownloadBundle.mockResolvedValue(bundle);
  return { cwd, index, bundle };
}

describe("skillUpdate", () => {
  beforeEach(() => {
    vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    process.env.AWOS_SERVER_URL = "http://127.0.0.1:8000";
    process.env.XDG_CACHE_HOME = makeTempDir("cache-");
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.restoreAllMocks();
    for (const dir of tempDirs) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
    tempDirs.length = 0;
  });

  it("replaces an outdated skill and updates the lock entry", async () => {
    const { cwd, index } = setupOutdatedProject();

    await skillUpdate([]);

    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v2");
    expect(readLock(cwd)?.skills.s.hash).toBe(index.skills.s.hash);
    expect(process.stdout.write).toHaveBeenCalledWith("Updated 's'.\n");
    expect(mockSendTelemetry).toHaveBeenCalledWith(
      "http://127.0.0.1:8000",
      "b4252689-6fa4-4675-b630-ecb331160d84",
      expect.arrayContaining([
        expect.objectContaining({ event: "capability_updated", capability_name: "s" }),
      ]),
    );
  });

  it("--dry-run prints the plan and changes nothing", async () => {
    const { cwd } = setupOutdatedProject();
    const before = readLock(cwd);

    await skillUpdate([], { dryRun: true });

    expect(mockDownloadBundle).not.toHaveBeenCalled();
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v1");
    expect(readLock(cwd)).toEqual(before);
    expect(process.stdout.write).toHaveBeenCalledWith(
      expect.stringContaining("would update  registry has a newer version"),
    );
  });

  it("keeps a locally modified skill without a terminal and says so", async () => {
    const { cwd } = setupOutdatedProject();
    fs.writeFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "my edit");
    Object.defineProperty(process.stdin, "isTTY", { value: false, configurable: true });

    await skillUpdate([]);

    expect(mockDownloadBundle).not.toHaveBeenCalled();
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("my edit");
    expect(process.stderr.write).toHaveBeenCalledWith(
      expect.stringContaining("Kept local copy of 's' (1 changed file(s)); the registry has a newer version but there is no terminal to ask"),
    );
  });

  it("--overwrite replaces a locally modified skill without a backup", async () => {
    const { cwd } = setupOutdatedProject();
    fs.writeFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "my edit");

    await skillUpdate([], { overwrite: true });

    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v2");
    expect(fs.existsSync(backupRoot(cwd))).toBe(false);
  });

  it("--no-overwrite keeps a locally modified skill", async () => {
    const { cwd } = setupOutdatedProject();
    fs.writeFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "my edit");

    await skillUpdate([], { noOverwrite: true });

    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("my edit");
    expect(process.stderr.write).toHaveBeenCalledWith(expect.stringContaining("Kept local copy of 's'"));
  });

  it("records a pre-lock copy that already equals the registry without downloading", async () => {
    const cwd = makeTempDir("cwd-");
    const dir = writeSkill(path.join(cwd, ".claude", "skills"), "s", "v2");
    const index: RegistryIndex = {
      version: 1,
      generated_at: "",
      skills: { s: hashDirectory(dir) },
      removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
    };
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(index);

    await skillUpdate([]);

    expect(mockDownloadBundle).not.toHaveBeenCalled();
    expect(readLock(cwd)?.skills.s.hash).toBe(index.skills.s.hash);
    expect(process.stdout.write).toHaveBeenCalledWith("Recorded 's' (already current).\n");
  });

  it("replaces a pre-lock copy that matches a historical version without asking", async () => {
    const cwd = makeTempDir("cwd-");
    const oldDir = writeSkill(path.join(cwd, ".claude", "skills"), "s", "v1");
    const oldHash = hashDirectory(oldDir).hash;
    const bundle = makeTempDir("bundle-");
    const newDir = writeSkill(bundle, "s", "v2");
    const index: RegistryIndex = {
      version: 1,
      generated_at: "",
      skills: { s: hashDirectory(newDir) },
      removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
    };
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    mockFetchIndex.mockResolvedValue(index);
    mockFetchHistory.mockResolvedValue({
      version: 1,
      generated_at: "x",
      skills: {
        s: [
          { hash: oldHash, from: "2026-03-11", to: "2026-09-24", commit: "a" },
          { hash: index.skills.s.hash, from: "2026-09-24", to: null, commit: "b" },
        ],
      },
    });
    mockDownloadBundle.mockResolvedValue(bundle);
    Object.defineProperty(process.stdin, "isTTY", { value: false, configurable: true });

    await skillUpdate([]);

    expect(mockFetchHistory).toHaveBeenCalledTimes(1);
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v2");
    expect(readLock(cwd)?.skills.s.hash).toBe(index.skills.s.hash);
  });

  it("does not download the history when every skill has a lock entry", async () => {
    setupOutdatedProject();

    await skillUpdate([], { dryRun: true });

    expect(mockFetchHistory).not.toHaveBeenCalled();
  });

  it("keeps a skipped skill, and updates it when it is named", async () => {
    const { cwd, index } = setupOutdatedProject();
    const lock = readLock(cwd)!;
    lock.skills.s.skip = { hash: index.skills.s.hash, at: "2026-10-20T00:00:00Z" };
    writeLock(cwd, lock);

    await skillUpdate([]);
    expect(mockDownloadBundle).not.toHaveBeenCalled();
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v1");

    await skillUpdate(["s"]);
    expect(fs.readFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "utf-8")).toBe("v2");
    expect(readLock(cwd)?.skills.s.skip).toBeUndefined();
  });

  it("rejects names that are not installed", async () => {
    setupOutdatedProject();

    await expect(skillUpdate(["nope"])).rejects.toThrow("not installed: nope");
  });
});
