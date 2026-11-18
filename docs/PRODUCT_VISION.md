# KeyStow product vision

## A small tool with a clear job

Make speaking a practical alternative to typing: focus a text field, press a shortcut, speak, stop, and receive useful text without sending audio to a transcription service.

KeyStow is a local voice-typing utility, not a claim of feature parity with Wispr Flow. Its first audience is Windows users who want straightforward everyday dictation without a subscription. macOS remains a separate validation track, not compatibility inferred from a successful build.

## Product choices

- Keep the core local and usable without an account or a paid transcription API.
- Make recording, processing, success, and failure easy to tell apart.
- Protect the user's work: one dictation at a time, predictable paste behavior, and recoverable text when insertion fails.
- Prefer a dependable base experience over more models, modes, or settings.
- Keep the owner-set $5 lifetime price and MIT source license. These do not imply a live checkout, a support guarantee, or any change to the license.
- Use existing free resources. New spending, accounts, distribution launches, and outreach are outside this build plan.

## Intended experience

1. Install and open KeyStow; the bundled base model loads locally.
2. Focus an editable field in another app.
3. Hold the configured shortcut while speaking, then release to stop (v1.0.1 uncustomized default). Explicit toggle and legacy custom-key settings may retain press-once/start, press-again/stop behavior.
4. Wait for local transcription. Do not accept another recording or switch models during processing.
5. Paste the result once. Show the transcript for recovery if insertion fails.
6. Return to a clear ready state, or explain the next recovery action.

Clipboard-based insertion targets the app focused when pasting. It is not proof of focus safety, successful insertion into every app, or support for elevated/secure fields. Those boundaries need visible guidance and real OS verification before broader claims.

## What counts as progress

Implemented code, isolated automated checks, actual hardware checks, and installed-release checks are different evidence levels. A green CI run proves only what its jobs actually exercised. Tests with substituted audio, UI, or keyboard dependencies do not prove real microphone capture, global shortcuts, transcription accuracy, or paste behavior.

The first quality milestone is a reproducible Windows install-to-dictation session with recorded environment, expected/observed text, recoverable errors, and no overlapping operations. The checklist tracks the evidence and remaining gaps. No zero-bug promise is made.

## Honest project presentation

This is an AI-assisted product-building project. Describe the problem, product decisions, implementation changes, checks actually run, defects found, and known limits. Do not imply unaided hand-coded engineering, real-user adoption, measured accuracy, or production reliability without evidence. A useful product and a clear decision/evidence record are the showcase.

## Deferred until the core is demonstrated

Cloud cleanup, custom styles, expanded vocabulary tools, automatic modes, and launch activity are not priorities. Optional larger local models are supporting choices, not a substitute for proving the default path. Downloads for non-bundled models require internet; their offline availability must not be implied before download.
