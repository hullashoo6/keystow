# KeyStow

Speak instead of typing. Put your cursor in a text field, hold a key, speak, and release: KeyStow turns your speech into text on your own computer and pastes it where the cursor is.

- **Website and purchase:** <https://hullashoo6.github.io/keystow/>. The ready-to-install app for Windows and Apple Silicon Mac costs $5 once.
- **Source:** the code in this repository is available under the [MIT license](LICENSE).
- **Support:** hullashoo6@gmail.com

## Using it

- **Shortcut.** Hold the key while you speak and release it to paste. The default is Right Ctrl on Windows and Right Option on a Mac. Choose another key in the window or from the tray icon.
- **Where the text goes.** KeyStow pastes into whichever app is focused when the text is ready, so keep the cursor where you want it. Some secure or elevated fields refuse pasted text.
- **Closing the window quits KeyStow.** Minimise it to keep dictation available. To leave, close the window or choose Quit KeyStow from the tray icon.
- **Start at sign-in** is on by default: a ticked option in the Windows installer, and switched on once at first run on a Mac. Started that way, KeyStow opens minimised. Switch it off from the tray icon.
- **Language.** KeyStow transcribes English.
- **Models.** The base model ships inside the app and needs no download. Larger models download once, the first time you pick them.
- **Mac permissions.** macOS asks for Microphone access, and the shortcut and pasting need Accessibility access. Allow both under System Settings > Privacy & Security, then quit and reopen KeyStow.

Transcription can be wrong, so read text before you send it. KeyStow puts the text on the clipboard to paste it and then restores the text that was there before; images and files on the clipboard are not preserved.

## Privacy

Audio is captured in memory, transcribed on your computer and discarded. KeyStow does not save recordings, keep a transcript history, upload audio or send usage data. The network is used only when you choose a larger model, which downloads once from Hugging Face.

The `.keystow` folder in your user folder holds your settings, daily word counts and a rotating diagnostic log. The log records errors and file paths, not what you dictated.

## What each release is checked for

The release workflow builds both installers and publishes only if all of this passes:

- the component tests, on Windows and on an Apple Silicon Mac;
- the packaged app itself loading the speech model it ships with and transcribing a recorded speech sample, on both;
- the packaged Windows app opening its window, refusing a second copy and closing cleanly;
- the Mac app's signature, checked again inside the finished disk image;
- the uploaded files matching the built files byte for byte.

These checks do not use a real microphone, the global shortcut or another app to paste into. Those are tested by hand on real computers. The installers are not code-signed, so Windows and macOS show a warning the first time.

## Run from source

1. Install Python 3.10 or later.
2. Clone this repository.
3. On Windows run `install_windows.bat`, then `run_windows.bat`. Elsewhere, create a virtual environment, `pip install -r requirements.txt`, and run `python -m keystow`.

A source run downloads the speech model the first time, cannot register itself to start at sign-in, and has noise suppression only where the RNNoise library is present.

## Tests

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

On Windows PowerShell, set `$env:QT_QPA_PLATFORM = 'offscreen'` first. The tests substitute the microphone, the speech model, the keyboard and the clipboard, and they use private temporary folders, so they are safe to run next to an installed KeyStow.

## Releasing

1. Set the new version in `installer/setup.iss` and `keystow/__init__.py`, and write `installer/release-notes.md` for it.
2. Run the **Build and release KeyStow installers** workflow from `main` with that version.

Library versions for release builds are pinned in `installer/constraints.txt`. The website lives in `docs/` and its download buttons always point at the latest release. Working notes from earlier development are in `notes/`.
