KeyStow v1.0.6 installs as an ordinary app, starts quietly at sign-in, and fixes the Mac setup.

- No more unpacking at every start. Earlier versions unpacked about 500 MB into the temp folder each time they started, and could leave it behind after a shutdown, an update or a crash. KeyStow is now installed as normal files and starts faster. On Windows it also removes the folders earlier versions left behind.
- Started at sign-in, KeyStow now opens minimised instead of on top of your work. Opening it yourself shows the window as before. Closing the window still quits KeyStow.
- Mac: the app now carries the microphone permission entry macOS requires, so it can ask for microphone access. The window explains the Accessibility permission that the shortcut and pasting need, and says so when macOS is blocking the shortcut. The default key on a Mac is now Right Option, because MacBook keyboards have no Right Ctrl; a key you chose yourself is kept. The disk image includes an Applications shortcut for drag-install.
- If no sound at all reaches KeyStow from the microphone, it now says so and points to the microphone setting.
- The version number is shown at the top of the tray menu.

Quit KeyStow before installing the update. KeyStow understands English. The Windows x64 and Apple Silicon Mac installers include the base model. The Windows installer is unsigned; the Mac app is ad-hoc signed and not notarized.

Checks on this build: component tests passed on Windows and macOS, the packaged app on both loaded its own speech model and transcribed a recorded speech sample, and the packaged app on both passed launch, second-launch and close checks. Not tested before release: a real microphone, the global shortcut and pasting into other apps on real hardware; on the Mac that includes the permission prompts. v1.0.5 stays available if you need to go back.
