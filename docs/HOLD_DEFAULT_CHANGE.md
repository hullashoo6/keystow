# Hold-default source change

Source-only work, 2026-11-18. The published v1.0.0 Windows and Mac artifacts
are unchanged and use the earlier toggle default. No hold-default release or
site deployment is authorized by this document.

## Mode resolution and upgrade evidence

Old source stored a `hotkey` only when the user selected/captured one. It had
no saved activation-mode field; `KEYSTOW_TOGGLE` supplied the optional mode.
The absence of a key is therefore the available signal for an uncustomized
install. It is not possible to reconstruct a removed environment override or
a hand-edited/deleted old preference. Do not pretend otherwise.

Resolution on startup, without writing preferences:

1. Present `KEYSTOW_TOGGLE`: `0` is hold, any other value preserves historical
   toggle semantics. Use `1` for an explicit toggle choice.
2. Valid saved `activation_mode`: `hold` or `toggle`.
3. Existing valid saved key, or explicit nonempty `KEYSTOW_HOTKEY`: legacy
   toggle, even if that key is Right Ctrl.
4. Otherwise hold.

A new key selection saves the active mode before the key so a hold user's
custom key is not misclassified as legacy on restart. Existing custom keys
and modes are not overwritten merely by startup. UI and controller share
one resolver. The mode can currently be explicitly selected via environment
or settings file, not a new in-app mode control.

## Component verification

- One key-down starts, auto-repeat does not restart, matching release stops
  once. An unrelated release does not stop it.
- Failed capture start does not retry from OS repeat; release then a new
  press can retry. Stop failure recovers for the next hold.
- Key held during processing cannot start a capture when processing finishes
  merely because another auto-repeat arrives.
- Capturing a custom key consumes repeats until release.
- Repeated empty/failing sessions do not paste previous text; next valid
  session inserts only its own result. Previous successful transcript remains
  available for intentional manual recovery.
- Quit mid-hold discards audio and rejects later callbacks; a fresh controller
  starts idle. This models restart, not a real OS crash/permission test.

These are controlled event/Qt checks. OS event delivery, modifier suppression,
physical release reliability, clipboard delivery, permission recovery and
installed application acceptance remain real-machine checks. A lost OS keyup
cannot be inferred from silence without changing hold semantics. Do not add
an arbitrary speech-duration cutoff to hide that limitation.

## Prepared page wording, not deployed

Apply only when the approved hold-default installer is actually available:

Hero: "Local voice typing for everyday work. Focus a text field, hold a key
while speaking, then release to transcribe on your computer."

Step 02 title: "Focus, hold, speak"

Step 02 body: "Hold Right Ctrl while speaking, then release to stop. Keep your
destination field focused while it processes. Existing custom settings may
retain toggle mode. Review the transcript before sending."

Do not change the live page to these words while v1.0.0 toggle is the only
available installer.

## Deliberate release boundary

The current workflow builds on main source pushes and automatically clobbers
v1.0.0 assets. Source-only commits must include `[skip ci]`. GitHub documents
this skip for push-triggered workflows; it does not block manual dispatch.

A later approved build can use manual `workflow_dispatch` on an explicitly
chosen commit, but the current workflow overwrites v1.0.0. Decide version/tag,
release notes and publication through the owner before running it. Do not
trigger it as a side effect of this source-only work.

Reference: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs
