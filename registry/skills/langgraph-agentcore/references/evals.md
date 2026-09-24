# Evaluations for langgraph-agentcore

Behaviour checks for **this skill**, not for agents built with it. Run them
after any change to SKILL.md or the reference files: give a fresh Claude
session the skill plus the prompt, and check the output against the bullets.

A bullet is a pass/fail claim about the produced code or plan, not a style
opinion. The point of the set is to catch the failure mode this skill exists to
prevent — plausible-looking AgentCore code that does not run, and pipelines
that skip a gate.

> Placement note: the registry bundler only ships `SKILL.md` and flat files
> under `references/` and `scripts/`, so these live here rather than in the
> `evals/evals.json` layout the skill-creator docs describe.

---

## Eval 1 — Fan-out pipeline with a confidence gate

**Prompt**

> I'm building a LangGraph pipeline that pulls a record from three sources in
> parallel, merges them, scores confidence on each field, and needs a human to
> sign off on anything below 0.6 before we write to the downstream system. The
> human sign-off comes back from a separate web app hours later. Sketch the
> graph for me.

**Expect**

- State declares the accumulated key with a reducer (`Annotated[list[...], add]`)
  and imports `add` from `operator` — no bare `add`.
- `Send` is imported from `langgraph.types`, not `langgraph.constants`.
- Uses `interrupt()` for the sign-off, not a polling loop or a `time.sleep`.
- Attaches a durable checkpointer (not `MemorySaver`) and says why: the gate
  outlives the session.
- Resumes with `Command(resume=...)` against the same `thread_id`.
- Does **not** claim a specific AgentCore session-length quota as fact.

**Fails if** it compiles the graph with `MemorySaver`, or hand-rolls a wait
loop instead of `interrupt()`.

---

## Eval 2 — Deploy an existing graph on AgentCore Runtime

**Prompt**

> I have a compiled LangGraph app in `agent.py`. What do I need to add to run
> it on Bedrock AgentCore Runtime, and how do I wire the Gateway Lambda tool it
> calls?

**Expect**

- Uses `BedrockAgentCoreApp` with an `@app.entrypoint` handler and `app.run()`.
  No `AgentCoreApp`, no `.serve()`.
- The entrypoint receives the invocation payload and calls the graph itself —
  it does not pass the compiled graph to the app constructor.
- CDK import is `aws_cdk.aws_bedrockagentcore` (one word), and the Lambda
  target goes through `add_lambda_target` with a `tool_schema`, not a generic
  `add_target(target_type="lambda")`.
- Binds tools with `bind_tools(...)`, never `invoke(..., tools=...)`.
- States a version for anything it pins rather than asserting an API is current.

**Fails if** any `bedrock_agentcore` or CDK symbol it writes does not exist in
the installed package.

---

## Eval 3 — Cost-aware model routing with fallback

**Prompt**

> Our extraction pipeline is too expensive. I want cheap models for the triage
> nodes and the expensive one only for the final reasoning step, and it has to
> keep working when a model gets throttled. How should I structure this?

**Expect**

- Node→tier mapping lives in configuration, not in Python literals.
- Model IDs are loaded from config, with an explicit note that Bedrock IDs
  carry version/date suffixes and cross-region profiles carry a `us.`/`eu.`/
  `apac.` prefix — no invented ID like `anthropic.claude-sonnet`.
- The fallback chain is implemented: it iterates candidates and raises on
  exhaustion. It does not return the primary with a "real implementation
  checks availability" comment.
- Carries over the rule that a high-stakes task must not silently degrade to a
  cheaper tier without explicit configuration.
- Mentions ordering cheap gates before expensive ones.

**Fails if** the routing function has a branch whose body is a TODO or a
comment deferring the logic.

---

## Eval 4 — Cedar rollout (negative check on repo-local leakage)

**Prompt**

> Add a CI step that validates our Cedar policies before we deploy the agent
> stack.

**Expect**

- Uses the Cedar CLI: `cedar validate --schema <file> --policies <file>`.
- Does not invent a project-specific command (in particular, not
  `just validate-registry`, which is this repository's capability-registry
  validator and has nothing to do with Cedar).
- Recommends deploying new policies in `LOG_ONLY` first and reviewing DENY
  decisions before `ENFORCE`.
