import { installSkills } from "./commands/skill.js";
import { CliError } from "./lib/errors.js";

const USAGE = `Usage: awos <command> <names...>

Commands:
  skill   Install skills into .claude/skills/
  mcp     Install MCP servers into .mcp.json`;

export async function run(): Promise<void> {
  const args = process.argv.slice(2);
  const subcommand = args[0];
  const names = args.slice(1);

  if (subcommand === undefined) {
    process.stderr.write(USAGE + "\n");
    process.exit(1);
  }

  if (subcommand !== "skill" && subcommand !== "mcp") {
    throw new CliError(
      `Error: unknown command '${subcommand}'. Run 'awos' for usage.`,
    );
  }

  if (names.length === 0) {
    throw new CliError(
      "Error: no names provided. Usage: awos <command> <name1> [name2] ...",
    );
  }

  switch (subcommand) {
    case "skill":
      await installSkills(names);
      break;
    case "mcp":
      console.log("mcp command: not yet implemented");
      break;
  }
}
