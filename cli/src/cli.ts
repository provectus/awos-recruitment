import { installAgents } from "./commands/agent.js";
import { installHooks } from "./commands/hook.js";
import { installMcpServers } from "./commands/mcp.js";
import { installSkills } from "./commands/skill.js";
import { skillStatus } from "./commands/skill-status.js";
import { skillDiff } from "./commands/skill-diff.js";
import { skillMerged } from "./commands/skill-merged.js";
import { skipSkills } from "./commands/skill-skip.js";
import { skillUpdate } from "./commands/skill-update.js";
import { CliError } from "./lib/errors.js";

const USAGE = `Usage: awos <command> <names...>

Commands:
  skill <names...>          Install skills into .claude/skills/ (--force to replace)
  skill status              Compare installed skills with the registry (--json)
  skill update [names...]   Update outdated skills (--dry-run, --overwrite, --no-overwrite)
  skill skip <names...>     Do not offer the current registry version of these skills again
  skill diff [names...]     Show what an update would change in each skill (--keep to prepare a merge)
  skill merged <names...>   Record a merge of the registry version with your own edits
  mcp <names...>            Install MCP servers into .mcp.json
  agent <names...>          Install agents into .claude/agents/
  hook <names...>           Install hooks into .claude/hooks/ (prompts; --yes/-y to skip)

Installed skills are recorded in .claude/awos-recruitment.lock.json.`;

const KNOWN_FLAGS = new Set([
  "--yes",
  "-y",
  "--force",
  "--json",
  "--dry-run",
  "--overwrite",
  "--no-overwrite",
  "--keep",
]);

export async function run(): Promise<void> {
  const rawArgs = process.argv.slice(2);
  const flags = new Set(rawArgs.filter((a) => a.startsWith("-")));
  const args = rawArgs.filter((a) => !a.startsWith("-"));
  const subcommand = args[0];
  const names = args.slice(1);

  for (const flag of flags) {
    if (!KNOWN_FLAGS.has(flag)) {
      throw new CliError(`Error: unknown option '${flag}'. Run 'awos' for usage.`);
    }
  }
  const yes = flags.has("--yes") || flags.has("-y");
  const force = flags.has("--force");

  if (subcommand === undefined) {
    process.stderr.write(USAGE + "\n");
    process.exit(1);
  }

  if (subcommand === "skill" && names[0] === "status") {
    if (names.length > 1) {
      throw new CliError("Error: 'skill status' takes no names.");
    }
    await skillStatus({ json: flags.has("--json") });
    return;
  }

  if (subcommand === "skill" && names[0] === "diff") {
    await skillDiff(names.slice(1), { keep: flags.has("--keep") });
    return;
  }

  if (subcommand === "skill" && names[0] === "merged") {
    await skillMerged(names.slice(1));
    return;
  }

  if (subcommand === "skill" && names[0] === "skip") {
    await skipSkills(names.slice(1));
    return;
  }

  if (subcommand === "skill" && names[0] === "update") {
    await skillUpdate(names.slice(1), {
      dryRun: flags.has("--dry-run"),
      overwrite: flags.has("--overwrite"),
      noOverwrite: flags.has("--no-overwrite"),
    });
    return;
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
  if (flags.has("--keep")) {
    throw new CliError("Error: --keep is supported for 'skill diff' only.");
  }
  for (const flag of ["--json", "--dry-run", "--overwrite", "--no-overwrite"]) {
    if (flags.has(flag)) {
      throw new CliError(`Error: ${flag} is supported for 'skill status' / 'skill update' only.`);
    }
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
