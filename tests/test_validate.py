import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

ONBOARD = os.path.join(os.path.dirname(__file__), "..", "plugins", "frontend-workflow", "skills", "onboard")
SCRIPTS = os.path.join(ONBOARD, "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import validate_workflow as vw  # noqa: E402

with open(os.path.join(ONBOARD, "reference", "example.workflow.json"), encoding="utf-8") as fh:
    EXAMPLE = json.load(fh)


def errors_for(mutate):
    data = copy.deepcopy(EXAMPLE)
    mutate(data)
    return vw.validate(data).errors


class ExampleTest(unittest.TestCase):
    def test_shipped_example_is_valid_without_warnings(self):
        rep = vw.validate(EXAMPLE)
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.warnings, [])


class RuleTest(unittest.TestCase):
    def assertError(self, mutate, needle):
        errs = errors_for(mutate)
        self.assertTrue(any(needle in e for e in errs), f"expected '{needle}' in {errs}")

    def test_missing_gate(self):
        self.assertError(lambda d: d["commands"].update(gate=""), "commands.gate")

    def test_required_level_needs_tool(self):
        self.assertError(lambda d: d["testing"]["e2e"].update(policy="new-features"), "testing.e2e.tool")

    def test_level_needs_meaning(self):
        self.assertError(lambda d: d["testing"]["unit"].pop("meaning"), "testing.unit.meaning")

    def test_unknown_policy(self):
        self.assertError(lambda d: d["testing"]["unit"].update(policy="sometimes"), "testing.unit.policy")

    def test_exactly_one_primary(self):
        self.assertError(lambda d: d["project"]["platforms"][1].update(primary=True), "exactly one platform")

    def test_duplicate_squad_id(self):
        self.assertError(lambda d: d["squads"][1].update(id="wallet-squad"), "duplicate squad id")

    def test_squad_id_kebab_case(self):
        self.assertError(lambda d: d["squads"][0].update(id="Wallet Squad"), "kebab-case")

    def test_two_squads_cannot_own_one_path(self):
        self.assertError(lambda d: d["squads"][1]["owns"].append("features/wallet/"), "already owned by 'wallet-squad'")

    def test_paths_must_stay_in_repo(self):
        self.assertError(lambda d: d["squads"][0]["owns"].append("../other"), "must not contain '..'")
        self.assertError(lambda d: d["squads"][0]["owns"].append("/abs/path"), "repo-relative")

    def test_squad_must_own_something(self):
        self.assertError(lambda d: d["squads"][0].update(owns=[]), "must not be empty")

    def test_unknown_provider_and_reviewer(self):
        self.assertError(lambda d: d["providers"].append("chatgpt"), "providers")
        self.assertError(lambda d: d["roles"]["reviewers"].append("style"), "roles.reviewers")

    def test_enums(self):
        self.assertError(lambda d: d["project"].update(size="huge"), "project.size")
        self.assertError(lambda d: d["git"].update(host="svn"), "git.host")
        self.assertError(lambda d: d["git"].update(branching="yolo"), "git.branching")
        self.assertError(lambda d: d["commands"].update(gateScope="some"), "commands.gateScope")

    def test_reviewer_agents_must_match_reviewers(self):
        self.assertError(lambda d: d["roles"].update(reviewerAgents={"security": "sec-bot"}), "not listed in roles.reviewers")
        self.assertError(lambda d: d["roles"].update(reviewerAgents={"tests": "QA Reviewer"}), "kebab-case agent name")
        self.assertEqual(errors_for(lambda d: d["roles"].update(reviewerAgents={"architecture": "arch-reviewer"})), [])

    def test_missing_top_level_and_version(self):
        self.assertError(lambda d: d.pop("testing"), "testing: is missing")
        self.assertError(lambda d: d.update(schemaVersion=2), "schemaVersion")


class WarningTest(unittest.TestCase):
    def test_nested_ownership_warns_not_errors(self):
        data = copy.deepcopy(EXAMPLE)
        data["squads"][1]["owns"].append("features/wallet/payments")
        rep = vw.validate(data)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("nests with" in w for w in rep.warnings))

    def test_full_size_without_squads_warns(self):
        data = copy.deepcopy(EXAMPLE)
        data["project"]["size"] = "full"
        data["squads"] = []
        data["files"]["ownership"] = None
        rep = vw.validate(data)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("no squads yet" in w for w in rep.warnings))


