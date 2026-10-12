import unittest
from unittest.mock import Mock, patch
import types
from compagnon.detection import CallLifecycle, TeamsDetector, is_end_call_control


class DetectionTests(unittest.TestCase):
    def test_french_and_english_call_controls(self):
        for name in ['Quitter', 'Raccrocher', 'Quitter la réunion', 'Leave', 'Hang up', 'Leave (Ctrl+Shift+H)']:
            with self.subTest(name=name):
                self.assertTrue(is_end_call_control(name))
        self.assertTrue(is_end_call_control('', 'hangup-button'))
        self.assertTrue(is_end_call_control('', 'hangUpButton'))
        self.assertTrue(is_end_call_control('Quitter l’appel'))

    def test_chat_and_prejoin_controls_do_not_trigger(self):
        for name in ['Join', 'Rejoindre', 'Annuler', 'Appeler', 'Chat', 'Quitter les paramètres']:
            self.assertFalse(is_end_call_control(name))

    def scan(self, detector, windows):
        desktop = Mock()
        desktop.windows.return_value = windows
        processes = types.SimpleNamespace(Process=lambda pid: types.SimpleNamespace(name=lambda: 'ms-teams.exe' if pid == 1 else 'notepad.exe'), NoSuchProcess=ProcessLookupError, AccessDenied=PermissionError)
        iconic = Mock(side_effect=lambda handle: handle == 99)
        windll = types.SimpleNamespace(user32=types.SimpleNamespace(IsIconic=iconic, IsWindowVisible=Mock(return_value=True)))
        with patch('sys.platform', 'win32'), patch('ctypes.windll', windll, create=True), patch.dict('sys.modules', {'pywinauto': types.SimpleNamespace(Desktop=lambda **_: desktop), 'psutil': processes}):
            return detector.scan()

    def window(self, button='Leave', pid=1, handle=1):
        control = Mock()
        control.is_enabled.return_value = True
        control.is_visible.return_value = True
        control.window_text.return_value = button
        control.element_info.automation_id = ''
        control.element_info.control_type = 'Button'
        window = Mock()
        window.process_id.return_value = pid
        window.window_text.return_value = 'M3S - transcript test'
        window.handle = handle
        window.descendants.return_value = [control]
        return window

    def test_real_scan_path_accepts_arbitrary_title_and_rejects_other_process(self):
        result = self.scan(TeamsDetector(), [self.window()])
        self.assertTrue(result.active)
        self.assertEqual(result.title, 'M3S - transcript test')
        self.assertFalse(self.scan(TeamsDetector(), [self.window(pid=2)]).active)
        self.assertFalse(self.scan(TeamsDetector(), [self.window(button='Join')]).active)

    def test_custom_webview_control_is_detected_without_depth_filter(self):
        window = self.window()
        control = window.descendants.return_value[0]
        control.element_info.control_type = 'Custom'
        control.window_text.return_value = ''
        control.element_info.automation_id = 'hangUpButton'
        result = self.scan(TeamsDetector(), [window])
        self.assertTrue(result.active)
        window.descendants.assert_called_once_with()
        self.assertIn('hangUpButton', result.detail)

    def test_disabled_hidden_and_prejoin_controls_are_not_active_calls(self):
        for property in ['is_enabled', 'is_visible']:
            window = self.window()
            getattr(window.descendants.return_value[0], property).return_value = False
            self.assertFalse(self.scan(TeamsDetector(), [window]).active)
        window = self.window()
        window.descendants.return_value = []
        result = self.scan(TeamsDetector(), [window])
        self.assertFalse(result.active)
        self.assertIn('0 éléments', result.detail)
        self.assertIn('Aucun contrôle interactif', result.detail)

    def test_minimized_confirmed_call_is_retained(self):
        detector = TeamsDetector()
        window = self.window(handle=99)
        # Previously verified before minimization.
        detector.active_handles = {99}
        window.descendants.side_effect = RuntimeError('minimized controls unavailable')
        self.assertTrue(self.scan(detector, [window]).active)
        self.assertFalse(self.scan(detector, []).active)

    def test_inspection_failure_is_unknown_not_call_end(self):
        window = self.window()
        window.descendants.side_effect = RuntimeError('UIA failure')
        self.assertIsNone(self.scan(TeamsDetector(), [window]).active)


class LifecycleTests(unittest.TestCase):
    def test_automatic_start_and_debounced_end(self):
        state = CallLifecycle()
        self.assertEqual(state.observe(True, 0, False, False), 'start')
        self.assertIsNone(state.observe(True, 1, True, True))
        self.assertIsNone(state.observe(False, 10, True, True))
        self.assertIsNone(state.observe(False, 29, True, True))
        self.assertEqual(state.observe(False, 30, True, True), 'stop')

    def test_manual_stop_does_not_restart_same_call(self):
        state = CallLifecycle()
        state.observe(True, 0, False, False)
        self.assertIsNone(state.observe(True, 10, False, False))
        state.observe(False, 20, False, False)
        state.observe(False, 40, False, False)
        self.assertEqual(state.observe(True, 41, False, False), 'start')

    def test_unknown_or_stale_scan_never_stops_and_resets_absence(self):
        state = CallLifecycle()
        state.observe(True, 0, False, False)
        state.observe(False, 1, True, True)
        self.assertIsNone(state.observe(None, 25, True, True))
        self.assertIsNone(state.observe(False, 26, True, True))
        self.assertEqual(state.observe(False, 46, True, True), 'stop')

    def test_call_detected_while_transcribing_starts_when_available(self):
        state = CallLifecycle()
        self.assertIsNone(state.observe(True, 0, True, False))
        self.assertEqual(state.observe(True, 2, False, False), 'start')
