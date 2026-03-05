import * as fs from "node:fs";
import * as path from "node:path";

import { downloadBundle } from "../lib/download.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import type { AgentFrontmatter, InstallResult } from "../lib/types.js";
import { processSkills } from "./skill.js";

/**
 * Installs one or more agents by downloading their `.md` files from the
 * AWOS server and copying them into `.claude/agents/` in the current
 * working directory.
 *
 * Phase 1: agent file installation.
 * Phase 2: auto-install skills referenced in installed agents' frontmatter.
 *
 * Exits with code 1 if any requested agent or referenced skill has
 * `"not-found"` status. Skipped (already-existing) agents and skills
 * are NOT treated as errors.
 */
export async function installAgents(names: string[]): Promise<void> {
  const serverUrl =
    process.env.AWOS_SERVER_URL || "https://recruitment.awos.provectus.pro";

  // --- Phase 1: Install agents -----------------------------------------------
  const agentTempDir = await downloadBundle(
    `${serverUrl}/bundle/agents`,
    names,
  );

  let agentResults: InstallResult[];
  try {
    agentResults = processAgents(agentTempDir, names);
  } finally {
    fs.rmSync(agentTempDir, { recursive: true, force: true });
  }

  // --- Phase 2: Auto-install referenced skills --------------------------------
  const skillResults = await installReferencedSkills(
    agentResults,
    serverUrl,
  );

  // --- Print combined summary -------------------------------------------------
  printResults(agentResults);

  if (skillResults.length > 0) {
    process.stdout.write("\nSkills (auto-installed):\n");
    printResults(skillResults);
  }

  // --- Exit code --------------------------------------------------------------
  const allResults = [...agentResults, ...skillResults];
  const hasNotFound = allResults.some(
    (r) => r.status === "not-found",
  );
  if (hasNotFound) {
    process.exit(1);
  }
}

/**
 * Reads frontmatter from newly installed agents, collects skill references,
 * filters out already-existing skills, downloads and installs the rest.
 */
async function installReferencedSkills(
  agentResults: InstallResult[],
  serverUrl: string,
): Promise<InstallResult[]> {
  // 1. Collect skill references from newly installed agents.
  const referencedSkills = new Set<string>();
  const agentsDir = path.join(process.cwd(), ".claude", "agents");

  for (const result of agentResults) {
    if (result.status !== "installed") {
      continue;
    }

    const agentFile = path.join(agentsDir, `${result.name}.md`);
    if (!fs.existsSync(agentFile)) {
      continue;
    }

    const content = fs.readFileSync(agentFile, "utf-8");
    const frontmatter = parseFrontmatter(content) as AgentFrontmatter | null;

    if (frontmatter?.skills) {
      for (const skill of frontmatter.skills) {
        referencedSkills.add(skill);
      }
    }
  }

  if (referencedSkills.size === 0) {
    return [];
  }

  // 2. Filter out skills that already exist locally.
  const skillResults: InstallResult[] = [];
  const missingSkills: string[] = [];
  const skillsBaseDir = path.join(process.cwd(), ".claude", "skills");

  for (const skill of referencedSkills) {
    const skillDir = path.join(skillsBaseDir, skill);
    if (fs.existsSync(skillDir)) {
      skillResults.push({
        name: skill,
        status: "skipped",
        message: `Skipped skill '${skill}': already exists at .claude/skills/${skill}/`,
      });
    } else {
      missingSkills.push(skill);
    }
  }

  if (missingSkills.length === 0) {
    return skillResults;
  }

  // 3. Download and install missing skills.
  const skillTempDir = await downloadBundle(
    `${serverUrl}/bundle/skills`,
    missingSkills,
  );

  try {
    const installResults = processSkills(skillTempDir, missingSkills);
    skillResults.push(...installResults);
  } finally {
    fs.rmSync(skillTempDir, { recursive: true, force: true });
  }

  return skillResults;
}

/**
 * Compares requested names against what was extracted, copies found
 * agent files into the target directory, and returns per-item results.
 */
function processAgents(
  tempDir: string,
  requestedNames: string[],
): InstallResult[] {
  const extractedFiles = new Set(
    fs.readdirSync(tempDir).map((f) => f.replace(/\.md$/, "")),
  );
  const results: InstallResult[] = [];

  const agentsDir = path.join(process.cwd(), ".claude", "agents");
  fs.mkdirSync(agentsDir, { recursive: true });

  for (const name of requestedNames) {
    if (!extractedFiles.has(name)) {
      results.push({
        name,
        status: "not-found",
        message: `Error: capability '${name}' not found.`,
      });
      continue;
    }

    const targetFile = path.join(agentsDir, `${name}.md`);

    if (fs.existsSync(targetFile)) {
      results.push({
        name,
        status: "skipped",
        message: `Skipped agent '${name}': already exists at .claude/agents/${name}.md`,
      });
      continue;
    }

    const sourceFile = path.join(tempDir, `${name}.md`);
    fs.copyFileSync(sourceFile, targetFile);

    results.push({
      name,
      status: "installed",
      message: `Installed agent '${name}' to .claude/agents/${name}.md`,
    });
  }

  return results;
}

/**
 * Prints each install result to stdout (installed) or stderr (errors/skipped).
 */
function printResults(results: InstallResult[]): void {
  for (const result of results) {
    if (result.status === "installed") {
      process.stdout.write(result.message + "\n");
    } else {
      process.stderr.write(result.message + "\n");
    }
  }
}
