from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from compagnon.core import save_transcript


class ExportTests(unittest.TestCase):
    def test_export_safe_name_timestamps_and_collision(self):
        with tempfile.TemporaryDirectory() as folder:
            args = (folder, '../Réunion: équipe?', [(0.0, ' Bonjour '), (65.5, 'Décision validée.')], datetime(2026, 10, 12, 10, 30))
            first = save_transcript(*args)
            second = save_transcript(*args)
            self.assertEqual(first.parent, Path(folder))
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(encoding='utf-8'), '[00:00] Bonjour\n[01:05] Décision validée.\n')
            self.assertEqual(second.read_text(encoding='utf-8'), first.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
