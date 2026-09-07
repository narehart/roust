# Shared agent configuration

This project uses [Rulesync](https://github.com/dyoshikawa/rulesync), pinned in
`package.json`, to translate shared configuration into native harness files.
The canonical source directory is `.rulesync/`; `.agents/` contains supporting
project context and Codex's generated skills. Edit the source, then regenerate.

## Commands

```sh
npm ci
npm run agents:preview       # inspect generated changes without writing
npm run agents:sync          # generate Claude Code and Codex configuration
npm run agents:check         # fail if generated files differ from the source
npm run agents:watch         # regenerate when shared source files change
```

`rulesync.jsonc` selects targets and features. Add another supported target
there to generate its native files as well. Features and lifecycle events vary;
inspect generation warnings when adding a target. Codex project commands are
omitted because Rulesync supports Codex commands only in global mode; use
skills for project workflows.

## What to edit

| Shared source | Purpose |
| --- | --- |
| `.rulesync/rules/project.md` | Instructions; generates root `AGENTS.md` and `CLAUDE.md` |
| `.rulesync/rules/*.md` | Additional rules, with scopes and target metadata |
| `.rulesync/skills/<name>/SKILL.md` | Skills, with scripts and references beside each skill |
| `.rulesync/subagents/<name>.md` | Subagent instructions and per-harness options |
| `.rulesync/hooks.jsonc` | Canonical lifecycle events and per-harness overrides |
| `.rulesync/hooks/` | Scripts referenced by hook commands |
| `.rulesync/commands/*.md` | Commands for harnesses with project command support |
| `.rulesync/mcp.jsonc` | MCP server configuration |
| `.rulesync/permissions.jsonc` | Explicitly authored portable permissions |
| `.agents/memory/` | Optional project notes; `MEMORY.md` is the index |

Create optional directories and files when adding real content. This checkout
had no project rules, skills, subagents, or hooks to import; the initial rule
was assembled from the repository's documentation and CI. User-wide Claude
skills and external Claude project memory have not been copied into this repo.

## Importing existing configuration

```sh
# Writes shared source files: review their diff before generating.
npm run agents:import:claude
npm run agents:preview
npm run agents:sync
```

Import is an explicit operation, not a two-way background merge. Once migrated,
edit `.rulesync/` rather than generated files. Importing changes from multiple
harnesses can overwrite the same source; review each import separately.

Machine-local permissions are excluded from the import shortcut. Author shared
permissions deliberately if needed. Existing `.claude/settings.local.json` and
`.claude/worktrees/` remain local harness state. Rulesync does not migrate
conversation history, automatic memory, or worktree bookkeeping.

Hooks and subagents are translated, not identical runtimes: tool names, event
payloads, model settings, and supported hook types can differ. Use target-specific
blocks for differences, and validate hooks in each installed harness before
relying on them. A generated file alone does not prove runtime compatibility.

Commit generated project files alongside shared sources so a fresh checkout is
usable before running npm. `agents:check` detects drift. Generation uses
`delete: false` to preserve unrelated configuration; after renaming or removing
a source, review and remove its obsolete generated files explicitly. Do not use
a blanket `--delete` against a mixed hand-written/generated setup.

References: [supported tools](https://github.com/dyoshikawa/rulesync/blob/main/docs/reference/supported-tools.md),
[file formats](https://github.com/dyoshikawa/rulesync/blob/main/docs/reference/file-formats.md),
and [CLI commands](https://github.com/dyoshikawa/rulesync/blob/main/docs/reference/cli-commands.md).
