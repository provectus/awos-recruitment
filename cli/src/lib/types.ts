export interface InstallResult {
  name: string;
  status: "installed" | "not-found" | "conflict" | "skipped" | "error";
  message: string;
}

export interface AgentFrontmatter {
  name: string;
  description: string;
  model?: string;
  skills?: string[];
}

/** Documented Claude Code hook events — keep in sync with
 * server/src/awos_recruitment_mcp/models/hook_metadata.py (HookEvent). */
export const HOOK_EVENTS = [
  "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
  "PermissionRequest", "PermissionDenied", "UserPromptSubmit",
  "UserPromptExpansion", "Notification", "MessageDisplay", "Stop",
  "StopFailure", "SubagentStart", "SubagentStop", "TaskCreated",
  "TaskCompleted", "TeammateIdle", "InstructionsLoaded", "ConfigChange",
  "CwdChanged", "FileChanged", "WorktreeCreate", "WorktreeRemove",
  "PreCompact", "PostCompact", "SessionStart", "SessionEnd", "Setup",
  "Elicitation", "ElicitationResult",
] as const;

export type HookEvent = (typeof HOOK_EVENTS)[number];

export interface HookDefinition {
  event: HookEvent;
  matcher?: string;
  timeout?: number;
}

export interface HookFrontmatter {
  name: string;
  description: string;
  hooks?: HookDefinition[];
}

export interface McpServerConfig {
  [key: string]: unknown;
}

export interface McpYamlShape {
  name: string;
  description: string;
  config: Record<string, McpServerConfig>;
}
