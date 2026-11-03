# dickjay-plugins

A Claude Code plugin marketplace.

| Plugin | Version | What it does |
|---|---|---|
| [frontend-workflow](plugins/frontend-workflow/) | 0.1.0 | Onboard a frontend repo to a provider-neutral AI workflow |

## Install

In a Claude Code session:

```
/plugin marketplace add TBoonkwan/claude-plugins
/plugin install frontend-workflow@dickjay-plugins
```

Or from a shell:

```bash
claude plugin marketplace add TBoonkwan/claude-plugins
claude plugin install frontend-workflow@dickjay-plugins
```

The name after `@` is the marketplace name (`dickjay-plugins`, from
`.claude-plugin/marketplace.json`), not the repo name. The repo is public, so no GitHub
login is needed. Updates arrive with `/plugin marketplace update dickjay-plugins`, or
automatically if you turn on auto-update for this marketplace in `/plugin` →
Marketplaces.

Installed at user scope, the plugin works in the terminal, the desktop app and the IDE
extensions.

## Use

In the repo you want to set up:

```
/frontend-workflow:onboard dry-run     # detect + interview, writes nothing
/frontend-workflow:onboard             # writes AGENTS.md, .agents/workflow.json, …
/frontend-workflow:add-squad           # later: add a feature-owner squad
```

Commit the generated files: teammates then get the workflow from the repo itself,
without installing the plugin. See [the plugin README](plugins/frontend-workflow/) for
modes, generated files and what v1 doesn't do yet.

## Try without installing

```bash
git clone https://github.com/TBoonkwan/claude-plugins.git
claude --plugin-dir ./claude-plugins/plugins/frontend-workflow
```

## Develop

```bash
python3 -m unittest discover -s tests -v       # script tests
claude plugin validate .                       # marketplace + plugin manifests
```

Release: bump `version` in the plugin's `.claude-plugin/plugin.json`, commit and push —
installed users only receive changes when it changes. Docs-only changes need no bump.
