# Changelog

Every version of KeyStow, newest first. This file is where release notes are written: the release workflow publishes the section for the version being released as that release's notes on GitHub.

Do not use the Mac installers of v1.0.0 to v1.0.5: they could not get microphone access.

## v1.0.7

KeyStow v1.0.7 stops older text from being pasted, answers faster, and has a new look that matches the website.

- Windows: no more stale pastes. KeyStow now learns when the app you are dictating into actually reads the text, and only then puts your previous clipboard back (pictures, files and formatted text included). If the app has not read it in time, your dictation stays on the clipboard, so a late paste still gets the right words. An older dictation is never put back, and anything you copy in the meantime is never overwritten.
- Windows: KeyStow pastes only into the window that was in front when you let go of the key. If you switched windows, if KeyStow itself is in front, or if the window runs as administrator, it does not paste and says why. Use the new Copy button (also in the tray menu) to paste the text yourself. Each recording is pasted at most once.
- Windows: dictated text is kept out of Windows clipboard history and Cloud Clipboard.
- Faster: noise suppression now runs while you speak instead of after you let go. On a 2-core laptop, the wait after a 5-second sentence went from about 1.6 to 1.0 seconds, and after a 14-second one from about 3.1 to 1.4 seconds. KeyStow also asks Windows not to slow it down while it is minimised.
- If the system misses the release of your shortcut key, KeyStow notices within a fraction of a second and stops listening, instead of joining two dictations together.
- New look: the window, tray icons and installers now match the website: the KeyStow logo, Instrument Sans and a light design. The status says in words what is happening (Ready, Listening, Pasted, Not pasted).
- Choose "Press to start, press to stop" if holding a key is hard. The window has keyboard focus rings and screen-reader names, and a short "Try it now" guide on first start.
- KeyStow never downloads a speech model without asking: choosing a larger model shows its size and waits for your OK. If the built-in model is missing or damaged, KeyStow says to reinstall instead of downloading it.
- Smaller: the Windows app takes about 385 MB instead of about 534 MB. Video libraries the app never used (FFmpeg, including the x264 and x265 encoders) and unused parts of Qt are gone.
- Updating on Windows: the installer closes a running KeyStow for you.
- Mac: fixes KeyStow closing at start-up or on the first dictation. It reads the keyboard layout once on the main thread, as macOS requires. If that is not possible, KeyStow starts without the shortcut and says so, instead of closing.
- Mac: at start, KeyStow asks macOS for Accessibility access, so macOS shows its own prompt with a button to the right setting. If access is still missing when your text is ready, the text is left on the clipboard and the window says so.
- Mac: KeyStow needs Apple Silicon and macOS 14 or later. On an older macOS the system now says so. The disk image includes "Open KeyStow the first time", with the one-time steps.
- The diagnostic log no longer gets a line for every dictation and can now roll over on Windows. Both installers include the licences of the third-party software inside them.

Quit KeyStow before installing the update on a Mac. On a Mac, after replacing the app, remove KeyStow from System Settings > Privacy & Security > Accessibility and add it again: macOS treats each update of an app like this one as a new app. KeyStow understands English. The Windows x64 and Apple Silicon Mac installers include the base model. The Windows installer is unsigned; the Mac app is ad-hoc signed and not notarized.

Checks on this build: component tests passed on Windows and macOS; KeyStow's clipboard handling passed its round-trip checks on a real Windows clipboard on a test machine; and the packaged app on both loaded its own speech model and transcribed a recorded speech sample. Before publication, a real microphone, the global shortcut and pasting into other apps must be tried on real hardware; the result is recorded here when this version is promoted.

## v1.0.6 - 2026-11-22

KeyStow v1.0.6 installs as an ordinary app, starts quietly at sign-in, and fixes the Mac setup.

