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

## 3. Skills as First-Class Citizens
In the AWOS Recruitment ecosystem, the delivery of *skills* is prioritized over static agent personas. 
* **Actionable Knowledge:** Skills contain the actual, concrete instructions, code standards, and workflows. 
* **Future-Proofing:** With the introduction of features like Claude Code Teams, where agents are generated dynamically on the fly, static agent files become less relevant. By focusing our hiring process on robust, highly specific skills, we ensure that no matter how the agent team is formed, they have the exact knowledge required to execute the task.

## 4. Dynamic Discovery via MCP
We utilize a remote Model Context Protocol (MCP) server as the intelligent discovery layer for the hiring process. 
Instead of hardcoding tool availability into the client, the remote MCP server abstracts the complexity of searching and matching the right tools. It provides a curated catalog, while the actual decision-making is delegated to Claude Code. Knowing the current tech stack and the task at hand, the LLM is perfectly capable of selecting the precise tools it needs. This architecture also allows us to easily expand the MCP server's knowledge and integrate execution feedback in the future.

## 5. Actionable Tools for True Autonomy
True agent autonomy means the AI shouldn't just write code—it must be able to run it, test it, and fix early mistakes without constantly distracting the developer. 
To achieve this, recruited agents need access to their environment (browsers, system logs, infrastructure, databases). Therefore, alongside delivering cognitive skills, the AWOS `hire` process provisions the preferred local MCP servers, giving the AI the hands it needs to interact with the real world safely and autonomously.

## 6. The Provectus Standard
Every skill, agent configuration, and MCP server available through the AWOS Recruitment registry is a curated asset maintained by Provectus experts. 
This is not a random collection of community prompts. It is the codified representation of our engineering standards. When you use `/awos:hire`, you are provisioning the exact methodologies, workflows, and code quality standards that we use in production.
