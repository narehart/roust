# Canonical agent configuration

Edit shared rules, skills, subagents, hooks, commands, MCP, and permissions here.
Run `npm run agents:preview`, then `npm run agents:sync` to update harness files.
See [the agent configuration guide](../.agents/README.md) for source paths,
imports, target selection, and portability limits.

Only `rules/` is populated initially: no project-local skill, hook, or subagent
configuration existed to migrate. Add optional sources when needed rather than
installing placeholder behaviors into the harnesses.
