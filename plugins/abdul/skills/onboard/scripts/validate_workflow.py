#!/usr/bin/env python3
"""Validate a .agents/workflow.json against schema v1.

Usage:
    validate_workflow.py <workflow.json> [--repo <repo-root>]

Prints one line per problem ("ERROR ..." / "WARN ...") and a final verdict.
Exit code 0 when there are no errors (warnings allowed), 1 otherwise, 2 on bad usage.
With --repo, also checks that owned paths and files.* entries exist.
Standard library only; runs on Python 3.9+.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, List

SCHEMA_VERSION = 1
TOP_LEVEL = [
    "schemaVersion", "project", "architecture", "commands", "testing", "squads",
    "roles", "hardRules", "git", "providers", "files",
]
SIZES = {"solo", "team", "full"}
PLATFORMS = {"flutter", "android", "ios", "react-native", "web", "other"}
POLICIES = {"every-change", "new-features", "optional", "none"}
REQUIRED_POLICIES = {"every-change", "new-features"}
TEST_LEVELS = ["unit", "integration", "e2e"]
GATE_SCOPES = {"full", "affected"}
REVIEWERS = {"architecture", "tests", "design-system", "l10n", "security", "accessibility"}
GIT_HOSTS = {"github", "gitlab", "bitbucket", "other", "none"}
BRANCHING = {"trunk", "feature-branch", "gitflow"}
PROVIDERS = {"claude", "codex", "cursor", "gemini", "copilot"}
OPTIONAL_COMMANDS = ["install", "format", "lint", "test", "build", "run"]
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Report:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"WARN  {where}: {msg}")


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _str_or_null(r: Report, where: str, v: Any) -> None:
    if v is not None and not isinstance(v, str):
        r.error(where, "must be a string or null")


def _str_list(r: Report, where: str, v: Any, allow_empty: bool = True) -> bool:
    if not isinstance(v, list) or not all(_is_str(x) for x in v):
        r.error(where, "must be a list of non-empty strings")
        return False
    if not allow_empty and not v:
        r.error(where, "must not be empty")
        return False
    return True


def _bool(r: Report, where: str, v: Any) -> None:
    if not isinstance(v, bool):
        r.error(where, "must be true or false")


def _rel_path(r: Report, where: str, p: str) -> bool:
    norm = p.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        r.error(where, f"'{p}' must be repo-relative, not absolute")
        return False
    if ".." in norm.split("/"):
        r.error(where, f"'{p}' must not contain '..'")
        return False
    return True


def _norm(p: str) -> str:
    p = p.replace("\\", "/").strip("/")
    while p.startswith("./"):
        p = p[2:]
    return p or "."


def _obj(r: Report, data: dict, key: str) -> dict:
    v = data.get(key)
    if not isinstance(v, dict):
        r.error(key, "must be an object")
        return {}
    return v


def check_project(r: Report, data: dict) -> None:
    p = _obj(r, data, "project")
    if not p:
        return
    if not _is_str(p.get("name")):
        r.error("project.name", "must be a non-empty string")
    if p.get("size") not in SIZES:
        r.error("project.size", f"must be one of {sorted(SIZES)}")
    plats = p.get("platforms")
    if not isinstance(plats, list) or not plats:
        r.error("project.platforms", "must be a non-empty list")
        return
    primaries = 0
    for i, pl in enumerate(plats):
        w = f"project.platforms[{i}]"
        if not isinstance(pl, dict):
            r.error(w, "must be an object")
            continue
        if pl.get("id") not in PLATFORMS:
            r.error(f"{w}.id", f"must be one of {sorted(PLATFORMS)}")
        root = pl.get("root")
        if not _is_str(root):
            r.error(f"{w}.root", "must be a non-empty string ('.' for the repo root)")
        else:
            _rel_path(r, f"{w}.root", root)
        if not isinstance(pl.get("primary"), bool):
            r.error(f"{w}.primary", "must be true or false")
        elif pl["primary"]:
            primaries += 1
    if primaries != 1:
        r.error("project.platforms", f"exactly one platform must be primary (found {primaries})")


def check_architecture(r: Report, data: dict) -> None:
    a = _obj(r, data, "architecture")
    if not a:
        return
    if not _is_str(a.get("style")):
        r.error("architecture.style", "must be a non-empty string")
    for k in ("stateManagement", "di", "notes"):
        _str_list(r, f"architecture.{k}", a.get(k))


def check_commands(r: Report, data: dict) -> None:
    c = _obj(r, data, "commands")
    if not c:
        return
    if not _is_str(c.get("gate")):
        r.error("commands.gate", "is required: the command that must pass before every commit")
    if c.get("gateScope") not in GATE_SCOPES:
        r.error("commands.gateScope", f"must be one of {sorted(GATE_SCOPES)}")
    for k in OPTIONAL_COMMANDS:
        _str_or_null(r, f"commands.{k}", c.get(k))


def check_testing(r: Report, data: dict) -> None:
    t = _obj(r, data, "testing")
    if not t:
        return
    for level in TEST_LEVELS:
        w = f"testing.{level}"
        lv = t.get(level)
        if not isinstance(lv, dict):
            r.error(w, "is required and must be an object")
            continue
        policy = lv.get("policy")
        if policy not in POLICIES:
            r.error(f"{w}.policy", f"must be one of {sorted(POLICIES)}")
        for k in ("tool", "location", "command"):
            _str_or_null(r, f"{w}.{k}", lv.get(k))
        if policy in REQUIRED_POLICIES and not _is_str(lv.get("tool")):
            r.error(f"{w}.tool", f"policy '{policy}' needs a tool")
        if not _is_str(lv.get("meaning")):
            r.error(f"{w}.meaning", "must say what this level means on this platform")


def check_squads(r: Report, data: dict, size: Any) -> None:
    squads = data.get("squads")
    if not isinstance(squads, list):
        r.error("squads", "must be a list (empty is allowed)")
        return
    if size == "full" and not squads:
        r.warn("squads", "size 'full' with no squads yet — add them with /add-squad")
    seen_ids = set()
    owners = {}  # normalised path -> squad id
    for i, s in enumerate(squads):
        w = f"squads[{i}]"
        if not isinstance(s, dict):
            r.error(w, "must be an object")
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not KEBAB.match(sid):
            r.error(f"{w}.id", "must be kebab-case, e.g. 'wallet-squad'")
        elif sid in seen_ids:
            r.error(f"{w}.id", f"duplicate squad id '{sid}'")
        else:
            seen_ids.add(sid)
        if not _is_str(s.get("description")):
            r.error(f"{w}.description", "must be a non-empty string")
        _str_list(r, f"{w}.tasks", s.get("tasks"))
        owns = s.get("owns")
        if not _str_list(r, f"{w}.owns", owns, allow_empty=False):
            continue
        for p in owns:
            if not _rel_path(r, f"{w}.owns", p):
                continue
            n = _norm(p)
            if n in owners and owners[n] != sid:
                r.error(f"{w}.owns", f"'{p}' is already owned by '{owners[n]}'")
                continue
            for other, other_id in owners.items():
                if other_id == sid:
                    continue
                if n.startswith(other + "/") or other.startswith(n + "/"):
                    r.warn(f"{w}.owns", f"'{p}' nests with '{other}' owned by '{other_id}'")
            owners[n] = sid


def check_roles(r: Report, data: dict) -> None:
    ro = _obj(r, data, "roles")
    if not ro:
        return
    for k in ("techLead", "ba", "qaLead"):
        _bool(r, f"roles.{k}", ro.get(k))
    rv = ro.get("reviewers")
    if _str_list(r, "roles.reviewers", rv):
        bad = [x for x in rv if x not in REVIEWERS]
        if bad:
            r.error("roles.reviewers", f"unknown {bad}; allowed {sorted(REVIEWERS)}")
    agents = ro.get("reviewerAgents")
    if agents is None:
        return
    if not isinstance(agents, dict):
        r.error("roles.reviewerAgents", "must be an object mapping a reviewer focus to an agent name")
        return
    for focus, name in agents.items():
        if not isinstance(rv, list) or focus not in rv:
            r.error("roles.reviewerAgents", f"'{focus}' is not listed in roles.reviewers")
        if not isinstance(name, str) or not KEBAB.match(name):
            r.error(f"roles.reviewerAgents.{focus}", "must be a kebab-case agent name, e.g. 'arch-reviewer'")


def check_git(r: Report, data: dict) -> None:
    g = _obj(r, data, "git")
    if not g:
        return
    if g.get("host") not in GIT_HOSTS:
        r.error("git.host", f"must be one of {sorted(GIT_HOSTS)}")
    if not _is_str(g.get("baseBranch")):
        r.error("git.baseBranch", "must be a non-empty string")
    if g.get("branching") not in BRANCHING:
        r.error("git.branching", f"must be one of {sorted(BRANCHING)}")
    for k in ("worktreePerTask", "askBeforeCommit", "askBeforePush"):
        _bool(r, f"git.{k}", g.get(k))


def check_providers(r: Report, data: dict) -> None:
    pv = data.get("providers")
    if not _str_list(r, "providers", pv, allow_empty=False):
        return
    bad = [x for x in pv if x not in PROVIDERS]
    if bad:
        r.error("providers", f"unknown {bad}; allowed {sorted(PROVIDERS)}")
    if len(set(pv)) != len(pv):
        r.error("providers", "contains duplicates")


def check_files(r: Report, data: dict) -> None:
    f = _obj(r, data, "files")
    if not f:
        return
    if not _is_str(f.get("rules")):
        r.error("files.rules", "must name the rules file, e.g. 'AGENTS.md'")
    else:
        _rel_path(r, "files.rules", f["rules"])
    for k in ("ownership", "agentsDir", "skillsDir"):
        v = f.get(k)
        _str_or_null(r, f"files.{k}", v)
        if isinstance(v, str) and v:
            _rel_path(r, f"files.{k}", v)
    squads = data.get("squads")
    if isinstance(squads, list) and squads and not f.get("ownership"):
        r.warn("files.ownership", "squads exist but no ownership file is recorded")


def check_repo(r: Report, data: dict, repo: str) -> None:
    for i, s in enumerate(data.get("squads") or []):
        if not isinstance(s, dict):
            continue
        for p in s.get("owns") or []:
            if isinstance(p, str) and not os.path.exists(os.path.join(repo, p)):
                r.warn(f"squads[{i}].owns", f"'{p}' does not exist in {repo}")
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    for k in ("rules", "ownership", "agentsDir", "skillsDir"):
        v = files.get(k)
        if isinstance(v, str) and v and not os.path.exists(os.path.join(repo, v)):
            r.warn(f"files.{k}", f"'{v}' does not exist yet in {repo}")
    for i, pl in enumerate((data.get("project") or {}).get("platforms") or []):
        root = pl.get("root") if isinstance(pl, dict) else None
        if isinstance(root, str) and not os.path.isdir(os.path.join(repo, root)):
            r.error(f"project.platforms[{i}].root", f"'{root}' is not a folder in {repo}")
    check_drift(r, data, repo, files)


def _text(repo: str, rel: Any) -> str | None:
    """Text of a repo file, or of every .md file in a repo folder; None if missing."""
    if not isinstance(rel, str) or not rel:
        return None
    path = os.path.join(repo, rel)
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    if os.path.isdir(path):
        parts = []
        for name in sorted(os.listdir(path)):
            if name.endswith(".md") and os.path.isfile(os.path.join(path, name)):
                with open(os.path.join(path, name), encoding="utf-8", errors="replace") as fh:
                    parts.append(fh.read())
        return "\n".join(parts)
    return None


def check_drift(r: Report, data: dict, repo: str, files: dict) -> None:
    """workflow.json restates facts the prose files own; warn when the two disagree."""
    rules = _text(repo, files.get("rules"))
    gate = (data.get("commands") or {}).get("gate") if isinstance(data.get("commands"), dict) else None
    if rules is not None and _is_str(gate) and gate not in rules:
        r.warn("commands.gate", f"'{gate}' is not mentioned in {files.get('rules')} — the two may have drifted")
    ownership = _text(repo, files.get("ownership"))
    if ownership is not None:
        for i, s in enumerate(data.get("squads") or []):
            sid = s.get("id") if isinstance(s, dict) else None
            if isinstance(sid, str) and sid and sid not in ownership:
                r.warn(f"squads[{i}].id", f"'{sid}' is not mentioned in {files.get('ownership')} — the two may have drifted")
    agents_dir = files.get("agentsDir")
    if isinstance(agents_dir, str) and agents_dir and os.path.isdir(os.path.join(repo, agents_dir)):
        roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
        mapping = roles.get("reviewerAgents") if isinstance(roles.get("reviewerAgents"), dict) else {}
        for focus in roles.get("reviewers") or []:
            name = mapping.get(focus, f"{focus}-reviewer")
            if isinstance(name, str) and not os.path.isfile(os.path.join(repo, agents_dir, f"{name}.md")):
                r.warn("roles.reviewers", f"no agent file '{agents_dir}/{name}.md' for '{focus}' — "
                                          "set roles.reviewerAgents if it has another name")


def validate(data: Any, repo: str | None = None) -> Report:
    r = Report()
    if not isinstance(data, dict):
        r.error("(root)", "must be a JSON object")
        return r
    for k in TOP_LEVEL:
        if k not in data:
            r.error(k, "is missing")
    for k in data:
        if k not in TOP_LEVEL:
            r.warn(k, "unknown key (ignored by schema v1)")
    if data.get("schemaVersion") != SCHEMA_VERSION:
        r.error("schemaVersion", f"must be {SCHEMA_VERSION}")
    check_project(r, data)
    check_architecture(r, data)
    check_commands(r, data)
    check_testing(r, data)
    check_squads(r, data, (data.get("project") or {}).get("size") if isinstance(data.get("project"), dict) else None)
    check_roles(r, data)
    if not isinstance(data.get("hardRules"), list) or not all(_is_str(x) for x in data.get("hardRules") or []):
        if "hardRules" in data:
            r.error("hardRules", "must be a list of non-empty strings")
    check_git(r, data)
    check_providers(r, data)
    check_files(r, data)
    if repo:
        check_repo(r, data, repo)
    return r


def main(argv: List[str]) -> int:
    args = list(argv)
    repo = None
    if "--repo" in args:
        i = args.index("--repo")
        if i + 1 >= len(args):
            print("usage: validate_workflow.py <workflow.json> [--repo <repo-root>]", file=sys.stderr)
            return 2
        repo = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print("usage: validate_workflow.py <workflow.json> [--repo <repo-root>]", file=sys.stderr)
        return 2
    path = args[0]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"ERROR {path}: file not found")
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR {path}: invalid JSON — {e}")
        return 1
    rep = validate(data, repo)
    for line in rep.errors + rep.warnings:
        print(line)
    if rep.errors:
        print(f"FAILED: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
        return 1
    print(f"OK: schema v{SCHEMA_VERSION}, {len(rep.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
