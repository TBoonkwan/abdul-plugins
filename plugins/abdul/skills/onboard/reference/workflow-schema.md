# `.agents/workflow.json` — schema v1

The one file every workflow skill reads. `/onboard` writes it; `/add-squad` and a
re-run of `/onboard` update it. Validate after every write:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/onboard/scripts/validate_workflow.py" .agents/workflow.json --repo .
```

A full example: [example.workflow.json](example.workflow.json).

## Top level

| Key | Type | Notes |
|---|---|---|
| `schemaVersion` | `1` | Bump only with a migration note in this file |
| `project` | object | Name, workflow size, platforms |
| `architecture` | object | Style, state management, DI, notes |
| `commands` | object | Install/lint/test/build/run and the **gate** |
| `testing` | object | `unit`, `integration`, `e2e` — each a test level |
| `squads` | array | Feature owners; may be empty ("create later", or `solo`) |
| `roles` | object | Lead roles and reviewers to generate |
| `hardRules` | array of strings | Non-negotiables, one sentence each |
| `git` | object | Host, base branch, branching model, authority |
| `providers` | array | AI tools the repo supports |
| `files` | object | Where the workflow files actually live in this repo |

## `project`

| Key | Type | Values |
|---|---|---|
| `name` | string | Short repo/app name |
| `size` | enum | `solo` (one dev, no squads/leads) · `team` (squads + reviewers) · `full` (squads + tech-lead/BA/QA lead + reviewers) |
| `platforms` | array, ≥1 | `{ "id", "root", "primary" }` — exactly one `primary: true` |

`id`: `flutter` · `android` · `ios` · `react-native` · `web` · `other`.
`root`: repo-relative folder of that platform's project (`.` for the repo root). A
Flutter module inside a native app is its own platform entry with its own root.

## `architecture`

| Key | Type | Example |
|---|---|---|
| `style` | string | `clean-feature-first`, `mvvm`, `mvi`, `layered`, or free text |
| `stateManagement` | array of strings | `["bloc"]`, `["rxjava", "coroutines"]` |
| `di` | array of strings | `["get_it", "injectable"]`, `["koin"]` |
| `notes` | array of strings | Layer rules in one line each, e.g. `presentation → domain only` |

## `commands`

`install`, `format`, `lint`, `test`, `build`, `run`: string or `null`.
`gate` (required): the one command that must pass before every commit.
`gateScope`: `full` (whole suite every time) or `affected` (only changed modules/packages).

## `testing`

Three keys — `unit`, `integration`, `e2e` — each:

| Key | Type | Notes |
|---|---|---|
| `policy` | enum | `every-change` · `new-features` · `optional` · `none` |
| `tool` | string or null | Required when policy is `every-change` or `new-features` |
| `location` | string or null | Folder, e.g. `test/`, `src/androidTest/` |
| `command` | string or null | How to run this level alone |
| `meaning` | string | What this level means **on this platform** — the words differ (Flutter `integration_test` drives the whole app; on Android "integration" usually means Robolectric or instrumented tests of one screen) |

## `squads[]`

| Key | Type | Notes |
|---|---|---|
| `id` | kebab-case string | Unique, ends in `-squad` by convention |
| `owns` | array of paths, ≥1 | Repo-relative folders. A Gradle module `:features:wallet` is owned as `features/wallet`. No `..`, no leading `/`. Two squads never own the same path |
| `description` | string | One line |
| `tasks` | array of strings | Typical tasks — used to route work |

## `roles`

`techLead`, `ba`, `qaLead`: booleans. `reviewers`: subset of
`architecture` · `tests` · `design-system` · `l10n` · `security` · `accessibility`.

`reviewerAgents` (optional): maps a reviewer focus to its agent's name when it isn't
`<focus>-reviewer`, e.g. `{ "architecture": "arch-reviewer", "design-system": "ds-guardian" }`.
Every key must be listed in `reviewers`.

## `git`

| Key | Type | Values |
|---|---|---|
| `host` | enum | `github` · `gitlab` · `bitbucket` · `other` · `none` |
| `baseBranch` | string | e.g. `develop`, `main` |
| `branching` | enum | `trunk` · `feature-branch` · `gitflow` |
| `worktreePerTask` | boolean | Each task edits in its own git worktree |
| `askBeforeCommit` | boolean | |
| `askBeforePush` | boolean | |

## `hardRules`

One sentence each. When `files.rules` is an existing, richer file (migrate mode),
these are an **index, not a copy**: one line per rule that names where the full rule
lives, e.g. `"HR2 Tests are mandatory — exemptions in CLAUDE.md"`. The prose file
stays authoritative; skills read `files.rules` for the detail.

## `providers`

Non-empty subset of `claude` · `codex` · `cursor` · `gemini` · `copilot`.

## `files`

Where things live, so skills find them without assuming a layout. In migrate mode
these point at the files the repo already had.

| Key | Type | Default (fresh/adopt) |
|---|---|---|
| `rules` | string | `AGENTS.md` |
| `ownership` | string or null | `.agents/OWNERSHIP.md` (`null` when there are no squads) |
| `agentsDir` | string or null | `.claude/agents` when `claude` is a provider |
| `skillsDir` | string or null | `.agents/skills` if the repo has its own skills |

**Which file wins:** `files.rules` and `files.ownership` are authoritative for prose
rules and ownership; `workflow.json` is the machine-readable summary. With `--repo`,
the validator warns when they drift: the gate command missing from `files.rules`, a
squad id missing from `files.ownership`, or a reviewer with no agent file in
`files.agentsDir`.

## Migrations

- v1 (2026-11-02): first version. Optional `roles.reviewerAgents` added the same day,
  before any repo used v1 — no migration needed.
