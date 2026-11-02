# Platform template: Flutter

Defaults and option lists for the interview when a platform's `id` is `flutter`.

## Detection hints
- `pubspec.yaml` with `sdk: flutter`; `.fvmrc` / `.fvm/` → prefix commands with `fvm `.
- `.android/` + `module:` in pubspec → add-to-app module (its own platform entry).
- Feature areas: `lib/features/*` (or `lib/src/features/*`). Squads own these folders.

## Architecture options
| Option | Pick when |
|---|---|
| `clean-feature-first` | `lib/features/<f>/{data,domain,presentation}` |
| `layered` | `lib/{data,domain,ui}` shared across features |
| `mvvm` | ViewModels / ChangeNotifiers per screen |
| `other` | Ask for one line describing it |

Typical `architecture.notes` for Clean: "presentation → domain only; domain imports
nothing from data", "wire models never leave the data layer".

## State management options
Detected first, then: `bloc` · `riverpod` · `provider` · `getx` · `mobx` · `redux` ·
`signals`. If one is detected and another is present-but-unwanted, offer a hard rule
"No <lib>".

## DI options
`get_it` + `injectable` · `riverpod` (as DI) · `kiwi` · none.

## Test levels on Flutter
| Level | Means here | Tools | Location | Command |
|---|---|---|---|---|
| Unit | Pure Dart: blocs/cubits, use cases, repositories, mappers | `flutter_test` + `mocktail`/`mockito`, `bloc_test` | `test/` | `flutter test --exclude-tags golden` |
| Integration | Widget tests of one screen with fakes, plus golden (screenshot) tests | `flutter_test`, `golden_toolkit`/`alchemist` | `test/` (goldens tagged) | `flutter test` |
| E2E | The whole app on a device/simulator, real navigation | `integration_test`, `patrol`, Maestro | `integration_test/` | `flutter test integration_test` |

Note: Flutter's own `integration_test` package is **e2e** here, not "integration".

## Default commands (prefix `fvm ` when fvm is detected)
| Key | Command |
|---|---|
| install | `flutter pub get` |
| format | `dart format .` |
| lint | `flutter analyze` |
| test | `flutter test` |
| build | `flutter build apk --debug` |
| run | `flutter run` |
| gate | an existing check script (e.g. `dart run tool/check.dart`), else `flutter analyze && flutter test` |

Also needed after codegen changes when `build_runner` is a dependency:
`dart run build_runner build --delete-conflicting-outputs` — mention it in
`architecture.notes` or hard rules if the repo uses freezed/injectable/retrofit.

## Hard-rule suggestions
- "No <unwanted state library>" (e.g. No GetX)
- "Design system first: reuse `lib/design_system/` (or equivalent) before new widgets"
  — only if such a folder exists
- "No hard-coded user-facing strings" — when `flutter_localizations`/`intl` is present
- "Secrets never go into `.env` / dart-define files"

## Reviewer suggestions
architecture + tests always; design-system when a DS folder exists; l10n when
localization libraries are present.
