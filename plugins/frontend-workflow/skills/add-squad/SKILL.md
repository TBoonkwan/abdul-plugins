---
name: add-squad
description: Add a feature-owner squad to a repo already set up with onboard — asks which paths or modules it owns, checks nobody else owns them, then updates .agents/workflow.json, the ownership map and the Claude agent file. Run it as "add-squad" or "add-squad dry-run".
disable-model-invocation: true
---

# Add a squad

Needs `.agents/workflow.json` (written by `onboard`). If it's missing, stop and tell
the user to run `onboard` first.

Scripts and templates are shared with the onboard skill: in Claude Code,
`${CLAUDE_PLUGIN_ROOT}/skills/onboard/`; in other tools, the sibling `onboard/` folder.

**Dry run** ("dry-run", "preview"): show the changes as diffs and write nothing.
Never commit or push.

## Steps

1. **Read** `.agents/workflow.json`. Show the current squads (id → owns) and the
   feature areas nobody owns yet — run
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/detect.py" .` and compare its
   `featureAreas` with every squad's `owns`.
2. **Ask** (one round):
   - Squad name → id `<name>-squad`, kebab-case, unique
   - Which paths or modules it owns — offer the unowned feature areas first
     (multi-select). Gradle modules are stored as paths (`:features:x` → `features/x`).
   - One-line description and 2–5 typical tasks (draft them from the folder names; the
     user corrects)
3. **Check**: every path exists; no path is already owned by another squad. If one is,
   ask whether to move it (and remove it from the old squad) or drop it.
4. **Validate** the new `workflow.json` in a scratch copy first:
   `python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/validate_workflow.py" <scratch>/workflow.json --repo .`
   Fix every `ERROR`.
5. **Write** (after showing the diffs):
   - `.agents/workflow.json` — append the squad (and the moved paths, if any)
   - `files.ownership` — add the row and the `### <id>` line (template:
     `templates/OWNERSHIP.md.tmpl`); if `files.ownership` is `null`, create
     `.agents/OWNERSHIP.md` and set it
   - If `claude` is in `providers`: `<files.agentsDir>/<id>.md` from
     `templates/agents/squad.md.tmpl` (create `files.agentsDir`, default
     `.claude/agents`, if it's `null`)
   - If `project.size` is `solo`: ask to switch it to `team` first — solo projects have
     no squads
6. **Validate again** against the real file, then report the files changed.
