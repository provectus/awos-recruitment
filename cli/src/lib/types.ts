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

export interface McpServerConfig {
  [key: string]: unknown;
}

export interface McpYamlShape {
  name: string;
  description: string;
  config: Record<string, McpServerConfig>;
}
