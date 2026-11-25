# PyInstaller hook for pynput (GNU LGPL v3).
#
# The LGPL lets people replace the library in a program that uses it. Inside
# PyInstaller's compressed archive that would be impractical, so pynput is
# shipped as plain Python source files in the app's pynput folder, where a
# modified version can simply be dropped in.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pynput")
module_collection_mode = "py"
