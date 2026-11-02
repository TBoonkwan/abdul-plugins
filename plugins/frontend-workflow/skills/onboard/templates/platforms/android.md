# Platform template: Android (native)

Defaults and option lists for the interview when a platform's `id` is `android`.

## Detection hints
- `settings.gradle(.kts)` + `com.android.application`/`library`; Gradle wrapper
  `./gradlew` present → use it in every command.
- Multi-module: `include` lines list modules. `:features:<x>` modules are feature
  areas; squads own them as paths (`features/<x>`). `:core`, `:common:*`, `:data`,
  `:app` usually go to a core squad; `:libs:*` vendored SDKs usually stay unowned.
- A module named like `*flutter*` with no `pubspec.yaml` in the repo is a bridge to a
  prebuilt Flutter AAR — not a Flutter platform in this repo.

## Architecture options
| Option | Pick when |
|---|---|
| `mvvm` | ViewModel + LiveData/StateFlow/Rx per screen (most common) |
| `mvi` | Single state object + intents/reducer (Orbit, Mavericks, custom) |
| `clean-feature-modules` | Feature modules with domain/data/presentation layers inside |
| `other` | Ask for one line describing it |

Typical `architecture.notes`: "feature modules never depend on other feature
modules", "shared code goes in core/common modules", "ViewModels expose state, views
never call repositories".

## State management options
Detected first, then: `coroutines` + `flow` · `rxjava` · `livedata` · `mavericks` ·
`orbit-mvi`. When both Rx and coroutines are present, ask which one new code must use
(a common hard rule: "New code uses coroutines/Flow; RxJava only in existing code").

## UI options
`viewbinding` · `databinding` · `compose` — ask which one new screens use.

## DI options
`hilt` · `koin` · `dagger` · manual.

## Test levels on Android
| Level | Means here | Tools | Location | Command |
|---|---|---|---|---|
| Unit | JVM tests of ViewModels, use cases, repositories; no Android framework | JUnit4/5 + Mockito/MockK, Turbine, Truth | `<module>/src/test/` | `./gradlew testDebugUnitTest` |
| Integration | One screen or component with fakes — Robolectric on the JVM, or an instrumented test | Robolectric, Espresso, Compose UI test | `src/test/` or `src/androidTest/` | `./gradlew testDebugUnitTest` / `connectedDebugAndroidTest` |
| E2E | Whole-app journeys on a device/emulator | Espresso/Kaspresso, UI Automator, Maestro, Appium | `src/androidTest/` or `.maestro/` | `./gradlew connectedDebugAndroidTest` / `maestro test .maestro` |

Instrumented tests need a device or emulator — a gate that must run without one should
keep e2e out of `commands.gate`.

## Default commands
| Key | Command |
|---|---|
| install | `null` (Gradle resolves dependencies) |
| format | `./gradlew ktlintFormat` / `spotlessApply` if configured, else `null` |
| lint | `./gradlew lint` (+ `detekt` / `ktlintCheck` if configured) |
| test | `./gradlew testDebugUnitTest` |
| build | `./gradlew assembleDebug` (use the real flavor/variant name if the app has flavors) |
| run | `null` (run from Android Studio) |
| gate | `./gradlew lint testDebugUnitTest` |

**Many modules (> ~15):** recommend `gateScope: affected` — run the gate only for the
changed modules (e.g. `./gradlew :features:<x>:testDebugUnitTest`) and the full gate
before merging.

## Hard-rule suggestions
- "Feature modules never depend on each other"
- "New code uses <coroutines|RxJava>" when both exist
- "New screens use <ViewBinding|Compose>"
- "Secrets and signing keys never go into Gradle files or source"

## Reviewer suggestions
architecture + tests always; security for apps handling payments, identity or
personal data; accessibility for public consumer apps.
