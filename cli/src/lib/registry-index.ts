import { CliError, NetworkError } from "./errors.js";

/** Shape of `GET /index.json` (see server `registry_index.py`). */
export interface RegistryIndex {
  version: number;
  generated_at: string;
  skills: Record<
    string,
    {
      hash: string;
      files: Record<string, string>;
      /** Registry commit of the current version, when the server knows it. */
      commit?: string | null;
      /** Date the current version appeared in the registry (YYYY-MM-DD). */
      released?: string | null;
    }
  >;
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

/** One past version of a skill (see server `history.py`). */
export interface HistoryVersion {
  hash: string;
  from: string;
  to: string | null;
  commit: string;
}

/** Shape of `GET /history.json`. */
export interface RegistryHistory {
  version: number;
  generated_at: string | null;
  skills: Record<string, HistoryVersion[]>;
}

/** Fetches every past version of every skill. Empty when the server has no history file. */
export async function fetchRegistryHistory(serverUrl: string): Promise<RegistryHistory> {
  const url = `${serverUrl}/history.json`;
  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new NetworkError(`Error: could not connect to AWOS server at ${url}.`);
  }
  if (response.status !== 200) {
    throw new CliError(`Error: server returned status ${response.status} for ${url}.`);
  }
  const body = (await response.json()) as Partial<RegistryHistory>;
  return {
    version: body.version ?? 1,
    generated_at: body.generated_at ?? null,
    skills: body.skills ?? {},
  };
}
