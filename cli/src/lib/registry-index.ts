import { CliError, NetworkError } from "./errors.js";

/** Shape of `GET /index.json` (see server `registry_index.py`). */
export interface RegistryIndex {
  version: number;
  generated_at: string;
  skills: Record<string, { hash: string; files: Record<string, string> }>;
  removed: Record<
    "skills" | "agents" | "hooks" | "mcp",
    Record<string, { removed: string; reason: string | null; replacement: string | null }>
  >;
}

/** Fetches the registry index from the server. */
export async function fetchRegistryIndex(serverUrl: string): Promise<RegistryIndex> {
  const url = `${serverUrl}/index.json`;
  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new NetworkError(`Error: could not connect to AWOS server at ${url}.`);
  }
  if (response.status !== 200) {
    throw new CliError(`Error: server returned status ${response.status} for ${url}.`);
  }

  const body = (await response.json()) as Partial<RegistryIndex>;
  if (body.version !== 1 || typeof body.skills !== "object" || body.skills === null) {
    throw new CliError("Error: unexpected registry index format from the server.");
  }
  const removed = body.removed ?? { skills: {}, agents: {}, hooks: {}, mcp: {} };
  return {
    version: body.version,
    generated_at: body.generated_at ?? "",
    skills: body.skills,
    removed: {
      skills: removed.skills ?? {},
      agents: removed.agents ?? {},
      hooks: removed.hooks ?? {},
      mcp: removed.mcp ?? {},
    },
  };
}
