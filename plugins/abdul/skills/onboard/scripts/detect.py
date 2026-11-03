#!/usr/bin/env python3
"""Detect a frontend repo's stack and existing AI-workflow files. Read-only.

Usage:
    detect.py [<repo-root>]          (defaults to the current folder)

Prints one JSON object to stdout:
    detectorVersion  1
    repo             absolute path scanned
    mode             fresh | adopt | migrate | update
                       fresh   = no app code found
                       adopt   = app code, no AI-workflow files
                       migrate = AI-workflow files exist (CLAUDE.md, AGENTS.md, agents, skills...)
                       update  = .agents/workflow.json already exists (re-run)
    aiFiles          AI-workflow files/folders found
    providers        AI tools those files belong to, with the files as evidence
    platforms[]      one per project root: id, root, primary, evidence, sourceFiles,
                     libraries (by category), featureAreas, modules (Gradle), testFolders,
                     toolchain
    gateCandidates   files that hint at the pre-commit gate (scripts, CI configs)
    git              host, hostname, baseBranch, baseBranchCandidates, currentBranch
    notes            things the interview should ask about

Standard library only; runs on Python 3.9+. Never writes anything.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

DETECTOR_VERSION = 1
MAX_DEPTH = 5

# Folders never scanned for code: build output, dependencies, VCS, worktrees, AI config.
PRUNE = {
    ".git", "build", ".dart_tool", "node_modules", "Pods", ".gradle", ".idea", ".vscode",
    "DerivedData", ".fvm", ".build", "dist", "out", ".next", ".nuxt", "coverage",
    ".claude", ".agents", ".cursor", ".worktrees", "worktrees", ".cxx", ".externalNativeBuild",
    "vendor", ".symlinks", "ephemeral", ".pub-cache", "generated", "__pycache__",
}
# Dot-folders that are still worth walking into.
ALLOWED_DOT_DIRS = {".github", ".maestro", ".husky"}

SOURCE_EXT = {
    ".dart": "dart", ".kt": "kotlin", ".kts": "kotlin", ".java": "java", ".swift": "swift",
    ".m": "objc", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".vue": "vue", ".svelte": "svelte",
}

AI_FILES = [
    "CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules",
    ".github/copilot-instructions.md",
]
AI_DIRS = [
    ".claude/agents", ".claude/skills", ".claude/commands", ".agents/skills", ".cursor/rules",
    ".codex/prompts", ".gemini", ".github/instructions", ".github/prompts",
]
WORKFLOW_JSON = ".agents/workflow.json"

# Which AI tool each workflow file points to (AGENTS.md alone says nothing: every tool reads it).
PROVIDER_HINTS = {
    "claude": ["CLAUDE.md", ".claude/agents/", ".claude/skills/", ".claude/commands/"],
    "codex": [".codex/prompts/"],
    "cursor": [".cursorrules", ".cursor/rules/"],
    "gemini": ["GEMINI.md", ".gemini/"],
    "copilot": [".github/copilot-instructions.md", ".github/instructions/", ".github/prompts/"],
}

# Flutter: pubspec dependency name -> (category, label)
FLUTTER_LIBS: Dict[str, Tuple[str, str]] = {
    "flutter_bloc": ("stateManagement", "bloc"), "bloc": ("stateManagement", "bloc"),
    "hydrated_bloc": ("stateManagement", "bloc"),
    "riverpod": ("stateManagement", "riverpod"), "flutter_riverpod": ("stateManagement", "riverpod"),
    "hooks_riverpod": ("stateManagement", "riverpod"),
    "provider": ("stateManagement", "provider"), "get": ("stateManagement", "getx"),
    "mobx": ("stateManagement", "mobx"), "flutter_mobx": ("stateManagement", "mobx"),
    "redux": ("stateManagement", "redux"), "flutter_redux": ("stateManagement", "redux"),
    "signals": ("stateManagement", "signals"),
    "get_it": ("di", "get_it"), "injectable": ("di", "injectable"), "kiwi": ("di", "kiwi"),
    "dio": ("network", "dio"), "retrofit": ("network", "retrofit"), "http": ("network", "http"),
    "chopper": ("network", "chopper"), "graphql_flutter": ("network", "graphql"),
    "go_router": ("routing", "go_router"), "auto_route": ("routing", "auto_route"),
    "freezed": ("models", "freezed"), "json_serializable": ("models", "json_serializable"),
    "flutter_localizations": ("l10n", "flutter_localizations"), "intl": ("l10n", "intl"),
    "easy_localization": ("l10n", "easy_localization"),
    "flutter_test": ("testTools", "flutter_test"), "mocktail": ("testTools", "mocktail"),
    "mockito": ("testTools", "mockito"), "bloc_test": ("testTools", "bloc_test"),
    "golden_toolkit": ("testTools", "golden_toolkit"), "alchemist": ("testTools", "alchemist"),
    "patrol": ("testTools", "patrol"), "integration_test": ("testTools", "integration_test"),
    "flutter_driver": ("testTools", "flutter_driver"),
}

# Android: regex over Gradle files + version catalogs -> (category, label)
ANDROID_LIBS: List[Tuple[str, str, str]] = [
    (r"androidx\.compose|compose-bom|compose\s*(=|true)|buildFeatures\s*\{[^}]*compose", "ui", "compose"),
    (r"viewBinding\s*(=\s*)?true|viewBinding\s*\{\s*enabled", "ui", "viewbinding"),
    (r"dataBinding\s*(=\s*)?true|dataBinding\s*\{\s*enabled", "ui", "databinding"),
    (r"dagger[.:-]hilt|hilt-android", "di", "hilt"),
    (r"com\.google\.dagger:dagger\b", "di", "dagger"),
    (r"io\.insert-koin|koin-", "di", "koin"),
    (r"io\.reactivex|rxjava|rxandroid|rxkotlin", "stateManagement", "rxjava"),
    (r"kotlinx[.-]coroutines", "stateManagement", "coroutines"),
    (r"lifecycle-livedata", "stateManagement", "livedata"),
    (r"lifecycle-viewmodel", "stateManagement", "viewmodel"),
    (r"mavericks", "stateManagement", "mavericks"),
    (r"orbit-mvi|orbit-viewmodel", "stateManagement", "orbit-mvi"),
    (r"com\.squareup\.retrofit2|retrofit", "network", "retrofit"),
    (r"okhttp", "network", "okhttp"),
    (r"apollo", "network", "apollo-graphql"),
    (r"junit:junit|junit4|androidx\.test\.ext:junit", "testTools", "junit4"),
    (r"junit-jupiter|junit5", "testTools", "junit5"),
    (r"mockito", "testTools", "mockito"),
    (r"io\.mockk|mockk", "testTools", "mockk"),
    (r"espresso", "testTools", "espresso"),
    (r"robolectric", "testTools", "robolectric"),
    (r"kaspresso", "testTools", "kaspresso"),
    (r"uiautomator", "testTools", "uiautomator"),
    (r"ui-test-junit4", "testTools", "compose-ui-test"),
    (r"app\.cash\.turbine|turbine", "testTools", "turbine"),
    (r"com\.google\.truth|truth", "testTools", "truth"),
    (r"kotest", "testTools", "kotest"),
    (r"detekt", "lint", "detekt"),
    (r"ktlint", "lint", "ktlint"),
    (r"spotless", "lint", "spotless"),
]
ANDROID_PLUGIN = re.compile(r"com\.android\.(application|library)|android\s*\{|androidApplication|androidLibrary")

# package.json dependency -> (category, label), for react-native / web detection
JS_LIBS: Dict[str, Tuple[str, str]] = {
    "react-native": ("framework", "react-native"), "react": ("framework", "react"),
    "next": ("framework", "next"), "vue": ("framework", "vue"), "nuxt": ("framework", "nuxt"),
    "@angular/core": ("framework", "angular"), "svelte": ("framework", "svelte"),
    "redux": ("stateManagement", "redux"), "@reduxjs/toolkit": ("stateManagement", "redux-toolkit"),
    "zustand": ("stateManagement", "zustand"), "mobx": ("stateManagement", "mobx"),
    "@tanstack/react-query": ("stateManagement", "react-query"), "jotai": ("stateManagement", "jotai"),
    "pinia": ("stateManagement", "pinia"), "@ngrx/store": ("stateManagement", "ngrx"),
    "jest": ("testTools", "jest"), "vitest": ("testTools", "vitest"),
    "@testing-library/react": ("testTools", "testing-library"),
    "@testing-library/react-native": ("testTools", "testing-library"),
    "@playwright/test": ("testTools", "playwright"), "cypress": ("testTools", "cypress"),
    "detox": ("testTools", "detox"), "eslint": ("lint", "eslint"), "prettier": ("lint", "prettier"),
}

GATE_HINTS = [
    "tool/check.dart", "tool/check.sh", "scripts/check.sh", "scripts/ci.sh", "Makefile",
    "melos.yaml", "lefthook.yml", ".pre-commit-config.yaml", ".husky/pre-commit",
    ".gitlab-ci.yml", "bitbucket-pipelines.yml", "Jenkinsfile", "fastlane/Fastfile",
    "codemagic.yaml", "bitrise.yml",
]


def _rel(repo: str, path: str) -> str:
    r = os.path.relpath(path, repo).replace(os.sep, "/")
    return "." if r in ("", ".") else r


def _read(path: str, limit: int = 2_000_000) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def walk(repo: str, max_depth: int = MAX_DEPTH):
    """os.walk with pruning and a depth limit. Yields (dirpath, dirnames, filenames)."""
    base_depth = repo.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(repo):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE and (not d.startswith(".") or d in ALLOWED_DOT_DIRS))
        if depth >= max_depth:
            dirnames[:] = []
        yield dirpath, dirnames, filenames


def count_sources(root: str, exclude: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    excl = [os.path.abspath(e) for e in exclude]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE and not d.startswith(".")]
        dirnames[:] = [d for d in dirnames if os.path.abspath(os.path.join(dirpath, d)) not in excl]
        for f in filenames:
            lang = SOURCE_EXT.get(os.path.splitext(f)[1])
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


# ---------- pubspec (minimal YAML: top-level sections + their direct keys) ----------

def parse_pubspec(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            current = line.split(":", 1)[0].strip()
            sections.setdefault(current, [])
            continue
        indent = len(line) - len(line.lstrip(" "))
        if current and indent == 2 and ":" in line:
            sections[current].append(line.strip().split(":", 1)[0].strip())
    return sections


def is_flutter_pubspec(text: str) -> bool:
    return bool(re.search(r"^\s+sdk:\s*flutter\s*$", text, re.M)) or bool(re.search(r"^flutter:\s*$", text, re.M))


# ---------- settings.gradle ----------

def parse_gradle_includes(text: str) -> List[str]:
    """Return Gradle module paths (':app', ':features:wallet') from include statements."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    modules: List[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^include\b", line):
            stmt = line
            while (stmt.rstrip().endswith(",") or stmt.count("(") > stmt.count(")")) and i + 1 < len(lines):
                i += 1
                stmt += " " + lines[i].strip()
            for m in re.findall(r"['\"](:?[\w\-.:]+)['\"]", stmt):
                mod = m if m.startswith(":") else ":" + m
                if mod not in modules:
                    modules.append(mod)
        i += 1
    return modules


