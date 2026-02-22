import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as zlib from "node:zlib";
import * as tar from "tar";
import { describe, it, expect, vi, afterEach } from "vitest";

import { downloadBundle } from "../download.js";
import { CliError, NetworkError } from "../errors.js";

/**
 * Creates a real tar.gz buffer containing the given files.
 *
 * @param files - An object mapping relative file paths (e.g. "skill-a/SKILL.md")
 *                to their string content.
 * @returns A gzipped tar buffer ready to be served as a mock response body.
 */
function createTarGzBuffer(files: Record<string, string>): Buffer {
  // Write the files to a staging directory, create a tar from it, then gzip.
  const staging = fs.mkdtempSync(path.join(os.tmpdir(), "tar-staging-"));
  const topLevelEntries: string[] = [];

  try {
    for (const [relPath, content] of Object.entries(files)) {
      const abs = path.join(staging, relPath);
      fs.mkdirSync(path.dirname(abs), { recursive: true });
      fs.writeFileSync(abs, content, "utf-8");

      const topDir = relPath.split("/")[0]!;
      if (!topLevelEntries.includes(topDir)) {
        topLevelEntries.push(topDir);
      }
    }

    // Create tar synchronously into a file, then read + gzip it.
    const tarFile = path.join(staging, "__out.tar");
    tar.create(
      { cwd: staging, file: tarFile, sync: true },
      topLevelEntries,
    );

    const tarBuf = fs.readFileSync(tarFile);
    return zlib.gzipSync(tarBuf);
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------------------
// Helpers to build mock Response objects
// ---------------------------------------------------------------------------

function mockResponse(status: number, body: Buffer | string): Response {
  const buf =
    typeof body === "string" ? Buffer.from(body, "utf-8") : body;
  // Convert to Uint8Array to satisfy the BodyInit type constraint.
  return new Response(new Uint8Array(buf), { status });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("downloadBundle", () => {
  /** Track temp dirs created by successful calls so we can clean them up. */
  const tempDirs: string[] = [];

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
  // 1. Network error
  // -----------------------------------------------------------------------
  it("throws NetworkError when fetch rejects (unreachable server)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    );

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["a"]),
    ).rejects.toThrow(NetworkError);

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["a"]),
    ).rejects.toThrow(/could not connect/);
  });

  // -----------------------------------------------------------------------
  // 2. Non-200 response
  // -----------------------------------------------------------------------
  it("throws CliError when server returns a non-200 status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(400, "Bad Request")),
    );

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["x"]),
    ).rejects.toThrow(CliError);

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["x"]),
    ).rejects.toThrow(/status 400/);
  });

  // -----------------------------------------------------------------------
  // 3. Corrupt / non-gzip response body
  // -----------------------------------------------------------------------
  it("throws CliError with 'failed to unpack' for corrupt response body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(200, "this is not gzip")),
    );

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["y"]),
    ).rejects.toThrow(CliError);

    await expect(
      downloadBundle("http://localhost:9999/bundle/skills", ["y"]),
    ).rejects.toThrow(/failed to unpack/);
  });

  // -----------------------------------------------------------------------
  // 4. Successful download
  // -----------------------------------------------------------------------
  it("extracts a valid tar.gz and returns a temp directory with expected files", async () => {
    const tarGz = createTarGzBuffer({
      "skill-alpha/SKILL.md": "# Alpha Skill",
      "skill-alpha/extra.txt": "hello",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse(200, tarGz)),
    );

    const result = await downloadBundle(
      "http://localhost:9999/bundle/skills",
      ["skill-alpha"],
    );

    tempDirs.push(result);

    // The returned path should exist and be a directory.
    expect(fs.statSync(result).isDirectory()).toBe(true);

    // The extracted skill directory should be present.
    const skillDir = path.join(result, "skill-alpha");
    expect(fs.existsSync(skillDir)).toBe(true);

    // The expected files should exist with correct content.
    expect(
      fs.readFileSync(path.join(skillDir, "SKILL.md"), "utf-8"),
    ).toBe("# Alpha Skill");
    expect(
      fs.readFileSync(path.join(skillDir, "extra.txt"), "utf-8"),
    ).toBe("hello");

    // The intermediate tar file should have been cleaned up.
    expect(fs.existsSync(path.join(result, "__bundle.tar"))).toBe(
      false,
    );
  });
});
