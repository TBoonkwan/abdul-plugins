# abdul

Set up a frontend repo's AI workflow by interview instead of copying another
project's rules. Works for Flutter and native Android today; iOS, React Native and web
are detected but have no pre-filled options yet.

## Skills

| Skill | What it does |
|---|---|
| `/abdul:onboard` | Detects the stack, interviews the team (architecture, squads, unit/integration/e2e policy, git, AI tools) and writes `AGENTS.md`, `.agents/workflow.json` and per-tool files |
| `/abdul:add-squad` | Adds a feature-owner squad after onboarding |

Both accept `dry-run`: everything up to the file plan, nothing written. Both are
user-invoked only (`disable-model-invocation`), so they add nothing to the context of
sessions that don't use them.

## Modes

`onboard` picks one from what's already in the repo:

| Mode | Repo has | Writes |
|---|---|---|
| fresh | no app code | everything |
| adopt | code, no AI-workflow files | everything |
| migrate | `CLAUDE.md` / `AGENTS.md` / agents / skills already | `workflow.json` + missing files; existing files only with a per-file OK |
| update | `.agents/workflow.json` | only the sections you choose |

## Provider support

`AGENTS.md` is the main rules file. Claude Code gets `CLAUDE.md` (`@AGENTS.md` import)
and `.claude/agents/`; Gemini gets `GEMINI.md`; Cursor `.cursor/rules/agents.mdc`;
Copilot `.github/copilot-instructions.md`; Codex reads `AGENTS.md` directly.

The plugin itself installs in Claude Code. For other tools, copy `skills/onboard/`
and `skills/add-squad/` into the repo's `.agents/skills/` — they use only
`python3` and plain Markdown.

## Layout

```
skills/onboard/
├── SKILL.md
├── reference/   questions.md · outputs.md · workflow-schema.md · example.workflow.json
├── scripts/     detect.py (read-only scan) · validate_workflow.py (schema v1 check)
└── templates/   AGENTS.md / OWNERSHIP.md · agents/ · pointers/ · platforms/{flutter,android}.md
skills/add-squad/SKILL.md
```

## Not in v1

Generic `/delegate`, `/wrap-up`, `/review` skills; hooks (commit gate, push guard);
templates for iOS, React Native and web; questions about design system, localization,
API/mock server, environments, accessibility, performance budgets, model per role.
