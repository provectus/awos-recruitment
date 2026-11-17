# disaster-recovery-plan

Registry notes for the `disaster-recovery-plan` skill. This file is not installed with the skill.

## What it does

The skill writes a disaster recovery plan for one environment of a cloud system, for the loss of its whole region. It answers three questions in order:

1. How is the environment recovered **today**, step by step?
2. What must the team **build** to recover better, in what order, at what monthly cost?
3. How does recovery work **after** that is built?

It writes `context/disaster-recovery/[env]/dr-recovery-today.md`, `context/disaster-recovery/[env]/dr-improvement-plan.md`, and a shared `context/disaster-recovery/disaster-recovery-plan.md` for all environments.

## How it works

- It reads the architecture record (`context/product/architecture.md` and `context/sources/sources.md` if they exist, otherwise the README, docs and infrastructure code).
- It reads the infrastructure code through an `Explore` agent.
- On a re-run (Update Mode) it edits the existing documents in place and keeps the team's edits, such as drill-measured times in §6.
- It checks the live cloud with read-only commands, scoped to the environment's own resources.
- It writes every fact to one temporary facts file outside the project.
- Three subagents draft the plans from that file: recovery today on `opus` at `medium` effort, the improvement plan on `fable` at `high`, and the recovery after the improvements on `opus` at `medium`. If a model is not available, the run uses the default model.
- It checks that the documents agree. When the third subagent reports many inconsistencies, one more subagent (`opus` at `medium`) fixes them, and the run checks the result.
- Commands in the documents never use the local CLI setup of the run: profile names are placeholders, and each plan starts with a step that selects access to the account.
- It asks the user about the open assumptions.

## Time and cost

One full run, measured on 2026-11-09 and 2026-11-11 with `claude -p` on one production environment, a managed Kubernetes cluster (all three documents written):

| Run | Time   | Cost   | `opus` | `fable` |
| --- | ------ | ------ | ------ | ------- |
| 1   | 51 min | $19.78 | $14.10 | $5.69   |
| 2   | 43 min | $18.08 | $12.17 | $5.91   |
| 3   | 54 min | $20.68 | $15.65 | $5.04   |

The improvement plan runs on `fable` at `high` effort. Runs on smaller environments were not measured.

## Safety

- Read-only: it never applies infrastructure-as-code, fails over, or changes a resource. A hook in the main session allows only listed read commands, and refuses `Read` and `Grep` calls that would print a secret file (see below).
- Every subagent gets the same rules file, including the agents that read code, sources and the live cloud.
- Secret names only: it never runs a read command that prints a secret value (for example `get-secret-value`, `terraform state pull`, or function environment variables), and never runs `init` or `plan`. A secret found in git or in an outside source is reported by location only.
- Region loss only: losses inside a healthy region are recorded as architecture gaps, not recovered.

## Read-only hook

The front matter declares a `PreToolUse` hook on `Bash`, `Read` and `Grep` ([scripts/block-writes.sh](scripts/block-writes.sh)). A `Read` or `Grep` call is checked as the `cat` or `grep` command it stands for, so the secret-file and secret-word rules below apply to it too: `Read` of a `secrets/` file, a `.tfvars` or `.env` file is refused, and so is a `Grep` that prints the lines of such files or the lines that match secret words; a `Grep` that lists files or counts matches passes. `Glob` lists names only and is not checked. It is an allow-list: a command passes only if every part of it is a listed read. The hook splits the command on `;`, `&`, `|` and newlines outside quotes, joins line continuations, finds each part's real command word (past `sudo`, `env`, `xargs`, `timeout`, `do`, assignments and shell functions), and checks the bodies of `$(...)`, `<(...)` and backticks as commands of their own. A command that gets its file names from input (`xargs`, `parallel`, `find -exec`) may only be `ls`, `stat`, `wc`, a checksum or `grep -l` or `-c`: the hook cannot see those files, so it does not let such a command print or change them.