def module_to_path(mod: str) -> str:
    return mod.strip(":").replace(":", "/")


# ---------- git ----------

def parse_remote(url: str) -> Dict[str, Optional[str]]:
    """Host classification for a remote URL, with any credentials removed."""
    url = url.strip()
    hostname = None
    m = re.match(r"^[a-z+]+://(?:[^@/]+@)?([^/:]+)", url)
    if m:
        hostname = m.group(1)
    else:
        m = re.match(r"^(?:[^@]+@)?([^:/]+):", url)
        if m:
            hostname = m.group(1)
    host = "other"
    if hostname:
        h = hostname.lower()
        if h == "github.com" or h.endswith(".github.com") or "github" in h:
            host = "github"
        elif "gitlab" in h:
            host = "gitlab"
        elif "bitbucket" in h:
            host = "bitbucket"
    return {"host": host if hostname else "other", "hostname": hostname}


def _git(repo: str, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def detect_git(repo: str) -> Dict[str, object]:
    if _git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return {"host": "none", "hostname": None, "baseBranch": None, "baseBranchCandidates": [], "currentBranch": None}
    info: Dict[str, object] = {"host": "none", "hostname": None}
    url = _git(repo, "remote", "get-url", "origin")
    if url:
        info.update(parse_remote(url))
    base = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    info["baseBranch"] = base.split("/", 1)[1] if base and "/" in base else None
    refs = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin") or ""
    names = {r.split("/", 1)[1] if r.startswith("origin/") else r for r in refs.splitlines()}
    info["baseBranchCandidates"] = [b for b in ("develop", "main", "master", "dev") if b in names]
    info["currentBranch"] = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return info


# ---------- platforms ----------

def _features_under(root: str, repo: str, candidates: List[str]) -> List[Dict[str, str]]:
    for c in candidates:
        d = os.path.join(root, c)
        if os.path.isdir(d):
            subs = sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and not x.startswith("."))
            if subs:
                return [{"path": _rel(repo, os.path.join(d, s)), "kind": "folder"} for s in subs]
    return []


