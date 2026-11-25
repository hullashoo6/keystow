"""Stand-in for PyAV inside KeyStow's installers.

faster-whisper imports PyAV ("av") so that it can decode audio *files*.
KeyStow never gives it a file: it passes raw microphone samples, and
faster-whisper only decodes when it is given something other than a sample
array. Shipping the real PyAV would add about 77 MB of FFmpeg libraries,
including the GPL-licensed x264 and x265 video encoders, for code that never
runs. The release build removes PyAV and puts this module in its place.

It must behave like an ordinary module that lacks attributes: tools such as
PySide6's import hook and inspect probe modules for names like __wrapped__
and expect AttributeError. So every missing name raises AVUnavailable, which
*is* an AttributeError, with a message that explains why.
"""


class AVUnavailable(AttributeError):
    """KeyStow's installers do not include PyAV."""


_MESSAGE = ("KeyStow does not decode audio files; it transcribes microphone samples only "
            "(PyAV is not included in the installed app).")


def open(*_args, **_kwargs):  # noqa: A001 - mirrors av.open
    raise AVUnavailable(_MESSAGE)


def __getattr__(name):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)  # ordinary probing (__wrapped__, __path__, ...)
    raise AVUnavailable(f"{_MESSAGE} (av.{name})")