- **Passes:** shell syntax and common local tools (`cat`, `grep`, `sed`, `awk`, `jq`, `yq`, `find`, `diff`, `cp`, `mkdir`, `tee`, `dig` and similar); HTTP reads (`curl -G` with `--data-urlencode` included); and the read verbs of these CLIs:
  - `aws`: `describe-*`, `list-*`, `get-*`, `head-*`, `lookup-*`, `search-*`, `filter-*`, `s3 ls`, `sts get-caller-identity`;
  - `az`: `list`, `show`, `query`, and GET requests through `az rest`;
  - `gcloud`: `list`, `describe`, `read`, `get-iam-policy`; `gsutil`: `ls`, `du`, `stat`;
  - `kubectl`: `get`, `describe`, `top`, `events`, `config view`; `helm`: `list`, `status`, `history`, `show`;
  - `terraform`/`tofu`: `version`, `validate`, `providers`, `graph`, `fmt -check`;
  - `git` reads, and `gh` `list`, `view` and GET API calls.
- **Local selection and cluster access pass on every provider:** `az account set`, `gcloud config`, `aws eks update-kubeconfig`, `az aks get-credentials`, `gcloud container clusters get-credentials`.
- **Refused even though they read**, because they print secrets or stored data: `get-secret-value`, `--with-decryption`, `--include-value(s)`, any AWS operation named for a password, token, credential or API key (for example `eks get-token`, `redshift get-cluster-credentials`, `appsync list-api-keys`), `cognito-idp describe-user-pool-client` unless a `--query` leaves the secret out, `get-object`, `get-item`, `scan`; `az keyvault secret show`, key lists and publishing profiles; `gcloud secrets versions access`, `print-access-token`; `kubectl get secret -o`, `--raw`; `kubectl get -o yaml|json` of ConfigMaps, pods, workloads, Argo CD applications, Flux objects, notebooks, inference services and external secrets, and `kubectl describe configmap`, with any flags before the resource type (`kubectl get -n prod secret db -o yaml`) (use `-o jsonpath` or `-o custom-columns` for the fields you need); `helm get values`; function, container, build and app environment reads unless the filter shows names only (`keys(@)`, `[].name`, or a projection that does not touch the environment; `--format=json` does not count); manifest renders not piped into `yq` or `grep`, and renders with plugins; `.env`, state, `tfvars`, key and credentials files, anything in a `secrets/` folder, and `*secret*` or `*cred*` manifests (`ls` and `grep -l` pass); searches for secret words that print the lines (`grep -l` passes); bare `env`, `printenv`; the instance metadata service. Field filters (`--query`, `--format`, `-o jsonpath`, `-o custom-columns`, `--jq`) that select a secret-valued field (a password, connection string, account key, client secret or token field; names in literals such as `name=='github-token'` do not count), the whole `.data` of a ConfigMap (one named key passes, and so does `| jq 'keys'`) or container `env` values (`env[*].name` passes). Log reads, which can print anything: `kubectl logs`, CloudWatch `filter-log-events`/`get-log-events`/`get-query-results`, `gcloud logging read`, `az … logs show`, Log Analytics and Application Insights queries. `gh api …/hooks` without a `--jq`, or with one that prints the config or delivery content (the URL host passes: `.config.url | split("/")[2]`). `az aks get-credentials --admin` and `--file -`.
- **Refused by default:** every other command, including deployers (Pulumi, CDK, Serverless, Argo CD, Flux…), task runners, package scripts, secret managers, `docker`, `ssh`, unknown binaries, and the CLIs of other providers (`oci`, `doctl`, `hcloud`, `flyctl`, `heroku`…), reads included. On such a provider, every live fact stays _unverified_ until the list grows. The block message tells the agent to record the fact as _unverified_ with the command for a human to run.
- **Code and scripts:** `eval`, a command word from a variable, input piped into a shell and `bash -c "$VAR"` are refused. A script run with `sh`, `bash`, `python` or `./` is read and checked first, two levels deep. Inline program code (`python -c`, a heredoc) passes unless it imports a cloud SDK, a process or a network module, or calls one (`subprocess.`, `os.system(`, `fetch(`…); words in the text it writes, such as "kubernetes" or "requests", do not count. A heredoc that writes a file is data, unless the same call also runs a script. Options of listed tools that run a command are refused too: an `awk` output pipe (`print … | "sh"`), an `awk` `print` to a file (`>`, `>>`), also when the program is in double quotes; `awk -f`, an awk program in `$'...'` quotes, `ENVIRON`, and gawk's `-E`, `-i`, `-l`, `@include` and `@load`; GNU `sed` with the `e` command or flag, `sort --compress-program`, `git -c`, `--config-env` and `--exec-path`, `git grep -O`, `--upload-pack` and `--ext-diff`, and variables that make a tool run a command or load code (`GIT_*`, `PAGER`, `EDITOR`, `LESSOPEN`, `BASH_ENV`, `LD_*`, `DYLD_*`, `NODE_OPTIONS` and similar).