def detect_flutter(repo: str, root: str, pubspec_text: str) -> Dict[str, object]:
    sections = parse_pubspec(pubspec_text)
    libs: Dict[str, List[str]] = {}
    for sec in ("dependencies", "dev_dependencies"):
        for dep in sections.get(sec, []):
            if dep in FLUTTER_LIBS:
                cat, label = FLUTTER_LIBS[dep]
                if label not in libs.setdefault(cat, []):
                    libs[cat].append(label)
    tests = {
        "test": os.path.isdir(os.path.join(root, "test")),
        "integration_test": os.path.isdir(os.path.join(root, "integration_test")),
        "goldens": any("goldens" in dirnames for _, dirnames, _ in walk(os.path.join(root, "test"), 6))
        if os.path.isdir(os.path.join(root, "test")) else False,
    }
    is_module = os.path.isdir(os.path.join(root, ".android")) or "module:" in pubspec_text
    return {
        "id": "flutter",
        "root": _rel(repo, root),
        "evidence": [f"{_rel(repo, os.path.join(root, 'pubspec.yaml'))} (sdk: flutter)"]
        + (["Flutter add-to-app module"] if is_module else []),
        "libraries": libs,
        "featureAreas": _features_under(root, repo, ["lib/features", "lib/src/features", "lib/feature", "lib/modules"]),
        "testFolders": tests,
        "toolchain": {"fvm": os.path.exists(os.path.join(root, ".fvmrc")) or os.path.isdir(os.path.join(root, ".fvm"))
                      or os.path.exists(os.path.join(repo, ".fvmrc"))},
    }


