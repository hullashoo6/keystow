import unittest
from virtual_keyboard_filter import filter_plugin_pairs

class FilterTests(unittest.TestCase):
 def test_exact_windows_plugin_removed(self):
  self.assertEqual(filter_plugin_pairs([(r'C:\venv\PySide6\plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll','PySide6/plugins/platforminputcontexts')]),[])
 def test_exact_mac_plugin_removed(self):
  self.assertEqual(filter_plugin_pairs([('/v/PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib','PySide6/Qt/plugins/platforminputcontexts')]),[])
 def test_other_input_plugins_retained(self):
  p=[('/v/platforminputcontexts/libcomposeplatforminputcontextplugin.so','PySide6/plugins/platforminputcontexts'),('/v/platforminputcontexts/libibusplatforminputcontextplugin.so','PySide6/plugins/platforminputcontexts')];self.assertEqual(filter_plugin_pairs(p),p)
 def test_qt_core_gui_widgets_platforms_retained(self):
  p=[('/v/Qt6Core.dll','PySide6'),('/v/Qt6Gui.dll','PySide6'),('/v/Qt6Widgets.dll','PySide6'),('/v/platforms/qwindows.dll','PySide6/plugins/platforms')];self.assertEqual(filter_plugin_pairs(p),p)
 def test_lookalike_not_removed(self):
  p=[('/v/platforminputcontexts/myqtvirtualkeyboardplugin.dll','PySide6/plugins/platforminputcontexts'),('/v/other/qtvirtualkeyboardplugin.dll','other')];self.assertEqual(filter_plugin_pairs(p),p)
 def test_empty(self):self.assertEqual(filter_plugin_pairs([]),[])
if __name__=='__main__':unittest.main()
