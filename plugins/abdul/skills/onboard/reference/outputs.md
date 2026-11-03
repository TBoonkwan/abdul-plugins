# File plan

Which files `/onboard` writes, from which template, and when. In `migrate` mode a file
that already exists is never replaced: propose a diff and write only with a per-file OK.

## Always

| File | Template | Notes |
|---|---|---|
| `.agents/workflow.json` | — (built from the answers) | Validate with `scripts/validate_workflow.py` |
| `AGENTS.md` | `templates/AGENTS.md.tmpl` | The main rules file every tool reads. Migrate: if the repo's canonical rules live elsewhere (e.g. `CLAUDE.md`), don't create a second copy — set `files.rules` to that file and propose a short "Workflow config" section linking `.agents/workflow.json` |

## Squads (size `team` or `full`, and at least one squad)

| File | Template | Notes |
|---|---|---|
| `.agents/OWNERSHIP.md` | `templates/OWNERSHIP.md.tmpl` | Provider-neutral ownership map; `AGENTS.md` links it. Migrate: if the repo already has an ownership map, point `files.ownership` at it instead |

## Per AI tool

| Provider | Files | Template |
|---|---|---|
| `claude` | `CLAUDE.md` (imports `AGENTS.md`) | `templates/pointers/CLAUDE.md.tmpl` |
| | `.claude/agents/<squad-id>.md` per squad | `templates/agents/squad.md.tmpl` |
| | `.claude/agents/tech-lead.md`, `ba.md`, `qa-lead.md` when those roles are on | `templates/agents/lead.md.tmpl` |
| | `.claude/agents/<focus>-reviewer.md` per reviewer | `templates/agents/reviewer.md.tmpl` |
| `codex` | none — Codex reads `AGENTS.md` | — |
| `cursor` | `.cursor/rules/agents.mdc` | `templates/pointers/cursor-agents.mdc.tmpl` |
| `gemini` | `GEMINI.md` | `templates/pointers/GEMINI.md.tmpl` |
| `copilot` | `.github/copilot-instructions.md` | `templates/pointers/copilot-instructions.md.tmpl` |

Squads, leads and reviewers are described for every tool in `.agents/OWNERSHIP.md`;
only Claude gets separate agent files, because only its subagents load them.

## Set `files` to match

| Key | Value |
|---|---|
| `files.rules` | `AGENTS.md`, or the existing canonical rules file in migrate mode |
| `files.ownership` | `.agents/OWNERSHIP.md`, the existing map, or `null` with no squads |
| `files.agentsDir` | `.claude/agents` when `claude` is a provider, else `null` |
| `files.skillsDir` | `.agents/skills` if the repo already has its own skills, else `null` |

## Never

- Delete or rename existing files.
- Write outside the repo, or into `.git/`.
- Copy plugin skills into the repo (they're installed with the plugin).
