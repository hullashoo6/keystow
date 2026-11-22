KeyStow v1.0.5 starts when you sign in by default, and includes the v1.0.4 fixes.

- Start at sign-in is on by default. On Windows it is a ticked option in the installer, and the installer remembers your choice on later updates. On Mac the app switches it on once, the first time it runs. To stop KeyStow starting at sign-in, switch it off from the KeyStow tray or menu bar icon; it stays off.
- The activation key no longer waits on microphone, disk or paste work, so it should not stall or stop responding after a dictation.
- A tap shorter than 0.3 seconds is ignored instead of being transcribed, and a recording left running stops at 120 seconds.
- Your previous clipboard text is put back 0.3 seconds after the paste instead of 0.05 seconds, so slower apps paste the dictated text and not the old clipboard.
- New Windows installs go to your per-user Programs folder. Existing installs stay where they are.

Quit KeyStow before installing the update. The Windows x64 and Apple Silicon Mac installers include the base model. The Windows installer is unsigned; the Mac app is ad-hoc signed and not notarized.

Component tests passed on Windows and macOS for this build, and the packaged Windows and Mac apps passed launch, second-launch and close checks on the build machines. Physical microphone, global shortcut and paste behaviour were not tested on real hardware before release. v1.0.3 stays available if you need to go back.
