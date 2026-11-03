import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "plugins", "abdul", "skills", "onboard", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import detect  # noqa: E402


def write(root, rel, text=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(text))


FLUTTER_PUBSPEC = """\
    name: shop
    environment:
      sdk: ">=3.0.0 <4.0.0"
    dependencies:
      flutter:
        sdk: flutter
      flutter_bloc: ^8.1.0
      get_it: ^7.6.0
      dio: ^5.0.0
    dev_dependencies:
      flutter_test:
        sdk: flutter
      mocktail: ^1.0.0
      integration_test:
        sdk: flutter
    flutter:
      uses-material-design: true
"""


class FlutterRepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        write(r, "pubspec.yaml", FLUTTER_PUBSPEC)
        write(r, ".fvmrc", '{"flutter": "3.38.0"}')
        write(r, "lib/main.dart", "void main() {}")
        write(r, "lib/features/auth/auth.dart")
        write(r, "lib/features/cart/cart.dart")
        write(r, "test/goldens/button.png")
        write(r, "integration_test/app_test.dart")
        write(r, "tool/check.dart")
        # Flutter's host shells must not be detected as native platforms.
        write(r, "android/settings.gradle", "include ':app'\n")
        write(r, "android/app/build.gradle", "plugins { id 'com.android.application' }\nandroid {}\n")
        write(r, "ios/Runner.xcodeproj/project.pbxproj")
        # Package example apps are not platforms.
        write(r, "packages/ui/example/pubspec.yaml", FLUTTER_PUBSPEC)
        # Worktrees and AI folders are never scanned for code.
        write(r, ".claude/worktrees/x/lib/features/ghost/ghost.dart")
        self.result = detect.detect(r)

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_flutter_platform_at_root(self):
        ids = [(p["id"], p["root"]) for p in self.result["platforms"]]
        self.assertEqual(ids, [("flutter", ".")])
        self.assertTrue(self.result["platforms"][0]["primary"])

    def test_libraries_by_category(self):
        libs = self.result["platforms"][0]["libraries"]
        self.assertEqual(libs["stateManagement"], ["bloc"])
        self.assertEqual(libs["di"], ["get_it"])
        self.assertIn("mocktail", libs["testTools"])
        self.assertIn("integration_test", libs["testTools"])

    def test_feature_areas_tests_and_toolchain(self):
        p = self.result["platforms"][0]
        self.assertEqual([f["path"] for f in p["featureAreas"]], ["lib/features/auth", "lib/features/cart"])
        self.assertEqual(p["testFolders"], {"test": True, "integration_test": True, "goldens": True})
        self.assertTrue(p["toolchain"]["fvm"])
        # lib/ (3) + integration_test/ + tool/ — not android/, ios/ or .claude/worktrees/
        self.assertEqual(p["sourceFiles"], {"dart": 5})

    def test_mode_and_gate(self):
        self.assertEqual(self.result["mode"], "adopt")
        self.assertIn("tool/check.dart", self.result["gateCandidates"])


class AndroidMultiModuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.tmp.name
        write(r, "settings.gradle", """\
            rootProject.name = 'wallet'
            include ':app',
                    ':features:wallet'
            include ':core'   // shared
            include ':features:flutterbridge'
            /* include ':ignored' */
        """)
        write(r, "gradlew", "#!/bin/sh\n")
        write(r, "app/build.gradle", """\
            plugins { id 'com.android.application' }
            android { buildFeatures { viewBinding true } }
            dependencies {
                implementation 'io.insert-koin:koin-android:3.5.0'
                implementation 'io.reactivex.rxjava3:rxjava:3.1.0'
                testImplementation 'junit:junit:4.13.2'
                testImplementation 'org.mockito:mockito-core:5.0.0'
            }
        """)
        write(r, "features/wallet/build.gradle", "plugins { id 'com.android.library' }\n")
        write(r, "features/wallet/src/main/kotlin/Wallet.kt", "class Wallet")
        write(r, "features/wallet/src/test/kotlin/WalletTest.kt", "class WalletTest")
        write(r, "app/src/main/java/Main.java", "class Main {}")
        self.result = detect.detect(r)

    def tearDown(self):
        self.tmp.cleanup()

    def test_modules_parsed_with_continuations_and_comments(self):
        p = self.result["platforms"][0]
        self.assertEqual(p["modules"], [":app", ":features:wallet", ":core", ":features:flutterbridge"])

    def test_feature_modules_become_paths(self):
        p = self.result["platforms"][0]
        self.assertEqual([f["path"] for f in p["featureAreas"]], ["features/wallet", "features/flutterbridge"])
        self.assertEqual(p["featureAreas"][0]["kind"], "module")

    def test_libraries_tests_and_toolchain(self):
        p = self.result["platforms"][0]
        self.assertEqual(p["id"], "android")
        self.assertEqual(p["libraries"]["di"], ["koin"])
        self.assertEqual(p["libraries"]["stateManagement"], ["rxjava"])
        self.assertEqual(p["libraries"]["ui"], ["viewbinding"])
        self.assertEqual(sorted(p["libraries"]["testTools"]), ["junit4", "mockito"])
        self.assertEqual(p["testFolders"], {"unitModules": 1, "instrumentedModules": 0})
        self.assertTrue(p["toolchain"]["gradleWrapper"])
        self.assertEqual(p["sourceFiles"], {"kotlin": 2, "java": 1})

    def test_notes_flag_missing_lint_ui_tests_and_flutter_bridge(self):
        notes = " ".join(self.result["notes"])
        self.assertIn("no detekt/ktlint/spotless", notes)
        self.assertIn("no UI/e2e test tool", notes)
        self.assertIn(":features:flutterbridge", notes)
        self.assertEqual(self.result["mode"], "adopt")


