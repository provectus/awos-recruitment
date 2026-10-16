import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, afterEach } from "vitest";

import { hashDirectory, type LockFile } from "../lock.js";
import type { RegistryIndex } from "../registry-index.js";
import { computeSkillStatuses } from "../status.js";

const tempDirs: string[] = [];

function makeCwd(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "status-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(() => {
  for (const dir of tempDirs) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  tempDirs.length = 0;
});

/** Writes a skill folder and returns its hash record. */
function writeSkill(cwd: string, name: string, files: Record<string, string>) {
  const dir = path.join(cwd, ".claude", "skills", name);
  for (const [rel, content] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.writeFileSync(path.join(dir, rel), content);
  }
  return hashDirectory(dir);
}

function emptyIndex(): RegistryIndex {
  return {
    version: 1,
    generated_at: "",
    skills: {},
    removed: { skills: {}, agents: {}, hooks: {}, mcp: {} },
  };
}

function lockWith(name: string, entry: { hash: string; files: Record<string, string> }): LockFile {
  return {
    version: 1,
    project_id: "pid",
    skills: { [name]: { server: "s", installed_at: "2026-10-16T00:00:00Z", ...entry } },
  };
}

describe("computeSkillStatuses", () => {
  it("reports up to date when lock, local files and registry agree", () => {
    const cwd = makeCwd();
    const local = writeSkill(cwd, "s", { "SKILL.md": "v1" });
    const index = emptyIndex();
    index.skills.s = local;

    const [status] = computeSkillStatuses(cwd, lockWith("s", local), index);

    expect(status.state).toBe("up-to-date");
    expect(status.adopt).toBe(false);
  });

  it("reports outdated when the registry hash differs and local files are untouched", () => {
    const cwd = makeCwd();
    const local = writeSkill(cwd, "s", { "SKILL.md": "v1" });
    const index = emptyIndex();
    index.skills.s = { hash: "newhash", files: { "SKILL.md": "x" } };

    const [status] = computeSkillStatuses(cwd, lockWith("s", local), index);

    expect(status.state).toBe("outdated");
    expect(status.registryChanged).toBe(true);
    expect(status.detail).toContain("installed 2026-10-16");
  });

  it("reports modified locally with the changed files, and notes a newer registry version", () => {
    const cwd = makeCwd();
    const original = writeSkill(cwd, "s", { "SKILL.md": "v1", "references/a.md": "a" });
    fs.writeFileSync(path.join(cwd, ".claude", "skills", "s", "SKILL.md"), "edited");
    const index = emptyIndex();
    index.skills.s = { hash: "newhash", files: {} };

    const [status] = computeSkillStatuses(cwd, lockWith("s", original), index);

    expect(status.state).toBe("modified-locally");
    expect(status.changedFiles).toEqual(["SKILL.md"]);
    expect(status.registryChanged).toBe(true);
    expect(status.detail).toBe("1 file changed; the registry has a newer version");
  });

  it("marks a copy without a lock entry as up to date and adoptable when it equals the registry", () => {
    const cwd = makeCwd();
    const local = writeSkill(cwd, "s", { "SKILL.md": "v1" });
    const index = emptyIndex();
    index.skills.s = local;

    const [status] = computeSkillStatuses(cwd, null, index);

    expect(status.state).toBe("up-to-date");
    expect(status.adopt).toBe(true);
  });

  it("reports no lock entry when a pre-lock copy differs from the registry", () => {
    const cwd = makeCwd();
    writeSkill(cwd, "s", { "SKILL.md": "old" });
    const index = emptyIndex();
    index.skills.s = { hash: "newhash", files: {} };

    const [status] = computeSkillStatuses(cwd, null, index);

    expect(status.state).toBe("no-lock-entry");
  });

  it("reports removed with the replacement from the tombstone", () => {
    const cwd = makeCwd();
    const local = writeSkill(cwd, "aws-docs", { "SKILL.md": "x" });
    const index = emptyIndex();
    index.removed.skills["aws-docs"] = {
      removed: "2026-03-23",
      reason: null,
      replacement: "aws-knowledge-mcp-server",
    };

    const [status] = computeSkillStatuses(cwd, lockWith("aws-docs", local), index);

    expect(status.state).toBe("removed");
    expect(status.replacement).toBe("aws-knowledge-mcp-server");
    expect(status.detail).toBe("removed 2026-03-23; replacement: aws-knowledge-mcp-server");
  });

  it("reports not in registry and missing locally", () => {
    const cwd = makeCwd();
    const local = writeSkill(cwd, "mine", { "SKILL.md": "x" });
    const lock = lockWith("mine", local);
    lock.skills.gone = { server: "s", installed_at: "t", hash: "h", files: {} };

    const statuses = computeSkillStatuses(cwd, lock, emptyIndex());

    expect(statuses.map((s) => [s.name, s.state])).toEqual([
      ["gone", "missing-locally"],
      ["mine", "not-in-registry"],
    ]);
  });
});
