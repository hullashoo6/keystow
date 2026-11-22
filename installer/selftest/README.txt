jfk.flac is an 11-second public-domain recording from John F. Kennedy's 1961
inaugural address ("ask not what your country can do for you"). It is the test
sample from the faster-whisper project:
https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/tests/data/jfk.flac
SHA-256: 63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715

The release workflow feeds it to the packaged app (installer/verify_self_test.py)
to prove that the app as built can load its speech model and recognise speech.
It is not shipped inside the app.
