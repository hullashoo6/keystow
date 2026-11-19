"""Local next-build candidate, not applied to release workflow.
Mirror the installed PyInstaller QtGui hook's supported dependency collector,
then discard only VirtualKeyboard's input plugin BEFORE dependency scanning.
"""
from pathlib import Path
import importlib.util
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

_filter_path = Path(__file__).with_name("virtual_keyboard_filter.py")
_spec = importlib.util.spec_from_file_location("keystow_vk_filter", _filter_path)
_filter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_filter)
hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = _filter.filter_plugin_pairs(binaries)
