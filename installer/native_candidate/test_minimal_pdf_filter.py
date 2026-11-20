import unittest
from virtual_keyboard_filter import filter_unused_plugin_pairs

class MinimalPdfFilterTests(unittest.TestCase):
    def test_pdf_image_entrypoints_removed_on_each_target(self):
        for source in ('C:/venv/PySide6/plugins/imageformats/qpdf.dll', '/v/PySide6/Qt/plugins/imageformats/libqpdf.dylib', '/v/plugins/imageformats/libqpdf.so'):
            self.assertEqual(filter_unused_plugin_pairs([(source, 'PySide6/plugins/imageformats')]), [])

    def test_unrelated_pdf_named_file_not_removed(self):
        pairs = [('/data/qpdf.dll', 'data'), ('/plugins/imageformats/myqpdf.dll', 'plugins/imageformats')]
        self.assertEqual(filter_unused_plugin_pairs(pairs), pairs)

    def test_png_platform_tls_and_core_preserved(self):
        pairs = [(name, dest) for name, dest in [('/plugins/imageformats/qjpeg.dll', 'plugins/imageformats'), ('/plugins/platforms/qwindows.dll', 'plugins/platforms'), ('/plugins/tls/qopensslbackend.dll', 'plugins/tls'), ('/Qt6Core.dll', 'PySide6')]]
        self.assertEqual(filter_unused_plugin_pairs(pairs), pairs)

    def test_existing_virtual_keyboard_filter_preserved(self):
        self.assertEqual(filter_unused_plugin_pairs([('/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll', 'plugins/platforminputcontexts')]), [])
