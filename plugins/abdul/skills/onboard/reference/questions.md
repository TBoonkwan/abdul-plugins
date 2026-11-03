# Interview rounds

At most 4 questions per round, 2–4 options per question (the user can always type
their own answer). Put the detected or recommended option first. Option lists come
from the platform template (`templates/platforms/<id>.md`); the ones here are the
fallback when there is no template.

Each round lists the `workflow.json` keys it fills.

## Round 1 — Project

| Question | Options | Fills |
|---|---|---|
| Which platforms are in scope, and which is primary? (multi-select) | Detected platforms first; "Other" for anything missed | `project.platforms` |
| Which architecture does the code follow? | From the primary platform's template, e.g. feature-first Clean · MVVM · MVI · Layered | `architecture.style`, `architecture.notes` |
| Which state management is allowed? (multi-select) | Detected libraries first, then the template's options | `architecture.stateManagement` |
| How big is the workflow? | **Solo** — one developer, no squads or leads · **Team** — squads + reviewers · **Full** — squads + tech-lead, BA, QA lead + reviewers | `project.size` |

Ask for DI only when detection found more than one DI library or none (fills
`architecture.di`). Add one free-text prompt for layer rules worth writing down
("presentation never imports data") → `architecture.notes`.

## Round 2 — Commands and the gate

Pre-fill from the template's default commands, the detected toolchain (fvm, Gradle
wrapper, package manager) and `gateCandidates` (read those files — a CI config or
check script usually shows the real commands).

| Question | Options | Fills |
|---|---|---|
| What must pass before every commit? | The gate script/CI command found · the template's default gate · "Write a gate script for me" | `commands.gate` |
| Run the whole suite every time, or only what changed? | Full · Affected modules/packages (recommend for > ~15 modules) | `commands.gateScope` |
| Are these the right lint / test / build / run commands? | Show them; Yes · Edit | `commands.*` |

If they pick "write a gate script", note it in the file plan as a follow-up; v1 does
not generate one.

## Round 3 — Tests

Tell the user what each level means **on this platform** first (the template's
"Test levels" table), because the same word means different things across platforms.

| Question | Options | Fills |
|---|---|---|
| Unit tests required? | Every change · New features only · Optional · Not now | `testing.unit.policy` |
| Integration tests required? | same | `testing.integration.policy` |
| E2E tests required? | same | `testing.e2e.policy` |
| Which tools? | Detected tools per level · template options | `testing.*.tool`, `location`, `command`, `meaning` |

A required level (every change / new features) needs a tool. If none is installed,
offer "Not now" or name the tool to adopt, and note it as a follow-up.

## Round 4 — Squads and roles (skip for Solo)

1. Show the detected feature areas (`featureAreas`; modules for Gradle, folders
   elsewhere) as a table with a **proposed** grouping into squads: related features
   together, shared/core code in a `core-squad`, roughly 2–6 squads. Name squads
   `<area>-squad`.
2. Ask: **Accept the grouping · Edit it · Create squads later**. On "Edit", take the
   user's changes in chat and show the table again.
3. Ask which lead roles to generate (multi-select): tech-lead · BA · QA lead — default
   on for Full, off for Team.
4. Ask which reviewers to generate (multi-select): architecture · tests ·
   design-system · l10n · security · accessibility — recommend architecture + tests.

Fills `squads`, `roles`. Each squad needs `owns` (paths), a one-line `description` and
a few `tasks`; draft them from folder names and ask the user to correct.

## Round 5 — Rules and git

| Question | Options | Fills |
|---|---|---|
| Any hard rules or banned libraries? | Suggestions from the template + detection (e.g. "No GetX" when GetX is absent but BLoC is used) · "None for now" · free text | `hardRules` |
| Which branching model? | Detected base branch with: Gitflow (develop + release) · Feature branches → main · Trunk | `git.branching`, `git.baseBranch` |
| Should each task use its own git worktree? | No (Recommended for Solo/Team) · Yes | `git.worktreePerTask` |
| Must the agent ask before commit and push? | Ask before both (Recommended) · Ask before push only · Never ask | `git.askBeforeCommit`, `git.askBeforePush` |

Confirm the git host when detection returned `other` (GitHub · GitLab · Bitbucket ·
Other) → `git.host`.

## Round 6 — AI tools

| Question | Options | Fills |
|---|---|---|
| Which AI coding tools does the team use? (multi-select) | Tools in detection's `providers` first, marked "(detected)", then the rest of Claude Code · Codex · Cursor · Gemini CLI · Copilot | `providers` |

`AGENTS.md` is always written as the main rules file; each tool gets a small pointer
file if it needs one (see `outputs.md`).