class RepoCheckTest(unittest.TestCase):
    def test_repo_mode_checks_paths(self):
        with tempfile.TemporaryDirectory() as r:
            os.makedirs(os.path.join(r, "features", "wallet"))
            os.makedirs(os.path.join(r, "features", "flutterbridge", "module"))
            rep = vw.validate(EXAMPLE, repo=r)
            self.assertEqual(rep.errors, [])
            self.assertTrue(any("'features/topup' does not exist" in w for w in rep.warnings))
            self.assertTrue(any("files.rules" in w for w in rep.warnings))

    def test_missing_platform_root_is_an_error(self):
        with tempfile.TemporaryDirectory() as r:
            rep = vw.validate(EXAMPLE, repo=r)
            self.assertTrue(any("project.platforms[1].root" in e for e in rep.errors))


class DriftTest(unittest.TestCase):
    """With --repo, warn when workflow.json and the prose files it summarises disagree."""

    def make_repo(self, r, rules, ownership, agents):
        for p in ("features/wallet", "features/topup", "core", "app", "features/flutterbridge/module"):
            os.makedirs(os.path.join(r, p))
        with open(os.path.join(r, "AGENTS.md"), "w") as fh:
            fh.write(rules)
        os.makedirs(os.path.join(r, ".agents"))
        with open(os.path.join(r, ".agents", "OWNERSHIP.md"), "w") as fh:
            fh.write(ownership)
        os.makedirs(os.path.join(r, ".claude", "agents"))
        for name in agents:
            with open(os.path.join(r, ".claude", "agents", f"{name}.md"), "w") as fh:
                fh.write("---\nname: x\n---\n")

    def test_in_sync_repo_has_no_warnings(self):
        with tempfile.TemporaryDirectory() as r:
            self.make_repo(r, "Gate: `./gradlew lint testDebugUnitTest`", "wallet-squad core-squad",
                           ["architecture-reviewer", "tests-reviewer"])
            rep = vw.validate(EXAMPLE, repo=r)
            self.assertEqual((rep.errors, rep.warnings), ([], []))

    def test_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as r:
            self.make_repo(r, "Gate: `./gradlew check`", "wallet-squad only", ["arch-reviewer"])
            rep = vw.validate(EXAMPLE, repo=r)
            self.assertEqual(rep.errors, [])
            joined = "\n".join(rep.warnings)
            self.assertIn("'./gradlew lint testDebugUnitTest' is not mentioned in AGENTS.md", joined)
            self.assertIn("'core-squad' is not mentioned in .agents/OWNERSHIP.md", joined)
            self.assertIn(".claude/agents/architecture-reviewer.md", joined)
            self.assertIn(".claude/agents/tests-reviewer.md", joined)

    def test_reviewer_agents_mapping_resolves_custom_names(self):
        with tempfile.TemporaryDirectory() as r:
            self.make_repo(r, "./gradlew lint testDebugUnitTest", "wallet-squad core-squad",
                           ["arch-reviewer", "qa-reviewer"])
            data = copy.deepcopy(EXAMPLE)
            data["roles"]["reviewerAgents"] = {"architecture": "arch-reviewer", "tests": "qa-reviewer"}
            self.assertEqual(vw.validate(data, repo=r).warnings, [])


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "validate_workflow.py"), *args],
                              capture_output=True, text=True)

    def test_exit_codes(self):
        ok = self.run_cli(os.path.join(ONBOARD, "reference", "example.workflow.json"))
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn("OK: schema v1", ok.stdout)
        with tempfile.TemporaryDirectory() as r:
            bad = os.path.join(r, "w.json")
            with open(bad, "w") as fh:
                fh.write("{not json")
            res = self.run_cli(bad)
            self.assertEqual(res.returncode, 1)
            self.assertIn("invalid JSON", res.stdout)
        self.assertEqual(self.run_cli().returncode, 2)


if __name__ == "__main__":
    unittest.main()
