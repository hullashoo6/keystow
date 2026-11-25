jfk.wav is an 11-second public-domain recording from John F. Kennedy's 1961
inaugural address ("ask not what your country can do for you"). It is the test
sample from the faster-whisper project, converted once to 16 kHz mono 16-bit
WAV so the packaged app can read it without any audio-file library:
https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/tests/data/jfk.flac
(original SHA-256 63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715)
SHA-256 of jfk.wav: d54aac94051098672995c76c2ca7e297a018d75ea50144a032473696c76fe021

The release workflow feeds it to the packaged app (installer/verify_self_test.py)
to prove that the app as built can load its speech model and recognise speech.
It is not shipped inside the app.
