# AWOS Recruitment Philosophy

**Why "Recruitment"?** In the real world of software engineering, when a new project or feature kicks off, you don't just assign a generic, unstructured pool of developers to it. You analyze the technical requirements and *recruit* specific specialists—a database expert, a frontend engineer, a security auditor—who possess the exact skills needed to get the job done right. AWOS Recruitment applies this exact paradigm to AI. Instead of relying on a monolithic, "know-it-all" AI assistant, we dynamically recruit specialized AI agents, skills, and tools tailored precisely to your project's current architectural needs.

While the broader AWOS framework provides a spec-driven SDLC designed to achieve high AI autonomy, the manual assembly of agents, skills, and infrastructure for each specific task remains a slow, brittle, and inconvenient bottleneck. **AWOS Recruitment** is the subsystem built to solve this. It acts as a dynamic provisioning engine for AI capabilities. 

This document outlines the core principles guiding the architecture of our AI recruitment and discovery process.

## 1. The Repository is the Single Source of Truth
When the Recruitment system "hires" an AI team, all resulting skills, MCP tools, agent prompts, and Claude Code configurations are delivered directly into the project repository. 
* **Consistency:** Code generation should never depend on the local state of a specific developer's machine. 
* **Evolution:** As architectural requirements change, the AI's instructions must evolve alongside the codebase. Storing these recruited assets in Git ensures that any updates to AI capabilities are instantly and simultaneously available to every developer on the team.

## 2. Context Isolation
Modern LLMs suffer from context bloat. Giving an AI agent access to every framework, database, and tool simultaneously increases the risk of hallucinations, dilutes its focus, and drives up token costs. 
AWOS Recruitment operates as a strict filter. By dynamically provisioning only the specific skills required for the current architectural specification, we keep the AI on a strict "information diet." This guarantees laser focus and high-fidelity output for the task at hand.

## 3. Skills Carry Knowledge, Agents Carry Orchestration
Skills and agents serve fundamentally different purposes in the AWOS Recruitment ecosystem.

**Skills** are small, focused knowledge pieces — best practices, code examples, and standards for a specific language, library, framework, or database. The general-purpose agent is sufficient for most coding tasks; skills are how you fine-tune its output within your standards. A Python skill teaches idiomatic patterns, a Terraform skill enforces module conventions, a ChromaDB skill provides up-to-date API usage. Skills carry the *what* — the concrete knowledge the AI needs to write better code.

**Agents** play an infrastructure role. They exist for context management, parallel processing, and behavioral constraints — not for carrying domain knowledge. An agent's system prompt defines *how* it should operate: what it can and cannot do, how it interacts with the codebase, and what boundaries it must respect. For example, a tester agent might be restricted from reading source code so it remains unbiased and tests only through the public interface.

### Terms

The registry uses three terms. One word, one meaning.

- A **reference skill** holds the knowledge of one technology: patterns, conventions, examples. An agent that lists it reads it before work. Name it by the technology: `react-best-practices`, `typescript-development`, `postgres-best-practices`.
- A **task skill** holds a procedure with scripts. An agent runs it as a step. Name it by the action: `verify-ui`, `pr-review`, `gha-diagnosis`.
- An **agent** is a container for a role. The front matter sets the model, the effort, the tool bounds, and the `skills:` list. The body sets the role, its scope, and its behavior rules. The knowledge comes from the skills in the list, not from the body. Name it by the role and its main stack: `python-backend`, `terraform-aws`, `react-frontend`.

Do not name a skill or an agent `*-expert`. The suffix hides what the thing is. A skill is named by what it teaches. An agent is named by what it owns.

This separation keeps the registry clean and composable. Skills are reusable across any agent configuration. Agents are lightweight orchestration wrappers that reference the skills they need. As features like Claude Code Teams evolve — where agents are generated dynamically — this distinction becomes even more important: the knowledge lives in skills, and any agent can pick up exactly what it needs.

## 4. Dynamic Discovery via MCP
We utilize a remote Model Context Protocol (MCP) server as the intelligent discovery layer for the hiring process. 
Instead of hardcoding tool availability into the client, the remote MCP server abstracts the complexity of searching and matching the right tools. It provides a curated catalog, while the actual decision-making is delegated to Claude Code. Knowing the current tech stack and the task at hand, the LLM is perfectly capable of selecting the precise tools it needs. This architecture also allows us to easily expand the MCP server's knowledge and integrate execution feedback in the future.

## 5. Actionable Tools for True Autonomy
True agent autonomy means the AI shouldn't just write code—it must be able to run it, test it, and fix early mistakes without constantly distracting the developer. 
To achieve this, recruited agents need access to their environment (browsers, system logs, infrastructure, databases). Therefore, alongside delivering cognitive skills, the AWOS `hire` process provisions the preferred local MCP servers, giving the AI the hands it needs to interact with the real world safely and autonomously.

## 6. The Provectus Standard
Every skill, agent configuration, and MCP server available through the AWOS Recruitment registry is a curated asset maintained by Provectus experts. 
This is not a random collection of community prompts. It is the codified representation of our engineering standards. When you use `/awos:hire`, you are provisioning the exact methodologies, workflows, and code quality standards that we use in production.
