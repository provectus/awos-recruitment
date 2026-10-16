import { installAgents } from "./commands/agent.js";
import { installHooks } from "./commands/hook.js";
import { installMcpServers } from "./commands/mcp.js";
import { installSkills } from "./commands/skill.js";
import { CliError } from "./lib/errors.js";

const USAGE = `Usage: awos <command> <names...>

Commands:
  skill   Install skills into .claude/skills/ (--force to replace installed ones)
  mcp     Install MCP servers into .mcp.json
  agent   Install agents into .claude/agents/
  hook    Install hooks into .claude/hooks/ (prompts; --yes/-y to skip)

Installed skills are recorded in .claude/awos-recruitment.lock.json.`;

const FLAGS = new Set(["--yes", "-y", "--force"]);

export async function run(): Promise<void> {
  const rawArgs = process.argv.slice(2);
  const yes = rawArgs.includes("--yes") || rawArgs.includes("-y");
  const force = rawArgs.includes("--force");
  const args = rawArgs.filter((a) => !FLAGS.has(a));
  const subcommand = args[0];
  const names = args.slice(1);

  if (subcommand === undefined) {
    process.stderr.write(USAGE + "\n");
    process.exit(1);
  }

  if (
    subcommand !== "skill" &&
    subcommand !== "mcp" &&
    subcommand !== "agent" &&
    subcommand !== "hook"
  ) {
    throw new CliError(
      `Error: unknown command '${subcommand}'. Run 'awos' for usage.`,
    );
  }

  if (names.length === 0) {
    throw new CliError(
      "Error: no names provided. Usage: awos <command> <name1> [name2] ...",
    );
  }

  if (force && subcommand !== "skill") {
    throw new CliError("Error: --force is supported for 'skill' only.");
  }

  switch (subcommand) {
    case "skill":
      await installSkills(names, { force });
      break;
    case "mcp":
      await installMcpServers(names);
      break;
    case "agent":
      await installAgents(names);
      break;
    case "hook":
      await installHooks(names, { yes });
      break;
  }
}