class FlutterModuleInsideAndroidTest(unittest.TestCase):
    def test_nested_flutter_module_is_secondary_platform(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "settings.gradle", "include ':app'\n")
            write(r, "app/build.gradle", "plugins { id 'com.android.application' }\n")
            write(r, "app/src/main/kotlin/A.kt", "class A")
            write(r, "flutter_module/pubspec.yaml", textwrap.dedent(FLUTTER_PUBSPEC) + "  module:\n    androidX: true\n")
            write(r, "flutter_module/lib/main.dart", "void main() {}")
            write(r, "flutter_module/.android/settings.gradle", "include ':flutter'\n")
            result = detect.detect(r)
            got = [(p["id"], p["root"], p["primary"]) for p in result["platforms"]]
            self.assertEqual(got, [("android", ".", True), ("flutter", "flutter_module", False)])
            self.assertEqual(result["platforms"][0]["sourceFiles"], {"kotlin": 1})
            self.assertIn("Flutter add-to-app module", result["platforms"][1]["evidence"])


class ModeTest(unittest.TestCase):
    def test_fresh_when_no_code(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "README.md", "# empty")
            self.assertEqual(detect.detect(r)["mode"], "fresh")

    def test_migrate_when_ai_files_exist(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "pubspec.yaml", FLUTTER_PUBSPEC)
            write(r, "CLAUDE.md", "# rules")
            write(r, ".claude/agents/auth-squad.md", "---\nname: auth-squad\n---\n")
            write(r, ".codex/prompts/delegate.md", "delegate")
            res = detect.detect(r)
            self.assertEqual(res["mode"], "migrate")
            self.assertEqual(res["aiFiles"], ["CLAUDE.md", ".claude/agents/", ".codex/prompts/"])
            self.assertEqual(res["providers"], {"claude": ["CLAUDE.md", ".claude/agents/"],
                                                "codex": [".codex/prompts/"]})

    def test_agents_md_alone_names_no_provider(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "pubspec.yaml", FLUTTER_PUBSPEC)
            write(r, "AGENTS.md", "# rules")
            res = detect.detect(r)
            self.assertEqual(res["mode"], "migrate")
            self.assertEqual(res["providers"], {})

    def test_settings_local_alone_is_not_a_workflow(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "pubspec.yaml", FLUTTER_PUBSPEC)
            write(r, ".claude/settings.local.json", "{}")
            self.assertEqual(detect.detect(r)["mode"], "adopt")

    def test_update_when_workflow_json_exists(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "AGENTS.md", "# rules")
            write(r, ".agents/workflow.json", "{}")
            self.assertEqual(detect.detect(r)["mode"], "update")


class JsPlatformTest(unittest.TestCase):
    def test_react_native_and_web(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "mobile/package.json", json.dumps({"dependencies": {"react-native": "0.76", "react": "18", "zustand": "4"},
                                                        "devDependencies": {"jest": "29", "detox": "20"}}))
            write(r, "web/package.json", json.dumps({"dependencies": {"next": "15", "react": "18"},
                                                     "devDependencies": {"@playwright/test": "1"}}))
            write(r, "web/src/app.tsx", "export {}")
            res = detect.detect(r)
            got = {p["id"]: p for p in res["platforms"]}
            self.assertEqual(set(got), {"react-native", "web"})
            self.assertEqual(got["react-native"]["libraries"]["stateManagement"], ["zustand"])
            self.assertIn("detox", got["react-native"]["libraries"]["testTools"])
            self.assertIn("playwright", got["web"]["libraries"]["testTools"])
            self.assertEqual(sum(p["primary"] for p in res["platforms"]), 1)


class ParseTest(unittest.TestCase):
    def test_kotlin_dsl_includes(self):
        text = 'include(":app", ":feature:home")\ninclude(\n  ":core:ui",\n)\n'
        self.assertEqual(detect.parse_gradle_includes(text), [":app", ":feature:home", ":core:ui"])

    def test_remote_strips_credentials(self):
        cases = {
            "https://alice@github.com/org/repo.git": ("github", "github.com"),
            "git@github.com:org/repo.git": ("github", "github.com"),
            "ssh://git@gitlab.example.com:2222/team/app.git": ("gitlab", "gitlab.example.com"),
            "ssh://git@git.corp.example:2222/team/app.git": ("other", "git.corp.example"),
            "https://bitbucket.org/team/app.git": ("bitbucket", "bitbucket.org"),
        }
        for url, (host, hostname) in cases.items():
            got = detect.parse_remote(url)
            self.assertEqual((got["host"], got["hostname"]), (host, hostname), url)
            self.assertNotIn("alice", json.dumps(got))

    def test_cli_prints_json_and_never_writes(self):
        with tempfile.TemporaryDirectory() as r:
            write(r, "pubspec.yaml", FLUTTER_PUBSPEC)
            before = sorted(os.walk(r))
            out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "detect.py"), r],
                                 capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(out.stdout)["detectorVersion"], 1)
            self.assertEqual(sorted(os.walk(r)), before)


if __name__ == "__main__":
    unittest.main()
