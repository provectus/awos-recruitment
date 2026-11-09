---
name: disaster-recovery-plan
description: >-
  Writes a disaster recovery plan for one environment of a cloud system, for the
  loss of its whole region: how to recover today, step by step; what to build to
  recover better, with monthly cost; and how recovery works once that is built.
  Checks every fact against the live cloud with read-only commands and marks what
  it could not verify. Use when the user asks for a disaster recovery plan, a DR
  plan, region-failure or region-loss readiness, "what happens if our region goes
  down", or wants an existing DR plan re-checked or updated.
argument-hint: '[environment — e.g. production or staging; optional recovery region or change request]'
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: "Bash|Agent|Read|Grep"
      hooks:
        - type: command
          command: >-
            sh -c 'for d in "$CLAUDE_PROJECT_DIR/.claude/skills" "$HOME/.claude/skills"; do
            f="$d/disaster-recovery-plan/scripts/block-writes.sh"; [ -f "$f" ] && exec env DRP_MODE=skill sh "$f"; done;
            echo "disaster-recovery-plan: scripts/block-writes.sh not found, cloud writes are not blocked" >&2; exit 1'
metadata:
  version: "1.0.0"
---

# Disaster Recovery Plan

Write an honest, verifiable disaster recovery plan for one environment: how it would be recovered from the loss of its cloud region today, what to build to recover better, and how recovery works once that is built. Check every fact against the live environment read-only, never assume from memory, and mark clearly what you could not verify. Write for an engineer under pressure: numbered steps, real commands, plain words.

**Read-only, always.** Use only commands that read state. Never apply infrastructure-as-code or run its `init` or `plan`, never fail over, create, change, lock or delete a resource — not even "to test" — and never run a read command that prints a secret value. Every command a human must run during a disaster goes into the documents, not into your shell. The full constraints and writing rules are in [references/rules.md](references/rules.md); read that file before Step 2, follow every rule in it, and give it unchanged to every subagent you start. A `PreToolUse` hook ([scripts/block-writes.sh](scripts/block-writes.sh)) checks every Bash command of this session against a list of read-only commands, and every Read and Grep call against the same secret-file rules: common local read tools and the read verbs of the cloud, cluster, infrastructure-as-code and git CLIs pass; any other command, a secret-printing read, and the shell routes around the check (`eval`, a command from a variable, a pipe into a shell, inline SDK or network code) are refused; scripts are read before they run. Claude Code runs a skill's hooks in the main session only, not in subagents, so run every command that reaches a cloud, a cluster or another remote system in this session; subagents only read files and write documents. A project can also check subagents with the settings hook in [references/subagent-gate.md](references/subagent-gate.md); if neither `.claude/settings.json` nor `.claude/settings.local.json` contains `DRP_MODE=gate`, say once in the final report that subagents were held by the rules only, and point to that file. The hook reads command text, so it is a guardrail, not a sandbox: the rules file stays the primary control. When it refuses a read you need, record the fact as _unverified_ with the command for a human to run.

## What it produces

One environment per run. Two per-environment documents, and one shared strategy document created or updated in place, each filled from its template in this skill's `assets/` folder:

| Output file                                              | Template                                 | Answers                                                                                                                                                     |
| -------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `context/disaster-recovery/disaster-recovery-plan.md`    | [assets/dr-overview-template.md](assets/dr-overview-template.md)             | Shared strategy for all environments: what holds state, current protection, ranked gaps, decisions, the map of all DR documents, a today-vs-after summary |
| `context/disaster-recovery/[env]/dr-recovery-today.md`   | [assets/dr-recovery-today-template.md](assets/dr-recovery-today-template.md) | Plan 1 — recovery today: what survives and what is lost, wait or rebuild, the day-by-day rebuild, when the home region returns, costs, secrets to re-issue |
| `context/disaster-recovery/[env]/dr-improvement-plan.md` | [assets/dr-improvement-plan-template.md](assets/dr-improvement-plan-template.md) | Plan 2 — improvements (phased, with per-item monthly cost) and, in §6, Plan 3 — recovery after the improvements                                           |

`[env]` is the environment's folder name, e.g. `production` or `staging`. If the user names a different output folder, use it.

**Scope: region loss only.** Losses inside a healthy region — a deleted or corrupted data store, a zone outage, a lost cluster — are resilience gaps in the architecture, not disaster recovery. When the inventory reveals one, record it in the shared strategy's gaps table with a pointer to where it should be fixed (the architecture or a feature spec), and write no recovery procedure for it.