def detect_android(repo: str, root: str, settings_path: str) -> Optional[Dict[str, object]]:
    modules = parse_gradle_includes(_read(settings_path))
    gradle_text = []
    gradle_files = []
    for dirpath, dirnames, filenames in walk(root, 4):
        for f in filenames:
            if f in ("build.gradle", "build.gradle.kts") or f.endswith(".versions.toml"):
                gradle_files.append(os.path.join(dirpath, f))
    for f in gradle_files:
        gradle_text.append(_read(f, 300_000))
    blob = "\n".join(gradle_text)
    if not ANDROID_PLUGIN.search(blob):
        return None
    libs: Dict[str, List[str]] = {}
    for pattern, cat, label in ANDROID_LIBS:
        if re.search(pattern, blob, re.I) and label not in libs.setdefault(cat, []):
            libs[cat].append(label)
    libs = {k: v for k, v in libs.items() if v}
    unit = instrumented = 0
    for dirpath, dirnames, _ in walk(root, 6):
        if os.path.basename(dirpath) == "src":
            unit += "test" in dirnames
            instrumented += "androidTest" in dirnames
    feature_mods = [m for m in modules if re.match(r"^:(features?|feature-[\w-]+)(:|$)", m) and m.count(":") >= 2]
    return {
        "id": "android",
        "root": _rel(repo, root),
        "evidence": [_rel(repo, settings_path)] + ([f"{len(modules)} Gradle modules"] if modules else []),
        "libraries": libs,
        "modules": modules,
        "featureAreas": [{"path": module_to_path(m), "kind": "module", "module": m} for m in feature_mods],
        "testFolders": {"unitModules": unit, "instrumentedModules": instrumented},
        "toolchain": {"gradleWrapper": os.path.exists(os.path.join(root, "gradlew")),
                      "kotlinDsl": settings_path.endswith(".kts")},
    }


