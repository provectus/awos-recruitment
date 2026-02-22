import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as zlib from "node:zlib";
import * as tar from "tar";

import { CliError, NetworkError } from "./errors.js";

/**
 * Fetches a tar.gz bundle from the given URL and extracts it into a
 * temporary directory.
 *
 * @param url  - The server endpoint to POST to (e.g. `http://host/bundle/skills`).
 * @param names - The list of bundle names to request.
 * @returns The absolute path to the temp directory containing the extracted files.
 */
export async function downloadBundle(
  url: string,
  names: string[],
): Promise<string> {
  // --- 1. POST the request ---------------------------------------------------
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ names }),
    });
  } catch {
    throw new NetworkError(
      `Error: could not connect to AWOS server at ${url}.`,
    );
  }

  // --- 2. Validate the response status ---------------------------------------
  if (response.status !== 200) {
    throw new CliError(
      `Error: server returned status ${response.status}.`,
    );
  }

  // --- 3. Extract the tar.gz payload -----------------------------------------
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "awos-"));
  const tempTarFile = path.join(tempDir, "__bundle.tar");

  try {
    const compressed = Buffer.from(await response.arrayBuffer());
    const decompressed = zlib.gunzipSync(compressed);

    // An empty tar archive (all null bytes) is valid but tar v7 rejects it.
    // Skip extraction if the decompressed content has no real data.
    const hasContent = decompressed.some((byte) => byte !== 0);
    if (hasContent) {
      fs.writeFileSync(tempTarFile, decompressed);
      await tar.extract({ cwd: tempDir, file: tempTarFile });
    }
  } catch (err) {
    // Re-throw our own errors as-is (e.g. if tar.extract rejects).
    if (err instanceof CliError) {
      throw err;
    }
    throw new CliError("Error: failed to unpack server response.");
  } finally {
    // Clean up the intermediate tar file regardless of outcome.
    try {
      fs.unlinkSync(tempTarFile);
    } catch {
      // Best-effort cleanup; ignore if already gone.
    }
  }

  return tempDir;
}
