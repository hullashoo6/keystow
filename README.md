# KeyStow

Speak instead of typing. Put your cursor in a text field, hold a key, speak, and release: KeyStow turns your speech into text on your own computer and pastes it where the cursor is.

- **Website and purchase:** <https://keystow.pages.dev/>. The ready-to-install app for Windows and Mac costs $5 once.
- **Source:** the code in this repository is available under the [MIT license](LICENSE).
- **Support:** hullashoo6@gmail.com
- **What changed in each version:** [CHANGELOG.md](CHANGELOG.md)

## What it runs on

- **Windows:** 64-bit (x64), Windows 10 or 11. The installed app takes about 385 MB; the installer download is about 195 MB.
- **Mac:** macOS 14 or later. The app is one universal build that runs on Apple Silicon and Intel. The installed app takes about 536 MB; the download is about 267 MB.

## Using it

- **Shortcut.** Hold the key while you speak and release it to paste. The default is Right Ctrl on Windows and Right Option on a Mac. Choose another key in the window or from the tray icon.
- **Where the text goes.** On Windows, KeyStow pastes only into the window that was in front when you released the key. If you switched windows, if KeyStow itself is in front, or if the window runs as administrator, it does not paste and says why; use the Copy button to paste the text yourself. On a Mac, KeyStow pastes into the app in front when the text is ready, so keep the cursor where you want it. Some secure or elevated fields refuse pasted text.
- **Closing the window quits KeyStow.** Minimise it to keep dictation available. To leave, close the window or choose Quit KeyStow from the tray icon.
- **Start at sign-in** is on by default: a ticked option in the Windows installer, and switched on once at first run on a Mac. Started that way, KeyStow opens minimised. Switch it off from the tray icon.
- **Language.** KeyStow transcribes English.
- **Models.** The base model ships inside the app and needs no download. Larger models download once, the first time you pick them.

Transcription can be wrong, so read text before you send it. KeyStow puts the text on the clipboard to paste it. On Windows, your previous clipboard contents (pictures, files and formatted text included) are put back once the app you dictated into has read the text; if it has not read it in time, your dictation stays on the clipboard instead. On a Mac, the previous text is restored on a timer, and earlier images or files are not preserved.

## First start on a Mac

The app is not notarized by Apple, so macOS blocks the first launch. Open System Settings > Privacy & Security, scroll to Security, and choose Open Anyway.

KeyStow then needs two permissions under Privacy & Security:

- **Microphone.** macOS asks the first time you dictate.
- **Accessibility**, for the shortcut and for pasting. KeyStow asks macOS for it at start and macOS shows a prompt with a button to the setting. After allowing it, quit and reopen KeyStow.

If Accessibility is missing when your text is ready, KeyStow leaves the text on the clipboard and says so. Depending on the macOS version, the system may also list KeyStow under Input Monitoring; Accessibility is the one it needs.

**When you update to v1.0.8 on a Mac**, remove KeyStow from the Accessibility list with the minus button and add it again once. From v1.0.8 the app is signed with KeyStow's own certificate, so it keeps the same identity from one version to the next and macOS can keep the permission across later updates. The app is still not notarized by Apple, so the one-time confirmation on first open remains.

## Removing it

- **Windows:** uninstall KeyStow from Settings > Apps. Your settings, word counts and log stay in the `.keystow` folder in your user folder; delete it if you want them gone.
- **Mac:** switch off Start at login from the menu bar icon, quit KeyStow and move it to the Trash. Then delete the `.keystow` folder in your home folder and, if it is still there, `~/Library/LaunchAgents/com.keystow.app.plist`.

Larger models you downloaded are in the Hugging Face cache (`.cache/huggingface` in your user folder).

## Privacy

Audio is captured in memory, transcribed on your computer and discarded. KeyStow does not save recordings, keep a transcript history, upload audio or send usage data. The network is used only when you choose a larger model, which downloads once from Hugging Face.

The `.keystow` folder in your user folder holds your settings, daily word counts and a rotating diagnostic log. The log records start-up, errors and file paths. It does not record what you dictated, and from v1.0.7 it no longer records a line for each dictation.

Dictated text passes through the system clipboard on its way to the cursor. If you use clipboard history or clipboard syncing between devices, those features can see it like any other copied text.

## Licences of what is inside

The installers contain third-party software under its own licences, including Qt and pynput (LGPL). v1.0.6 and earlier also bundled FFmpeg libraries (LGPL); they are gone from v1.0.7 onwards. From v1.0.7 the notices and licence texts ship with the app: the `licenses` folder next to `KeyStow.exe` on Windows, and `Contents/Resources/licenses` inside the app on a Mac. `installer/collect_licenses.py` gathers them at build time and `installer/third-party-notes.txt` says where each part's source is.

## What each release is checked for

The release workflow builds both installers and publishes only if all of this passes:

- the component tests, on Windows and on an Intel Mac (the Apple Silicon check runs by hand, outside the release workflow);
- the packaged app itself loading the speech model it ships with and transcribing a recorded speech sample, on both;
- the packaged Windows app opening its window, refusing a second copy and closing cleanly;
- the Mac app's signature, checked again inside the finished disk image;
- the uploaded files matching the built files byte for byte.

These checks do not use a real microphone, the global shortcut or another app to paste into. Only a person at a real computer can check those, which is why a new version is published as a pre-release first; each version's notes in the changelog say what had and had not been tried by hand. The Windows installer is unsigned, so Windows may show a SmartScreen prompt the first time. The Mac app is signed with KeyStow's own certificate but not notarized by Apple, so macOS asks you to confirm the first open.

## Run from source

1. Install Python 3.11, the version releases are built and tested with (3.10 or later may work).
2. Clone this repository.
3. On Windows run `install_windows.bat`, then `run_windows.bat`. Elsewhere, create a virtual environment, `pip install -r requirements.txt`, and run `python -m keystow`.

A source run downloads the speech model the first time, cannot register itself to start at sign-in, and has noise suppression only where the RNNoise library is present.

## Tests

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

On Windows PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` first. The tests substitute the microphone, the speech model, the keyboard and the clipboard, and they use private temporary folders, so they are safe to run next to an installed KeyStow.

## Changing and releasing

The version number lives in one place, `keystow/__init__.py`. Release notes live in one place, `CHANGELOG.md`.

1. Make the change on a branch and open a pull request. If it touches the app or its build, the pull request builds both installers and runs every release check without publishing anything; the installers are attached to that run as artifacts.
2. To ship: set the new version in `keystow/__init__.py`, add a `## v<version>` section at the top of `CHANGELOG.md`, and merge.
3. Run the **Build and release KeyStow installers** workflow from `main` with that version. It publishes a pre-release. The website's download buttons keep serving the previous release.
4. Install the pre-release on a real Windows PC and a real Mac and dictate into another app.
5. Run the **Promote a tested pre-release** workflow with the same version. The website now serves it. If the test failed, fix it and ship the next version number instead; a published version is never replaced.

Library versions for release builds are pinned in `installer/constraints.txt`. The website lives in `docs/` and its download buttons always point at the latest release. Working notes from earlier development are in `notes/`.
