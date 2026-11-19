"""Candidate-only filter for the exact unused QtVirtualKeyboard input plugin.
No broad removal of platforminputcontexts or unrelated Qt files.
"""
from pathlib import PurePosixPath

PLUGIN_NAMES = frozenset({
    "qtvirtualkeyboardplugin.dll",
    "libqtvirtualkeyboardplugin.dylib",
    "libqtvirtualkeyboardplugin.so",
})

def is_virtual_keyboard_plugin(source, destination):
    src = PurePosixPath(str(source).replace("\\", "/"))
    dst = PurePosixPath(str(destination).replace("\\", "/"))
    return src.name.lower() in PLUGIN_NAMES and (
        src.parent.name.lower() == "platforminputcontexts"
        or dst.name.lower() == "platforminputcontexts"
    )

def filter_plugin_pairs(pairs):
    return [(src, dst) for src, dst in pairs
            if not is_virtual_keyboard_plugin(src, dst)]
