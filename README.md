# Murmur

**Speak softly, it's typed.**

Your voice, typed anywhere. Free and local forever - no subscription, no cloud, no account.

Hold a key, speak naturally, release. Polished text appears wherever your cursor
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
4. Double-click **`run_windows.bat`** (or run `python -m wisprflow`).

The first launch downloads the speech model (~75 MB, one time only). After that
everything works offline.

## Using it

- **Hold** `Right Ctrl` anywhere and speak. **Release** - your words type
  themselves into the active app.
- Or press the big **Hold to talk** button in the app window.
- The window shows what it heard, so you always know what was typed.
- Press `Esc` to quit.

Want a different hotkey or a smarter (bigger) model? Change the model in the
app's dropdown, or set `WISPR_HOTKEY` / `WISPR_MODEL` in `wisprflow/config.py`.

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
