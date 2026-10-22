/**
 * Best-effort reporting of update events to the server (`POST /telemetry`).
 * Never throws and never delays the command by more than a few seconds.
 * Events carry the project's random id and capability names only.
 */
export interface ClientEvent {
  event: "capability_update_checked" | "capability_updated" | "capability_removed_in_use";
  capability_name?: string;
  capability_type?: "skill" | "agent" | "hook" | "mcp_server";
  properties?: Record<string, string | number | boolean>;
}

export async function sendTelemetry(
  serverUrl: string,
  projectId: string,
  events: ClientEvent[],
): Promise<void> {
  if (events.length === 0 || process.env.AWOS_TELEMETRY === "0") {
    return;
  }
  try {
    await fetch(`${serverUrl}/telemetry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, events: events.slice(0, 50) }),
      signal: AbortSignal.timeout(3000),
    });
  } catch {
    // Telemetry must never affect the command.
  }
}