**Not produced:** a day-of runbook (decision gates, owners' roster, communications templates, formal fail-back). It depends on a recovery design the team has not ratified yet. If the user asks for one, explain this and offer to write it once the team has ratified the design (the first decision in the improvement plan).

## Inputs

- **The request:** the environment, optionally a recovery region or a change request for existing documents.
- **The architecture record:** `context/product/architecture.md` if it exists, and `context/product/product-definition.md` for what is critical. Without them, the README, `docs/`, and the infrastructure code. Where nothing records the environments, build the list from the infrastructure code and say so.
- **Optional:** `context/sources/sources.md` if it exists — pointers to cloud accounts, runbooks, post-mortems and other material outside the repository.
- **Code:** the environment's infrastructure-as-code and deployment manifests, existing `context/disaster-recovery/` documents, post-mortems and runbooks in the repository.
- **Live, read-only:** the CLI of the cloud provider, scoped to the environment's account, subscription or project, and the CLI of its compute platform if any (for example `kubectl`).

## Interaction

- Use `AskUserQuestion` for every fixed-choice question.
- A skipped or unanswered question is never a stop signal. Record your best-fit option as an explicit `**Assumption:**` and continue, including writing the documents. The one exception is the environment selection in Step 1: without an environment there is nothing to verify or write.
- Unattended runs: when the user asked for no questions, or the session cannot ask (for example a non-interactive `claude -p` run), ask nothing. Resolve the environment as Step 1 says, skip Step 5, and carry every open choice as an `**Assumption:**`. Under `claude -p` a dismissed question ends the turn, which is why every write comes before any question.

## Process

### Step 1: Identify the environment

1. Map the request to an environment, its folder name, its cloud account (subscription / account / project), resource groupings, compute platform and infrastructure-as-code directory, from the architecture record.
2. If the request is empty and exactly one environment exists, use it and say so in one line — do not ask. If the request is empty with several environments, ambiguous, or names an environment the record does not list:
   - Unattended: stop with one line before asking anything — name the environments and ask for a re-run that names one.
   - Otherwise ask with `AskUserQuestion`, offering the known environments and any existing `context/disaster-recovery/*/` folders. An unanswered selection ends the run cleanly.
3. Mode. If `context/disaster-recovery/[env]/` already holds one or both files, this is Update Mode: read them, treat the rest of the request as the change request, and re-verify every fact the change touches. The existing documents hold the team's own edits — drill-measured times, ratified decisions — so Update Mode edits them in place and never rewrites them from the template (Step 4). Otherwise it is Creation Mode. The shared strategy is updated in place if it exists (only this environment's rows and sections change) and created from its template if not.

### Step 2: Gather context

