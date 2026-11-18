# KeyStow

Speak softly, it's typed.

Local voice typing: focus an editable field, hold a key while speaking, then release it to request a paste of the transcript. Speech recognition uses faster-whisper on your own machine.

KeyStow is an AI-assisted project under active reliability testing. It is not a verified feature-for-feature Wispr Flow replacement. See the [product vision](docs/PRODUCT_VISION.md) and [living acceptance checklist](docs/CHECKLIST.md) for evidence and open checks.

## Price and source

The owner-set product price is **$5 one-time, lifetime**. Source code remains available under the [MIT license](LICENSE). This repository does not activate a checkout or change that license. No paid transcription API or app account is required by the current core implementation.

## Current verification boundary

Windows is the first validation target. A packaged build, an existing download, and a green CI job do not establish that real microphone capture, global shortcuts or insertion work on every machine. macOS packaging is a separate validation track; do not infer Intel Mac support or a tested release from source availability.

Use the release notes and checklist for the tested commit and actual artifact state. Real OS/device journeys remain required.

## Windows

### Packaged build

Check the [release](https://github.com/hullashoo6/keystow/releases/latest) for `KeyStowSetup.exe`. Install only an artifact whose source and release you trust. Builds are not code-signed; Windows may warn about an unknown publisher. An unsigned warning is not proof that any download is safe.

The installer build is intended to bundle the **base** speech model so core dictation can run without a first-run model download. This must be verified against the actual downloaded release. Other models require an internet download before local use.

### Run from source

1. Install Python 3.10 or later from [python.org](https://www.python.org/downloads/).
2. Download or clone this repository.
3. Run `install_windows.bat`, then `run_windows.bat`, or create a virtual environment, install `requirements.txt`, and run `python -m keystow`.

Source installs do not include the bundled speech model. First model load normally downloads it; later use depends on the local model cache. Download size and speed depend on the chosen model and connection.

## macOS

The workflow targets an Apple Silicon app named `KeyStowMac.dmg`. Confirm that it exists in the release before trying it. Installation, signing/security behavior, microphone and Accessibility permissions, hotkeys, and insertion still require independent real-Mac verification. No Intel Mac installer or compatibility guarantee is offered here.

## Use

- Current source default for uncustomized installs: **hold Right Ctrl** while speaking, then **release** to stop and transcribe.
- Focus the destination field first. Clipboard insertion acts on the app focused when paste is requested. Changing focus during processing can send text to a different field. Secure/elevated fields and some apps may reject paste.
- Use the tray menu or window to choose an activation key. Avoid keys that conflict with shortcuts you depend on.
- Close the window to hide it to the tray; choose **Quit KeyStow** in the tray menu to exit.
- Model loading and transcription can take time on CPU. Larger models need more storage and memory and are not automatically better for every device or utterance.
- Existing saved key customizations (including a saved Right Ctrl selection) conservatively retain prior toggle behavior: press once to start, press again to stop. Changing a key now saves the active mode too.
- `KEYSTOW_TOGGLE=0` explicitly selects hold; `KEYSTOW_TOGGLE=1` selects toggle. Environment mode wins over saved `activation_mode` (`hold` or `toggle`), which wins over the legacy custom-key rule. An explicit `KEYSTOW_HOTKEY` without a mode also retains legacy toggle behavior. Startup does not rewrite preferences.
- The published **v1.0.1 installers use hold by default for uncustomized installs**. Older **v1.0.0 installers default to toggle**. Both v1.0.1 build jobs passed and both downloads were hash-verified; actual installed microphone, hotkey and paste acceptance remains open. Check the exact version and custom settings before following instructions.
- Start-at-login is available in the tray menu. Check its actual setting and installed path after upgrades.

Transcription is fallible. Review text before sending or using it. The app does not independently verify that a destination accepted the paste. Clipboard restoration is text-only and can be affected by other apps; do not rely on it to preserve images, files or rich clipboard formats.

## Local data and network behavior

Current application code captures audio in memory, performs speech recognition locally, and uses the OS clipboard for insertion. It does not intentionally save recordings, upload audio or send telemetry. Optional model downloads and source dependency installation use the network; this is distinct from cloud transcription.

The `.keystow` folder in your user directory holds preferences, word counts, and rotating diagnostic logs. On first use, the code attempts to migrate an existing `.murmur` data folder. Logs may contain error details and local paths; review them before sharing. The transcript stays visible in the current window and temporarily passes through the clipboard.

Noise suppression has a native-library fallback. If the library is unavailable or fails, audio passes through without that suppression. A checked box does not prove suppression ran successfully on a particular platform.

## Checks for contributors

With PySide6 installed:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
python -m compileall -q keystow tests
```

On Windows PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` before running unittest. These checks exercise startup, controller transitions and Qt behavior with substituted peripheral I/O. They do not certify real microphone capture, model accuracy, OS hotkeys, clipboard behavior or an installed release. Follow the checklist for those journeys.

## Near-term work

Prove the default install-to-dictation journey, make failures recoverable, and keep app/page copy consistent with actual behavior. Cloud cleanup, extra modes and new platform claims are deferred until the core is demonstrated.