Notes:

- **Subagents.** Verified on 2026-11-06: Claude Code runs a skill's hooks in the main session only (across three ClusterQuest runs, the skill hook saw 0 of 161 subagent Bash calls). The skill therefore keeps every command that reaches a cloud, a cluster or another remote system in the main session, and subagents read files and write documents. To also enforce this in subagents, a project adds the settings hook in [references/subagent-gate.md](references/subagent-gate.md) once. Settings hooks run in subagents, which share the main session's id. The skill hook marks the session on its first Bash or Agent call (`DRP_MODE=skill`); the settings hook (`DRP_MODE=gate`) checks a subagent's Bash, Read or Grep call only while that mark exists, so outside DR runs it allows every call. A command that touches the mark folder is refused. Without the gate, the run's report says once that subagents were held by the rules only.
- **Limits.** It reads text, so it is a guardrail, not a sandbox: a program that builds a command at run time, or a listed tool used in an unusual way, can pass it. It checks field filters by the field names they mention, so a broad filter (`--query 'properties'`, `-o jsonpath='{.spec}'`) can still print a value it does not name, and a recursive search over a folder prints the lines of every file under it, the secret ones included. The rules file stays the primary control.
- **Lifetime.** Claude Code registers a skill hook when the skill starts and keeps it until the session ends. After a DR run, these commands stay blocked in that session, in subagents too when the gate is installed. Start a new session to run them.
- **Location.** The hook looks for the script in `$CLAUDE_PROJECT_DIR/.claude/skills/` and then `~/.claude/skills/`. If it finds neither, it refuses the call (exit 2). The hook also sets `onFailure: block`, so from Claude Code v2.1.295 a crash or a timeout of the hook refuses the call too; older versions ignore the key (checked on v2.1.286).
- **Self-test.** A managed setting can turn off the hooks of a skill that is not in a plugin (`strictPluginOnlyCustomization`). Thus, in Step 2.4, the skill runs `drp-hook-selftest`, which the hook always refuses. If the hook does not refuse it, the skill tells the user at once, and the report says that no hook checked the commands.
- **Parsing.** It reads the command with `jq`, else `python3`, else `sed`. Failing all three, it scans the whole hook input, which can block more but never less. If its own check fails (an awk error), it refuses the command. A check takes about 40 ms.
- **Tests.** `python3 scripts/block-writes_test.py` runs 362 commands and 22 `Read` and `Grep` calls through the hook, with and without `jq` and `python3`, plus 14 checks of the subagent gate: reads a DR run needs (among them commands from two real runs), and writes, secret reads, unlisted tools and shell evasions. The 762 distinct Bash commands of seven debug runs (four on an AWS serverless project, three on an Azure AKS Kubeflow project) pass, except thirteen it is meant to refuse: secret-file reads, an `xargs grep` that prints lines of secret manifests, secret-word matches, full webhook URLs, a local configuration write, a command name from a variable, a heredoc script run in the same call, and backticks inside double quotes. Their 77 `Read` and `Grep` calls all pass.

## Tests

`evals/evals.json` holds eleven test cases. [evals/fixtures.md](evals/fixtures.md) holds the fixture projects they run on: one AWS environment, an Azure variant and a Google Cloud variant, with the additions each case needs (a fake secret in a saved plan, existing documents with a drill time in §6, a runbook with a fake password).

## Requirements

- Read-only access to the cloud provider's CLI (and the compute platform's CLI, if any). Without access, the run continues and marks the affected facts as unverified.
- The `Agent` tool for the drafting subagents. Without it, the run drafts the plans itself.

## Origin

Tested on a serverless AWS project with one environment, and on an Azure AKS Kubeflow environment with Argo CD.

## Invocation

`disable-model-invocation: true`: the skill runs only as `/disaster-recovery-plan`. A run starts several subagents and reads the live cloud, so a passing question about region failure must not start one.

Install this skill directly. Do not add it to the `skills:` list of an agent: it is a process that the user starts, not knowledge for a role.