def detect_js(repo: str, root: str, pkg_path: str) -> Optional[Dict[str, object]]:
    try:
        pkg = json.loads(_read(pkg_path))
    except ValueError:
        return None
    deps = {}
    for k in ("dependencies", "devDependencies", "peerDependencies"):
        if isinstance(pkg.get(k), dict):
            deps.update(pkg[k])
    libs: Dict[str, List[str]] = {}
    for dep in deps:
        if dep in JS_LIBS:
            cat, label = JS_LIBS[dep]
            if label not in libs.setdefault(cat, []):
                libs[cat].append(label)
    frameworks = libs.get("framework", [])
    if not frameworks:
        return None
    pid = "react-native" if "react-native" in frameworks else "web"
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    return {
        "id": pid,
        "root": _rel(repo, root),
        "evidence": [f"{_rel(repo, pkg_path)} ({', '.join(frameworks)})"],
        "libraries": libs,
        "featureAreas": _features_under(root, repo, ["src/features", "src/modules", "app/features", "features"]),
        "testFolders": {"e2e": os.path.isdir(os.path.join(root, "e2e")) or os.path.isdir(os.path.join(root, "cypress"))},
        "toolchain": {"scripts": sorted(scripts)[:20],
                      "packageManager": "pnpm" if os.path.exists(os.path.join(root, "pnpm-lock.yaml"))
                      else "yarn" if os.path.exists(os.path.join(root, "yarn.lock")) else "npm"},
    }


def detect_ios(repo: str, root: str, marker: str) -> Dict[str, object]:
    return {
        "id": "ios",
        "root": _rel(repo, root),
        "evidence": [_rel(repo, marker)],
        "libraries": {},
        "featureAreas": [],
        "testFolders": {},
        "toolchain": {"cocoapods": os.path.exists(os.path.join(root, "Podfile")),
                      "spm": os.path.exists(os.path.join(root, "Package.swift"))},
    }


def find_platforms(repo: str) -> List[Dict[str, object]]:
    platforms: List[Dict[str, object]] = []
    flutter_roots: List[str] = []
    js_roots: List[str] = []
    # Pass 1: Flutter and JS roots (their android/ios folders are host shells, not native apps).
    for dirpath, dirnames, filenames in walk(repo):
        if "pubspec.yaml" in filenames:
            text = _read(os.path.join(dirpath, "pubspec.yaml"))
            # Package example apps are not platforms of their own.
            if is_flutter_pubspec(text) and "example" not in _rel(repo, dirpath).split("/"):
                flutter_roots.append(dirpath)
                platforms.append(detect_flutter(repo, dirpath, text))
        if "package.json" in filenames:
            p = detect_js(repo, dirpath, os.path.join(dirpath, "package.json"))
            if p:
                js_roots.append(dirpath)
                platforms.append(p)
    hosts = []
    for r in flutter_roots + js_roots:
        hosts += [os.path.join(r, d) for d in ("android", "ios", ".android", ".ios")]

    def under_host(path: str) -> bool:
        return any(path == h or path.startswith(h + os.sep) for h in hosts)

    # Pass 2: native Android / iOS outside those host shells.
    seen_android = False
    for dirpath, dirnames, filenames in walk(repo, 3):
        if under_host(dirpath):
            dirnames[:] = []
            continue
        if not seen_android:
            for name in ("settings.gradle", "settings.gradle.kts"):
                if name in filenames:
                    p = detect_android(repo, dirpath, os.path.join(dirpath, name))
                    if p:
                        platforms.append(p)
                        seen_android = True
                    break
        xcode = [d for d in dirnames if d.endswith((".xcodeproj", ".xcworkspace"))]
        if xcode and not any(pl["id"] == "ios" for pl in platforms):
            platforms.append(detect_ios(repo, dirpath, os.path.join(dirpath, xcode[0])))

    # Source counts per platform, excluding nested platform roots.
    roots = [os.path.join(repo, str(p["root"])) if p["root"] != "." else repo for p in platforms]
    for p, root in zip(platforms, roots):
        nested = [r for r in roots if r != root and r.startswith(root + os.sep)]
        p["sourceFiles"] = count_sources(root, nested + [h for h in hosts if h.startswith(root + os.sep)])
    # Primary: the platform at the repo root, else the one with most source files.
    if platforms:
        at_root = [p for p in platforms if p["root"] == "."]
        primary = at_root[0] if at_root else max(platforms, key=lambda p: sum(p["sourceFiles"].values()))
        for p in platforms:
            p["primary"] = p is primary
        platforms.sort(key=lambda p: (not p["primary"], str(p["root"])))
    return platforms


