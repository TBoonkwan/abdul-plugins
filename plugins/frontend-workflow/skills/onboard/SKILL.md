---
name: onboard
description: Set up (or update) a frontend repo's AI workflow — detect the stack, interview the team about architecture, feature-owner squads, which tests are required and which AI tools they use, then write AGENTS.md, .agents/workflow.json and per-tool files. Works for Flutter, native Android/iOS, React Native and web. Run it as "onboard" or "onboard dry-run".
disable-model-invocation: true
---

# Onboard a project

Turn a repo into one with a written, provider-neutral AI workflow. Everything this
skill learns goes into `.agents/workflow.json` (schema:
[reference/workflow-schema.md](reference/workflow-schema.md)); every other workflow
skill reads that file instead of assuming a stack.

Paths below are relative to this skill's folder. In Claude Code that folder is
`${CLAUDE_PLUGIN_ROOT}/skills/onboard`; in other tools, the folder holding this file.

## Ground rules

- **Dry run** (the user said "dry-run", "dry run" or "preview"): do every step up to
  the file plan, print the would-be `workflow.json` and file list, and **write nothing**.
- **Never overwrite** an existing file without a per-file OK. Migrate mode adds; it
  does not replace.
- **Never commit or push.** Leave changes in the working tree and say so.
- **Follow the repo's own rules first.** If its `CLAUDE.md`/`AGENTS.md` demands a branch,
  worktree or check before edits, do that before writing.
- **Ask, don't assume.** Detection pre-fills answers; the user confirms them. Put the
  detected or recommended option first, marked "(Recommended)" or "(detected)".
- **Ask in rounds** of at most 4 questions. Use the runtime's question tool when it has
  one; otherwise ask in plain chat, one round per message.
- No secrets, tokens, internal hostnames or credentials in any generated file.
- **Run the scripts; don't read their source.** Their usage and output fields are
  described here and in the reference files.

## Step 1 — Detect (no questions yet)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/detect.py" .
```

Output fields: `mode`, `aiFiles`, `providers` (AI tools already set up, with the files
as evidence), `platforms[]` (`id`, `root`, `primary`, `evidence`, `sourceFiles`,
`libraries` by category, `featureAreas`, `modules` for Gradle, `testFolders`,
`toolchain`), `gateCandidates`, `git` (`host`, `baseBranch`, `baseBranchCandidates`,
`currentBranch`) and `notes`.

Show the user a short table: mode, platforms (root, primary, main libraries), feature
areas count, test folders, gate candidates, AI tools found, git host/base branch, and
every entry in `notes`.

Then load the template for each detected platform from `templates/platforms/`
(`flutter.md`, `android.md`). A platform without a template (iOS, React Native, web in
v1): say so, and ask its questions without pre-filled options.

## Step 2 — Pick the mode

| `mode` | Meaning | What this run may write |
|---|---|---|
| `fresh` | No app code | Everything in the file plan |
| `adopt` | Code, no AI-workflow files | Everything in the file plan |
| `migrate` | AI-workflow files already exist | `.agents/workflow.json`, plus files that don't exist yet; existing files only with a per-file OK |
| `update` | `.agents/workflow.json` exists | Ask what to change; touch only those parts |

**Migrate:** before the interview, read the existing files (`CLAUDE.md`, `AGENTS.md`,
agent/role files, skills, ownership maps, the gate script). Pre-fill every answer you
can from them, and set `files.*` to where things already live (for example
`files.rules = "CLAUDE.md"` when that is the canonical rules file). Then ask only what
the files don't answer. In this mode:

- `hardRules` is an **index**: one line per existing rule that names where the full
  rule lives — never a condensed rewrite that drops its exceptions.
- Keep squad ids and agent names exactly as the repo has them. Map reviewers whose
  agents aren't called `<focus>-reviewer` in `roles.reviewerAgents`.
- Owned paths must be real repo-relative paths, even when the existing ownership map
  writes them shorter (e.g. `features/auth` → `lib/features/auth`).
- After validating, treat every drift warning (gate, squad id, reviewer agent not
  found in the prose files) as a question for the user, not something to silence.

**Update:** load the current `workflow.json`, show it as a short summary, and ask which
sections to revisit. Skip the other rounds.

## Step 3 — Interview

Run the rounds in [reference/questions.md](reference/questions.md). Skip a round
when detection or migrate-mode reading already answers it with certainty — but show
the answer so the user can correct it.

## Step 4 — Build and validate `workflow.json`

Assemble the answers into schema v1. Save to a scratch path first (dry run: never
inside the repo):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/validate_workflow.py" <scratch>/workflow.json --repo .
```

Fix every `ERROR`. Show `WARN` lines to the user and ask whether to keep them.

## Step 5 — File plan and confirmation

Work out the files from [reference/outputs.md](reference/outputs.md). Show one table:
path · create / update / skip · why. For each file that already exists, show the
proposed change as a diff and ask for an OK per file.

Dry run stops here: print the `workflow.json` and the table, say "dry run — nothing
written", and end.

## Step 6 — Write

Write the confirmed files from the templates in `templates/`. Fill every
`{{placeholder}}`; delete template sections that don't apply (for example the squads
section when there are none). Keep generated files short — rules, not essays.

Validate again against the repo:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/validate_workflow.py" .agents/workflow.json --repo .
```

## Step 7 — Report

- Files created / updated / skipped (with paths)
- Answers the user should double-check (anything inferred, not confirmed)
- Next steps: review the diff, commit when ready, `/add-squad` for later squads,
  re-run `onboard` to change answers