1. Read, in one batch: the architecture record, the product definition if any, the shared strategy, the other environments' documents (for structure and shared mechanics — writing rule 8), and `context/sources/sources.md` if it exists.
2. External sources. If `sources.md` exists, take from it the sources that bear on infrastructure, operations and documentation. For each one reachable through an MCP server, retrieve it read-only with one `Explore` agent per source; read a source that only a CLI reaches (for example `gh`) in this session, where the hook checks the command. Give each agent [references/rules.md](references/rules.md) unchanged: a source can hold a secret, which the agent reports by location and kind only, never quoted. Note sources no tool can reach and ask for their content in Step 5.
3. Inventory from code. Delegate a read-only exploration to the built-in `Explore` agent (and a cloud or infrastructure-as-code specialist, if the `Agent` tool lists one) over the environment's infrastructure-as-code and deployment manifests. Ask for, with paths cited:
   - every stateful resource — databases, object and file storage, queues, caches that are not rebuildable, search indexes, container and artifact registries, secret stores, managed disks and persistent volumes;
   - every hard-coded region, and where infrastructure-as-code state lives (account, region, key);
   - what a second copy of the environment would collide with — webhooks on the same URL, CI runner registrations, DNS records, OAuth callbacks, globally unique names;
   - items the code and docs say are applied by hand or not in git, and jobs that exist only as live objects on the platform (the live check is Step 2.5, not this agent's);
   - external dependencies — networks and firewalls owned by other teams, DNS, identity, outside consumers.

   Give each agent [references/rules.md](references/rules.md) unchanged. It reads code and files only and runs no cloud, platform or infrastructure-as-code command; a committed secret is reported by location only, never opened or measured.

4. Check live access. Run one cheap read-only call per CLI (the provider's "who am I" or account-show command) and record each CLI's version. If a login is missing, tell the user once which one and continue: every fact that needed it is recorded _unverified_, with the command to run once access exists. When a check needs a subcommand the installed version lacks, say so once and record those facts _unverified_, with upgrading the CLI as the verify step.
5. Verify live, read-only, and record each fact with the date. Scope every call to this environment's own resources, by the names the inventory found or by the environment's tags. Never loop over every resource in the account: shared accounts hold unrelated resources, and an account-wide sweep can stall the run for minutes.
   - Storage: redundancy, cross-region replication and its status, used capacity, soft delete and versioning.
   - Databases: high availability mode, backup retention, whether backups are copied to another region, replicas and their regions, size and tier.
   - Secret stores and registries: public network access, network rules, private connections and the region of each, cross-region replicas. Secret names only.
   - Deletion locks or deletion protection on resources that hold state.
   - Compute platform: persistent volumes, objects that exist only live (scheduled jobs, serving objects), hand-applied objects.
   - Recovery region: quota (including specialised hardware), whether the network the environment depends on exists there, name collisions, the provider's paired or recommended secondary region.
   - Infrastructure-as-code state store: region and redundancy. If it sits in the home region of any environment, that region's loss blocks applies everywhere.

   A failed or forbidden read is recorded as _unverified — verify by: [command, run by whom]_, never guessed. Reachability: a secret store or registry whose public access is off and whose only private connections are in the home region is "probably not usable from the recovery region today", whatever copies the provider keeps.

6. Prices. Look up list prices (the provider's price list or pricing API) for every standing item today and after. Record the source.

### Step 3: Fix the facts

Everything the plans say comes from one file, so the drafts cannot disagree with each other or with the live environment.

1. Recovery region. Propose one (default: the provider's paired or recommended secondary region, unless quota, network or policy rule it out) and record it as an `**Assumption:**` unless the user, the architecture record or the shared strategy already settled it.
2. In Update Mode, copy the existing per-environment documents into a temporary folder outside the project (e.g. from `mktemp -d`) before any dispatch. Subagents read the other plan from these copies, never from a path another subagent is writing.
3. Write the facts file to a temporary path outside the project (e.g. from `mktemp`): environment and folder name, mode and change request, home and recovery region, the inventory with cited paths, every live fact with its _verified_ date and command or its _unverified — verify by:_ line, reachability decisions, prices with their source, open assumptions, the account, subscription or project ID (never the local profile, configuration or context name this run used — writing rule 5), and the absolute paths of the templates, of [references/rules.md](references/rules.md), of the existing documents and their Update Mode copies, and of the other environments' documents. Secret names only. This file is never written into the project.

### Step 4: Draft and write the plans

Dispatch each plan to its own `Agent` subagent (`subagent_type: general-purpose`) with the model below in the `model` field. The `Agent` tool has no effort field: state the effort in the prompt (for example "Work at high effort."). Each prompt carries the facts file path, the rules file path, its template path and its output path. The subagent reads only those files and the documents the facts file lists; it runs no cloud or platform command, and a fact missing from the facts file goes in as _unverified_, never looked up or guessed. It writes its file without waiting for approval and returns its headline, its numbers and any facts it found missing.

| Plan                                     | Writes                                                  | Model   | Effort   | Runs                     |
| ---------------------------------------- | ------------------------------------------------------- | ------- | -------- | ------------------------ |
| Plan 1 — recovery today                  | `dr-recovery-today.md`                                  | `opus`  | `medium` | together with Plan 2     |
| Plan 2 — improvement plan                | `dr-improvement-plan.md`, every section but §6          | `fable` | `high`   | together with Plan 1     |
| Plan 3 — recovery after the improvements | §6 of `dr-improvement-plan.md` only                     | `opus`  | `medium` | after Plan 2 has written |

Dispatch Plans 1 and 2 in one message so they run concurrently; dispatch Plan 3 when Plan 2 returns, since it builds on Plan 2's design.

- **Plan 1:** step 0 selecting access to the account (writing rule 5); §1 what survives and what is lost (the "usable from the recovery region today?" column driven by the verified reachability); §2 wait or rebuild (default, triggers, owner, the question that can make a rebuild pointless); §3 the day-by-day rebuild — long waits first (incident and freeze, quota, other teams, re-issue secrets), then infrastructure-as-code with a new state key, a targeted first apply, imports of surviving global resources, data restores, a full apply, then the platform, then data and serving; "When the home region returns"; §4 costs today; the appendix of secret names by owner.
- **Plan 2:** §0 sizes, §0.1 today-vs-after and cost tables (Today from the facts file), §1 inventory, then the phases — decisions and requests to other teams, home-region hardening, the recovery environment (layout, what pre-exists in the recovery region, what it must do differently, keeping it current), backup and replication jobs, the drill — and §8 order of work and effort. Fit the number and names of phases to the environment. In Creation Mode, leave §6 as the template's placeholder; in Update Mode, keep the existing §6 unchanged. Return the list of sections whose design changed.
- **Plan 3:** reads the written improvement plan, then writes §6 (in Update Mode, changes §6 only where Plan 2's changed sections or the change request touch it, and keeps the rest): the lowered wait-or-fail-over threshold, then the deploy sequence in the order the data stores come back, ending with re-protecting the recovery site and the user announcement of what was not recovered. It changes nothing outside §6, and returns every inconsistency it finds between the improvement plan, recovery today and the facts file — numbers that disagree, a fact marked _unverified_ that the facts file settles, a cross-reference that points nowhere, a command with wrong syntax.

**Update Mode.** Each prompt also says Update Mode, carries the change request and the path of the existing document, and tells the subagent to edit that document in place: change only the parts the change request and the re-verified facts touch, keep everything else as written, and keep any value the team measured or ratified unless a re-verified fact contradicts it — then report the conflict instead of overwriting silently. If only one of the two per-environment files exists, the subagent for the missing one creates it from its template.

**Missing facts.** When a subagent returns facts it found missing, settle every one a read-only call can answer (within the scope of Step 2), and append each to the facts file with its date and command before the next dispatch. A fact that stays open remains _unverified_.

**Fallback.** If an `Agent` call is rejected for its `model` value, dispatch it again without that field so it runs on the default model, and name the substitution in the report. If the `Agent` tool is unavailable, draft the three plans yourself in order: Plan 1, Plan 2, Plan 3.

Then, yourself:

1. **Shared strategy:** from the facts file and the subagents' headlines, add or update this environment in the summary, document map, today-vs-after table, inventory, gaps and decisions. Leave other environments' content untouched unless a fact is shared. Write it without waiting for approval.
2. **Self-check** the written documents and fix what fails:
   - every stateful resource in the facts file appears in §1 of both per-environment documents, or is listed as left out with the reason;
   - the documents agree: Today numbers match across Plan 1, the improvement plan's §0.1 and the shared strategy; After numbers match what the §6 sequence adds up to; §6 covers every data store the improvement plan protects;
   - every inconsistency Plan 3 reported is fixed, and every fact settled after a draft was written is updated in the documents. When the list is longer than a handful of items, dispatch one more `Agent` subagent (`opus`, `medium`, same fallback) with the list, the facts file, the rules file and the three document paths: it edits in place, changes nothing that is not on the list, runs no cloud command, and returns what it changed and what it could not fix. Then run this self-check yourself on the result;
   - each document is near its length target (writing rule 11): count its lines with `wc -l`. Aim at the target. A per-environment document more than a quarter over its target (half over for a large environment, such as a Kubernetes platform with many workloads) is cut before the run ends; that limit is the most a document may reach, not the goal. The shared strategy has no large-environment allowance: about 250 lines, plus about 50 for each further environment. To cut: merge repeated explanations into one section and link to it, write option mechanics once and only the differences per option, and move long blocks to the appendix, which counts too. Never cut a step, a hazard or a check. Give the line counts and targets in the final report;
   - no command depends on this machine: no local profile, configuration or context name, no absolute local path; each per-environment document starts its steps with selecting access to the account;
   - no command sits in a table cell or inline in prose, and nothing is said twice — long blocks go to the appendix, steps are never cut. Find inline commands with `grep -nE '`(az|aws|gcloud|gsutil|kubectl|helm|terraform|tofu|gh|git|curl) [a-z-]+' <document>`; move each hit that is a command, not a resource or field name, into a fenced block of its step;
   - no bare abbreviations; every cost table has Today and After; every unverified claim says how to verify it;
   - no runbook content and no recovery procedure for an in-region loss.

The documents are written whether or not every question was answered — they are reversible (re-run this skill to revise), so they are never gated behind a confirmation an unattended run cannot give. Do not commit; leave git to the user.

### Step 5: Review with the user

Skip this step in unattended runs.

1. Ask with `AskUserQuestion` (up to four questions per call) only what the drafts recorded as assumptions and the live checks could not settle, plus the content of any `manual` sources. Typical questions: the recovery region; the proposed recovery time and recovery point objectives; the wait threshold and its owner; data accepted as lost by policy; which improvement option is in scope; how many engineers are available during a disaster.
2. Apply the answers to the facts file and the documents. Edit small answers in place; when an answer reshapes the design (a different region, another option), re-dispatch the affected plans as in Step 4 in Update Mode, Plan 2 before Plan 3. Answers stay proposals until the team ratifies them. Unanswered questions stay as `**Assumption:**` lines.

### Step 6: Report

1. The saved paths; the headline today-vs-after numbers (time to recover, data lost, standing cost); open assumptions and _unverified_ facts with how each will be verified (usually in the drill); any model or effort substitution the fallback made; any security finding outside DR, such as a committed secret. Then the commands the read-only hook refused, in this session and in the subagents: count them from the hook's own messages (each starts "Blocked by the disaster-recovery-plan skill") and the subagents' lists, never from memory, and give each in one line with what was done instead. Say "none" when there were none.
2. Next steps: run this skill for each environment not yet covered; turn the improvement plan's phases into specs or tickets; re-run after each phase lands, or after a drill measures real times, so the documents stay true.
