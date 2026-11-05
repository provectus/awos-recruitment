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
- It checks the live cloud with read-only commands, scoped to the environment's own resources.
- It writes every fact to one temporary facts file outside the project.
- Three subagents draft the plans from that file: recovery today on `opus` at `medium` effort, the improvement plan on `fable` at `high`, and the recovery after the improvements on `opus` at `medium`. If a model is not available, the run uses the default model.
- It checks that the documents agree. When the third subagent reports many inconsistencies, one more subagent (`opus` at `medium`) fixes them, and the run checks the result.
- Commands in the documents never use the local CLI setup of the run: profile names are placeholders, and each plan starts with a step that selects access to the account.
- It asks the user about the open assumptions.

## Safety

- Read-only: it never applies infrastructure-as-code, fails over, or changes a resource.
- Secret names only: it never reads a secret value. A secret found in git is reported by location only.
- Region loss only: losses inside a healthy region are recorded as architecture gaps, not recovered.

## Requirements

- Read-only access to the cloud provider's CLI (and the compute platform's CLI, if any). Without access, the run continues and marks the affected facts as unverified.
- The `Agent` tool for the drafting subagents. Without it, the run drafts the plans itself.

## Origin

Tested on a serverless AWS project with one environment.

## Invocation

`disable-model-invocation: true`: the skill runs only as `/disaster-recovery-plan`. A run starts several subagents and reads the live cloud, so a passing question about region failure must not start one.
