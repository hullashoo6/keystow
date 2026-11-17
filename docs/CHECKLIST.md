# KeyStow living acceptance checklist

Updated 2026-11-17. This is a record of evidence, not a feature list.

Labels: **OPEN** = insufficient evidence; **COMPONENT** = isolated logic or offscreen check; **HARDWARE** = real OS/device journey; **RELEASE** = actual downloaded installer journey. Never promote a component result to a hardware or release claim.

## Current truth

- Baseline inspected: `3178afb`.
- Startup regression reproduced: `run_app` discarded the controller and never called `start()`. Introduced by `3bf5d53` (tray UI rewrite), not the rename. Earlier source started correctly.
- Startup fix verified on public main at `71a66de`; startup regression file verified byte-identical at `210f231`. Local check fails on baseline and passes on fixed code. Installer build `44125878593` is still queued, not accepted.
- Latest installer build/release is not yet accepted. A Windows asset exists; macOS asset was absent at baseline. Asset existence is not installation evidence.
- Real Windows and macOS microphone/hotkey/paste journeys remain OPEN. Earlier owner V1 use does not certify later changes.

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

## Local follow-up evidence awaiting public commit

- Threaded controller check holds inference on an event while repeated capture/stop/hotkey/model-switch requests arrive: only one capture/worker/paste occurs.
- Forced inference failure followed by a successful next session pastes only recovered text. Paste failure keeps a selectable transcript; a statistics disk error does not suppress usable text.
- Real Qt window plus controller: optional-model load failure restores visible base selection, controls re-enable, next dictation uses the prior model (peripheral I/O substituted).
- Quit during held inference discards late output and rejects new work. Quit during recording stops/discards capture. Real Qt event loop waits for a running QThread before exit. A running model download is not forcibly cancelled; shutdown may wait for its network timeout.
- Real Qt listening/processing/error pixels inspected after changes: clear Stop and type action, transparent labels, active-state controls disabled, selectable recovery transcript, error points below. Rendered states were injected; this is not real microphone evidence.
- Remaining observed claims defects: README free-forever/works-everywhere/two-files copy and unverified Intel-Mac claim; page polished-anywhere claim and Mac download before confirmed asset. Corrections remain open.
- Local environment: Python 3.10.12, PySide6 6.8.3, Linux offscreen. Checks: `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`; `python -m compileall -q keystow tests`. Actual audio, OS keyboard, clipboard and installed-release journeys remain OPEN.
