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


def is_unused_pdf_image_plugin(source, destination):
    # KeyStow loads its PNG tray/icon assets, never PDF documents. This plugin
    # otherwise pulls QtPdf/PDFium into an app using QtCore/Gui/Widgets only.
    src = PurePosixPath(str(source).replace(chr(92), "/"))
    dst = PurePosixPath(str(destination).replace(chr(92), "/"))
    return src.name.lower() in {"qpdf.dll", "libqpdf.dylib", "libqpdf.so"} and (
        src.parent.name.lower() == "imageformats" or dst.name.lower() == "imageformats"
    )


def filter_unused_plugin_pairs(pairs):
    return [(src, dst) for src, dst in pairs
            if not is_virtual_keyboard_plugin(src, dst)
            and not is_unused_pdf_image_plugin(src, dst)]
