# dickjay-plugins

A Claude Code plugin marketplace.

| Plugin | Version | What it does |
|---|---|---|
| [frontend-workflow](plugins/frontend-workflow/) | 0.1.0 | Onboard a frontend repo to a provider-neutral AI workflow |

## Try a plugin locally (no install)

```bash
claude --plugin-dir ~/Documents/Workspace/AI/claude-plugins/plugins/frontend-workflow
```

Then, inside the session, in the repo you want to onboard:

```
/frontend-workflow:onboard dry-run
```

## Install from this marketplace

Local checkout:

```bash
claude plugin marketplace add ~/Documents/Workspace/AI/claude-plugins
claude plugin install frontend-workflow@dickjay-plugins
```

Once pushed to a git host, replace the path with `owner/repo` (GitHub) or the full
git URL (GitLab and others).

## Develop

```bash
python3 -m unittest discover -s tests -v       # script tests
claude plugin validate .                       # marketplace + plugin manifests
```

Release: bump `version` in the plugin's `.claude-plugin/plugin.json` — installed users
only receive changes when it changes.
