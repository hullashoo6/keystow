# KeyStow living acceptance checklist

Updated 2026-11-18. This is a record of evidence, not a feature list.

Labels: **OPEN** = insufficient evidence; **COMPONENT** = isolated logic or offscreen check; **HARDWARE** = real OS/device journey; **RELEASE** = actual downloaded installer journey. Never promote a component result to a hardware or release claim.

## Current truth

- v1.0.1 source/tag is `bbb511c2e9a05122196bd141b5e841e1042aa98f`. Both packaging jobs passed in [run44243349123](https://github.com/hullashoo6/keystow/actions/runs/44243349123). Both complete public asset downloads returned200 and matched GitHub SHA256 digests. This is packaging/download evidence, NOT installed acceptance.
- [v1.0.1 release](https://github.com/hullashoo6/keystow/releases/tag/v1.0.1): Windows292238320bytes, SHA256 `24cde89cf38feba67464423fe1131ad7e4a05e069742678a3b244505f1be6003`; Mac235717838bytes, SHA256 `017f57a49329c8b731e28f824a54eff91e133f292c436aa5209e38dc6e2af486`. v1.0.0 retained separately.
- Uncustomized v1.0.1 defaults to HOLD, preserving explicit modes/env and conservative legacy custom-key toggle. Startup, debounce, mode persistence and staged legacy-data migration have component coverage. Installed upgrade behavior remains OPEN.
- Engineering source snapshot `68ddeb8284849739ccfb79cce48059737233645d` on `engineering/clipboard-log-recovery`: fresh public clone61tests passed in2.553s on2026-11-18 at19:10IST; compile/whitespace passed; zero branch workflows. Clipboard cleanup/conditional restore, best-effort logging, autostart retry/atomic Mac plist, and startup-storage recovery are COMPONENT evidence only. They are NOT in main or downloaded v1.0.1. The five-file startup patch is cumulative across `3350579..68ddeb8`, not the latest single-file commit alone.
- Main at `645d6f5eb8b4a482d5bad6745bad5e31afbd998b` contains the current page. [Pages run44302009038](https://github.com/hullashoo6/keystow/actions/runs/44302009038) passed; [live page](https://hullashoo6.github.io/keystow/) exact served bytes and desktop1440/mobile390 pixels checked2026-11-18 at17:47IST. Both direct installer links returned200. Page mechanics state that these buttons download installers directly and collect no payment; the owner-set $5 lifetime hero/card remain unchanged. Footer and install-override guidance remain removed. Preserve this newer page and README during reconciliation.
- Real Windows/macOS microphone, global shortcut, external paste, permission recovery and installed-release journeys remain OPEN. No owner hardware pass is inferred from an attempted install or source checks.

## Ordered work and acceptance

### 1. Startup wiring

- [x] COMPONENT: `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v` must show the real Qt event loop calls controller `start()` once and retains it through event-loop execution. Record Python/Qt versions and commit.
- [x] COMPONENT: `python -m compileall -q keystow tests` exits zero.
- [ ] RELEASE: install the rebuilt asset, launch, observe ready or an actionable initialization error, not indefinite loading. Record artifact hash and OS.

The startup check substitutes the controller and external side effects. It does not test the speech model, microphone, global shortcut or real paste.

### 2. One dictation session at a time

- [ ] COMPONENT: block a transcription worker with an event; repeated start/stop/hotkey calls must not create a second capture or worker.
- [ ] COMPONENT: while recording or processing, request a model switch; no second loader or current-model mutation may interfere with the active operation.
- [ ] COMPONENT: force capture-start, capture-stop, transcription, and paste failures independently; the next recording must be possible and the message must identify the failed step.
- [ ] COMPONENT: empty input produces no paste; one successful session pastes once; recovery retains the transcript.
- [ ] HARDWARE: repeat real shortcut dictation into Notepad and a browser text field, including rapid presses during processing. Record observed text, duplicates, recovery, OS/mic/CPU and elapsed time. Passing mocks is not sufficient.

### 3. Real first-time Windows journey

- [ ] RELEASE: download the exact public installer, record SHA256, install without Python or development tools, launch and use the bundled base model with network disconnected. Record any network attempt/error.
- [ ] HARDWARE: focus Notepad, dictate a known sentence, stop with the configured key, compare inserted text and punctuation. Repeat in a browser field and a code editor without sending any message externally.
- [ ] HARDWARE: deny/revoke mic permission or remove the device; recording must fail clearly, no false success, and work again after permission/device recovery.
- [ ] HARDWARE: change focus during transcription and document actual paste destination. Do not claim focus safety unless tested and implemented. Test clipboard text preservation and non-text clipboard limits explicitly.
- [ ] HARDWARE: test silence, pauses, a longer utterance and immediate next utterance. Record actual transcript and latency, not an invented accuracy percentage.

### 4. Model and interruption journeys

- [ ] COMPONENT/HARDWARE separately: with packaged base present, load by its local path; with no cache/network, optional model selection gives understandable failure and leaves a usable recovery path.
- [ ] HARDWARE: interrupt an optional download, retry it, then choose base. No stuck controls, unusable model state, or worker destruction while running. Record logs without transcript/private text.
- [ ] HARDWARE: switch models while idle, then dictate. Switch requests while recording/processing must not alter the active session.
- [ ] HARDWARE: verify noise reduction available/unavailable paths; missing native support must preserve dictation and copy must not imply active suppression when unavailable.

### 5. Upgrade, persistence and shutdown

- [ ] COMPONENT: in a temporary home directory seed old `.murmur` settings/stats, invoke migration, compare content; existing `.keystow` data must not be overwritten. Exercise malformed settings and failed migration permissions.
- [ ] HARDWARE: upgrade an old install, check preferences/stats, shortcut registration and autostart target; no duplicate running apps. Preserve user data.
- [ ] HARDWARE: quit during idle, recording, loading and processing; no orphan recording, model-thread crash, stuck key, or unexplained loss. Restart successfully.

### 6. Coherent app and page experience

- [ ] Inspect rendered app pixels at normal and narrow sizes for loading, ready, listening, processing, empty transcript and error states. Record screenshots after user-visible changes.
- [ ] First-time journey explains purpose, where text will go, toggle versus hold, local base versus downloaded models, and closing-to-tray versus quitting. Controls agree with behavior and use plain language.
- [ ] Record button and model/hotkey controls must not imply actions are available when the controller rejects them. Errors explain recovery; transcript recovery must be possible, not merely promised.
- [ ] Inspect the live page and README against actual release evidence: price is $5 lifetime, MIT source is distinct from paid distribution, no unsupported universal OS/app, zero-error, accuracy or privacy promises. No launch/checkout is implied by repo docs.
- [ ] On each UI/copy change, repeat the affected journey, capture pixels, and rerun startup/lifecycle regressions. Cosmetics do not certify working dictation.

### 7. Packaging and platform gates

- [ ] Inspect CI for the intended commit, not an older green run. Verify model-download/build/release jobs actually passed.
- [ ] Check release names, asset size/hash, and both actual download links. Record run/release URLs and commit. Do not overwrite the evidence with just a success badge.
- [ ] RELEASE: Windows downloaded-artifact install and dictation journey passes before calling that release tested.
- [ ] RELEASE: separately install on the intended Apple Silicon/macOS version; verify microphone and Accessibility permission denial/recovery, global key, local transcription, external insertion and removal. A macOS build alone is not support validation.

## Evidence log

| Date | Change | Check / environment | Result | Limits / next |
|---|---|---|---|---|
| 2026-11-17 | Restore controller startup | Python 3.10.12, PySide6 6.8.3, Linux offscreen Qt | Baseline failed: never started, collected. Fixed code passes startup and compile checks locally. | Public push/CI confirmation pending; no real microphone or OS paste verified. |

Update checked boxes and this log only after the evidence exists. A failed check is useful evidence and must remain visible until fixed and rechecked. After each completed step, report the actual result and next risk to the project planning conversation. Hourly review is a backstop, not permission to idle while useful work is ready.

## Component evidence now in public source

- Threaded controller check holds inference on an event while repeated capture/stop/hotkey/model-switch requests arrive: only one capture/worker/paste occurs.
- Forced inference failure followed by a successful next session pastes only recovered text. Paste failure keeps a selectable transcript; a statistics disk error does not suppress usable text.
- Real Qt window plus controller: optional-model load failure restores visible base selection, controls re-enable, next dictation uses the prior model (peripheral I/O substituted).
- Quit during held inference discards late output and rejects new work. Quit during recording stops/discards capture. Real Qt event loop waits for a running QThread before exit. A running model download is not forcibly cancelled; shutdown may wait for its network timeout.
- Real Qt listening/processing/error pixels inspected after changes: clear Stop and type action, transparent labels, active-state controls disabled, selectable recovery transcript, error points below. Rendered states were injected; this is not real microphone evidence.
- Historical copy defects were corrected: README no longer claims universal app/Intel Mac support; both release assets exist; live page has dual platform CTAs. Hardware/platform acceptance is still open.
- Local environment: Python 3.10.12, PySide6 6.8.3, Linux offscreen. Checks: `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`; `python -m compileall -q keystow tests`. Actual audio, OS keyboard, clipboard and installed-release journeys remain OPEN.

## Additional evidence after the first follow-up bundle

- Real `Transcriber`, faster-whisper 1.2.1 / CTranslate2 4.9.0, CPU int8 base, Python 3.10.12 on Linux: public upstream JFK sample transcribed to the upstream expected sentence. Silence/empty produced no text. Repeated with `HF_HUB_OFFLINE=1` and Python socket connection denied, explicit local model directory. Missing RNNoise library fell back correctly with suppression requested. This does not establish target-device latency, accuracy across speakers, actual mic capture or packaged offline startup. See `docs/evidence/inference-2026-11-17.json`.
- Real temporary filesystem: old-data migration, existing-destination preservation and copy fallback passed. Valid JSON arrays reproduced settings/stats startup crashes; type validation and atomic same-directory writes fixed locally. Injected replacement failure retains the last-good file and cleans temporary files. Installed upgrades remain OPEN.
- Real recorder logic with controlled stream: start failure closes the partly initialized stream; stop failure closes it; audio frames are cleared after delivery/failure; immediate retry succeeds. These are stream-ownership component checks, not PortAudio hardware evidence.
- README/page corrections rendered in Chrome at desktop and 390px mobile. No overflow/crop found. These are local previews, not proof of deployed page state.
- Public branch and released-binary evidence must stay separate. The current engineering recovery changes are branch-only; no installer rebuild was triggered for them.

## 2026-11-18 recovery findings and remaining boundaries

- Clipboard dispatch failure reproduced a held modifier and temporary text left behind; unconditional restoration overwrote newer clipboard text. Branch fix tracks owned keys for finally cleanup and restores old text only while temporary text still matches. Error preserves transcript and warns that text may already be inserted. Non-atomic compare/write race, text-only clipboard preservation and focus-dependent target remain limitations.
- A file occupying the logs directory blocked startup. Branch logging setup is best effort, local-only and retryable after storage repair; native fault trace failure does not disable ordinary logging. That earlier logging-only patch did not fix an inaccessible whole data directory during imports; the separate startup-storage patch below addresses that reproduced obstruction.
- First-run autostart registration OSError wrongly saved initialized=True. Branch fix marks initialization only on success and retries a later launch without overriding an explicit later opt-out. Windows installs register HKCU Run; Mac registers LaunchAgent on first successful app launch. This is login, not wake-from-sleep or crash restart. Real OS behavior is unverified.
- Short-speech diagnostic: same cached offline base CPU-int8 model rejected a genuine0.32s word due to no_speech_prob>.6; padding changed confidence. A44-case artificial word/context matrix also included wrong raw outputs rejected by filters. Three repeated speech/silence sequences showed no stale-text leakage. These clipped single-speaker English samples are NOT an accuracy benchmark and do NOT justify threshold/padding changes. Independent natural short-speech fixtures, silence/noise controls and real mic journeys are still needed.

## 2026-11-18 startup-storage recovery and v1.0.2 gate

- COMPONENT: a real regular file at the intended home `.keystow` path reproduced an import-time startup crash. The fix retains that canonical path and obstruction, does not delete/rename it or redirect data, and lets the UI open with a persistent warning and word counts unavailable.
- COMPONENT: actual temporary-home subprocess checks cover blocked-file startup, visible warning plus synthetic transcript, failed noise-setting save, user repair, successful retry and fresh-process saved-value readback. Injected mkdir permission denial and unobstructed startup are separate cases. Actual offscreen Qt530x700 and360x700 pixels were inspected; narrow warning clipping was fixed. This is not installed or microphone evidence.
- COMPONENT: failed noise writes restore the last saved value. Hotkey first/second persistence-write errors preserve the prior active key and UI; autostart OS failure is visible and retryable. The model selector has no settings write. No general later-storage health check, backup or automatic model repair is claimed.
- COMPONENT: simulated macOS LaunchAgent construction is parsed with plistlib and written atomically. Real launchd acceptance remains OPEN.
- COMPONENT: v1.0.2 release-asset verifier tests cover wrong names, upload state, zero metadata size, mismatched SHA256, missing/extra assets, wrong tag/non-draft and a passing pair. The actual new CI path remains unexecuted.
- RELEASE GATE, not completed evidence: preserve the newer page/README, verify the exact combined tree from a fresh public clone, record full tests/compile/whitespace/YAML/workflow checks, exact SHA and zero v1.0.1 references in the retargeted build workflow, and compare prior release identities/assets against the recorded baseline. Tonight requires the pre-dispatch bundle and explicit owner GO before any dispatch.
- The proposed workflow stages artifacts from both current-run builds, creates one draft with both assets and no clobber, verifies exact names/upload state/nonempty sizes/SHA256 against staged files, and only then undrafts. Workflow source review and verifier tests are not evidence that this path has run successfully. Failures hold; prior release assets stay untouched.
