import queue
import unittest
from unittest.mock import Mock, patch
import types
from compagnon.tray import Tray


class TrayTests(unittest.TestCase):
    def test_callbacks_only_enqueue_commands_and_colors_follow_state(self):
        events = queue.Queue()
        icon = Mock()
        pystray = types.SimpleNamespace(Icon=Mock(return_value=icon), Menu=lambda *items: items, MenuItem=lambda *args, **kwargs: (args, kwargs))
        with patch.dict('sys.modules', {'pystray': pystray}):
            tray = Tray(events)
            tray.command('stop')(None, None)
            self.assertEqual(events.get_nowait(), ('command', 'stop'))
            tray.update(True, True, True)
            self.assertEqual(icon.title, 'Compagnon — capture en cours')
            self.assertEqual(icon.icon.getpixel((10, 32)), (220, 38, 38, 255))
            tray.update(True, True, False)
            self.assertEqual(icon.title, 'Compagnon — transcription en cours')
            tray.update(True, False, False)
            self.assertEqual(icon.title, 'Compagnon — prêt')
