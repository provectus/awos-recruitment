import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { describe, it, expect, afterEach } from "vitest";

import { CliError } from "../errors.js";
import {
  LOCK_FILE_RELATIVE,
  hashDirectory,
  readLock,
  recordSkillInstalls,
  writeLock,
} from "../lock.js";

const tempDirs: string[] = [];

function makeTempDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "lock-"));
  tempDirs.push(dir);
  return dir;
}

function sha256(content: string): string {
  return createHash("sha256").update(content).digest("hex");
}

afterEach(() => {
  for (const dir of tempDirs) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  tempDirs.length = 0;
});

describe("hashDirectory", () => {
  it("hashes every file with POSIX relative paths and folds them in sorted order", () => {
    const dir = makeTempDir();
    fs.mkdirSync(path.join(dir, "references"));
    fs.writeFileSync(path.join(dir, "references", "a.md"), "alpha");
    fs.writeFileSync(path.join(dir, "SKILL.md"), "skill");

    const result = hashDirectory(dir);

    expect(result.files).toEqual({
      "SKILL.md": sha256("skill"),
      "references/a.md": sha256("alpha"),
    });
    // Same scheme as server/src/awos_recruitment_mcp/registry_index.py.
    const expected = sha256(
      `SKILL.md\0${sha256("skill")}\nreferences/a.md\0${sha256("alpha")}\n`,
    );
    expect(result.hash).toBe(expected);
  });
});

describe("readLock / writeLock", () => {
  it("returns null when there is no lock file", () => {
    expect(readLock(makeTempDir())).toBeNull();
  });

  it("round-trips the lock file", () => {
    const cwd = makeTempDir();
    writeLock(cwd, {
      version: 1,
      project_id: "pid",
      skills: {
        zeta: { server: "s", installed_at: "t", hash: "h", files: {} },
        alpha: { server: "s", installed_at: "t", hash: "h", files: {} },
      },
    });

    expect(readLock(cwd)?.skills).toEqual({
      alpha: { server: "s", installed_at: "t", hash: "h", files: {} },
      zeta: { server: "s", installed_at: "t", hash: "h", files: {} },
    });
  });

  it("throws a CliError on invalid JSON instead of overwriting", () => {
    const cwd = makeTempDir();
    fs.mkdirSync(path.join(cwd, ".claude"));
    fs.writeFileSync(path.join(cwd, LOCK_FILE_RELATIVE), "{not json");

    expect(() => readLock(cwd)).toThrow(CliError);
  });

  it("throws a CliError on an unknown lock version", () => {
    const cwd = makeTempDir();
    fs.mkdirSync(path.join(cwd, ".claude"));
    fs.writeFileSync(
      path.join(cwd, LOCK_FILE_RELATIVE),
      JSON.stringify({ version: 99, project_id: "x", skills: {} }),
    );

    expect(() => readLock(cwd)).toThrow(/unexpected format/);
  });
});

describe("recordSkillInstalls", () => {
  it("creates the lock file with a project id and per-file hashes", () => {
    const cwd = makeTempDir();
    const skillDir = path.join(cwd, ".claude", "skills", "my-skill");
    fs.mkdirSync(skillDir, { recursive: true });
    fs.writeFileSync(path.join(skillDir, "SKILL.md"), "# My Skill");

    recordSkillInstalls(cwd, ["my-skill"], "http://127.0.0.1:8000");

    const lock = readLock(cwd);
    expect(lock?.version).toBe(1);
    expect(lock?.project_id).toMatch(/^[0-9a-f-]{36}$/);
    const entry = lock?.skills["my-skill"];
    expect(entry?.server).toBe("http://127.0.0.1:8000");
    expect(entry?.installed_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(entry?.files).toEqual({ "SKILL.md": sha256("# My Skill") });
    expect(entry?.hash).toBe(hashDirectory(skillDir).hash);
  });

  it("keeps the project id and other entries on a later install", () => {
    const cwd = makeTempDir();
    for (const name of ["one", "two"]) {
      const dir = path.join(cwd, ".claude", "skills", name);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "SKILL.md"), name);
    }

    recordSkillInstalls(cwd, ["one"], "s");
    const firstId = readLock(cwd)?.project_id;
    recordSkillInstalls(cwd, ["two"], "s");

    const lock = readLock(cwd);
    expect(lock?.project_id).toBe(firstId);
    expect(Object.keys(lock?.skills ?? {})).toEqual(["one", "two"]);
  });

  it("does nothing when no skill was installed", () => {
    const cwd = makeTempDir();
    recordSkillInstalls(cwd, [], "s");
    expect(fs.existsSync(path.join(cwd, LOCK_FILE_RELATIVE))).toBe(false);
  });
});