def find_ai_files(repo: str) -> List[str]:
    found = [f for f in AI_FILES if os.path.isfile(os.path.join(repo, f))]
    for d in AI_DIRS:
        path = os.path.join(repo, d)
        if os.path.isdir(path) and any(not x.startswith(".") for x in os.listdir(path)):
            found.append(d + "/")
    if os.path.isfile(os.path.join(repo, WORKFLOW_JSON)):
        found.append(WORKFLOW_JSON)
    return found


def find_gate_candidates(repo: str) -> List[str]:
    found = [g for g in GATE_HINTS if os.path.exists(os.path.join(repo, g))]
    wf = os.path.join(repo, ".github", "workflows")
    if os.path.isdir(wf):
        found += [f".github/workflows/{f}" for f in sorted(os.listdir(wf)) if f.endswith((".yml", ".yaml"))]
    return found


def detect(repo: str) -> Dict[str, object]:
    repo = os.path.abspath(repo)
    ai = find_ai_files(repo)
    platforms = find_platforms(repo)
    if WORKFLOW_JSON in ai:
        mode = "update"
    elif ai:
        mode = "migrate"
    elif platforms:
        mode = "adopt"
    else:
        mode = "fresh"
    notes: List[str] = []
    if len(platforms) > 1:
        notes.append("More than one platform found — confirm which are in scope and which is primary.")
    for p in platforms:
        libs = p.get("libraries", {})
        if p["id"] == "flutter" and "getx" in libs.get("stateManagement", []) and len(libs.get("stateManagement", [])) > 1:
            notes.append(f"{p['root']}: GetX and another state library both present — ask which one is allowed.")
        tt = libs.get("testTools", [])
        if p["id"] == "android" and not any(t in tt for t in ("espresso", "kaspresso", "uiautomator", "compose-ui-test")):
            notes.append(f"{p['root']}: no UI/e2e test tool found — e2e policy may need 'none' or a new tool.")
        if p["id"] == "android" and not libs.get("lint"):
            notes.append(f"{p['root']}: no detekt/ktlint/spotless — ask what lint the gate runs.")
        if p["id"] == "android" and not any(q["id"] == "flutter" for q in platforms):
            bridges = [m for m in p.get("modules", []) if "flutter" in m.lower()]
            if bridges:
                notes.append(f"{p['root']}: module(s) {bridges} mention Flutter but no Flutter source is in this repo "
                             "— likely a prebuilt add-to-app AAR; don't treat Flutter as a platform here.")
    if mode == "migrate":
        notes.append("Existing AI-workflow files found — migrate mode: read them first, never overwrite without a per-file OK.")
    providers = {p: [f for f in files if f in ai] for p, files in PROVIDER_HINTS.items()}
    return {
        "detectorVersion": DETECTOR_VERSION,
        "repo": repo,
        "mode": mode,
        "aiFiles": ai,
        "providers": {p: ev for p, ev in providers.items() if ev},
        "platforms": platforms,
        "gateCandidates": find_gate_candidates(repo),
        "git": detect_git(repo),
        "notes": notes,
    }


def main(argv: List[str]) -> int:
    repo = argv[0] if argv else "."
    if not os.path.isdir(repo):
        print(json.dumps({"error": f"not a folder: {repo}"}))
        return 2
    print(json.dumps(detect(repo), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
