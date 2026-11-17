# Murmur

**Speak softly, it's typed.**

Your voice, typed anywhere. Free and local forever - no subscription, no cloud, no account.

Press a key, speak naturally, press again. Polished text appears wherever your cursor
is - Chrome, WhatsApp, VS Code, Word, anywhere. Powered by OpenAI's Whisper,
running entirely on your own machine. Your audio never leaves your device.

## Why people switch

- **No subscription.** Wispr Flow charges monthly. This runs free, forever.
- **Private by design.** Transcription happens on your device. Nothing is uploaded.
- **Works everywhere.** If you can click it, you can talk into it.

## Setup (Windows, about 5 minutes)

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/)
   (tick **"Add python.exe to PATH"** during setup).
2. Download this repository: **Code -> Download ZIP**, then unzip it.
3. Double-click **`install_windows.bat`**.
4. Double-click **`run_windows.bat`** (or run `python -m murmur`). Murmur lives in your system tray - press the key, speak, press again to type.

The first launch downloads the speech model (~75 MB, one time only). After that
everything works offline.

## Setup (Mac - Apple Silicon: M1, M2, M3, M4)

1. Download **MurmurMac.dmg** from the
   [latest release](https://github.com/hullashoo6/murmur/releases/latest),
   open it, and drag Murmur into Applications.
2. First launch: right-click the app and choose **Open**, then click **Open**
   again in the dialog. (Or: System Settings -> Privacy & Security ->
   **Open Anyway**.) Murmur isn't signed with an Apple certificate yet, so
   macOS asks for this one-time confirmation - normal for indie apps.
3. macOS will ask for two permissions, both required:
   - **Microphone** - so Murmur can hear you.
   - **Accessibility** (System Settings -> Privacy & Security -> Accessibility) -
     so Murmur can hear your hotkey and type into other apps.

The download is for Apple Silicon Macs. Intel Macs aren't covered by the
installer yet - running from source (Python 3.10+) works there.

## Using it

- Press `Right Ctrl` once anywhere and speak. Press it again - your words
  type themselves into the active app.
- Change the activation key from the tray menu (Right Ctrl, Caps Lock,
  Right Shift, Right Alt, or capture a custom key).
- Murmur lives in the system tray. Double-click the tray icon to open the
  window - it shows what it heard and your word counts (today + all time).
- Turn on **Start with Windows** in the tray menu to keep it always ready.
- Prefer hold-to-talk? Set `TOGGLE_MODE` in `murmur/config.py`.
- Bigger model for more accuracy? Pick it from the app's Model dropdown.

## Privacy: what's stored

Everything stays on your machine. Murmur keeps exactly two small local files
(in a `.murmur` folder in your user directory):

- `settings.json` - your model, hotkey and start-with-Windows preferences.
- `stats.json` - your word counts (today and all time), for the dashboard.

Your audio is never saved, nothing is uploaded, there is no telemetry,
and there is no account.

## Roadmap

| Version | What you get |
|---------|--------------|
| **V1** (now) | Push-to-talk, offline transcription, automatic typing, clean UI |
| V2 | AI cleanup: filler-word removal, punctuation, grammar |
| V3 | Custom vocabulary, writing styles, more languages |
| V4 | Floating toolbar, settings, transcription history |
| V5 | Hands-free mode, advanced voice commands |

## Tech

Python + [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (local
speech-to-text) + PySide6 (UI) + pynput/pyperclip (typing into any app).

## License

MIT - see [LICENSE](LICENSE).