- No more unpacking at every start. Earlier versions unpacked about 500 MB into the temp folder each time they started, and could leave it behind after a shutdown, an update or a crash. KeyStow is now installed as normal files and starts faster. On Windows it also removes the folders earlier versions left behind.
- Started at sign-in, KeyStow now opens minimised instead of on top of your work. Opening it yourself shows the window as before. Closing the window still quits KeyStow.
- Mac: the app now carries the microphone permission entry macOS requires, so it can ask for microphone access. The window explains the Accessibility permission that the shortcut and pasting need, and says so when macOS is blocking the shortcut. The default key on a Mac is now Right Option, because MacBook keyboards have no Right Ctrl; a key you chose yourself is kept. The disk image includes an Applications shortcut for drag-install.
- If no sound at all reaches KeyStow from the microphone, it now says so and points to the microphone setting.
- The version number is shown at the top of the tray menu.

Quit KeyStow before installing the update. KeyStow understands English. The Windows x64 and Apple Silicon Mac installers include the base model. The Windows installer is unsigned; the Mac app is ad-hoc signed and not notarized.

Checks on this build: component tests passed on Windows and macOS, the packaged app on both loaded its own speech model and transcribed a recorded speech sample, and the packaged app on both passed launch, second-launch and close checks. Not tested before release: a real microphone, the global shortcut and pasting into other apps on real hardware; on the Mac that includes the permission prompts. The v1.0.5 Windows installer stays available if you need to go back.

## v1.0.5 - 2026-11-22

KeyStow v1.0.5 starts when you sign in by default, and includes the v1.0.4 fixes.

- Start at sign-in is on by default. On Windows it is a ticked option in the installer, and the installer remembers your choice on later updates. On Mac the app switches it on once, the first time it runs. To stop KeyStow starting at sign-in, switch it off from the KeyStow tray or menu bar icon; it stays off.
- The activation key no longer waits on microphone, disk or paste work, so it should not stall or stop responding after a dictation.
- A tap shorter than 0.3 seconds is ignored instead of being transcribed, and a recording left running stops at 120 seconds.
- Your previous clipboard text is put back 0.3 seconds after the paste instead of 0.05 seconds, so slower apps paste the dictated text and not the old clipboard.
- New Windows installs go to your per-user Programs folder. Existing installs stay where they are.

Quit KeyStow before installing the update. The Windows x64 and Apple Silicon Mac installers include the base model. The Windows installer is unsigned; the Mac app is ad-hoc signed and not notarized.

Component tests passed on Windows and macOS for this build, and the packaged Windows and Mac apps passed launch, second-launch and close checks on the build machines. Physical microphone, global shortcut and paste behaviour were not tested on real hardware before release.

## v1.0.4 - 2026-11-22

KeyStow v1.0.4 keeps the activation key responsive and makes start at login a choice.

- The activation key no longer waits on microphone, disk or paste work, so it should not stall or stop responding after a dictation.
- A tap shorter than 0.3 seconds is ignored instead of being transcribed, and a recording left running stops at 120 seconds.
- Your previous clipboard text is put back 0.3 seconds after the paste instead of 0.05 seconds, so slower apps paste the dictated text and not the old clipboard.
- Start at login is no longer switched on at first run. Choose it in the Windows installer or in the app. An existing choice is kept.
- New Windows installs go to your per-user Programs folder. Existing installs stay where they are.

Component tests passed on Windows and macOS for this build, and the packaged Windows and Mac apps passed launch, second-launch and close checks on the build machines. Physical microphone, global shortcut and paste behaviour were not tested on real hardware before release.

## v1.0.3 - 2026-11-20

KeyStow v1.0.3 fixes duplicated dictation caused by multiple running copies. One dictation process per user; reopening raises the existing window. Closing the window now quits instead of hiding in the tray, stops recording and listening, discards late text and exits after worker cleanup. Quit all older KeyStow copies once before upgrading.

## v1.0.2 - 2026-11-19

Recovery update: paste-key cleanup and conditional clipboard restoration, best-effort local diagnostic logging, retryable login registration, safe Mac login-file handling, and bounded startup-storage recovery with a visible warning and a retry after the user repairs the folder. Hold-to-speak remains the default for uncustomised installs; explicit modes and earlier custom keys are preserved.

## v1.0.1 - 2026-11-18

Hold-to-speak becomes the default for uncustomised installs. An earlier custom key keeps its press-to-start, press-to-stop behaviour. Fixes an interrupted move of settings from the earlier data folder.

## v1.0.0 - 2026-11-17

First release: push-to-talk voice typing for Windows and Mac.
