import queue
import threading
import time
import unittest
from unittest.mock import Mock, patch
from compagnon.app import App
from compagnon.detection import CallLifecycle, Detection


class Value:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class AppTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.root = Mock()
        app.auto = Value(True)
        app.background = Value(False)
        app.launch_background = False
        app.setup_complete = True
        app.lifecycle = CallLifecycle()
        app.detection = Detection(None)
        app.detection_time = time.monotonic()
        app.events = queue.Queue()
        app.busy = False
        app.recorder = None
        app.recording = False
        app.started_automatically = False
        app.tray = Mock()
        app.tray_ready = True
        app.progress_bar = Mock()
        app.progress_bar.__setitem__ = Mock()
        app.progress_text = Value('')
        app.progress_mode = 'idle'
        app.job_started = None
        app.audio_processed = app.audio_duration = 0
        app.status = Value('')
        app.detection_status = Value('')
        app.start_button = Mock()
        app.stop_button = Mock()
        app.import_button = Mock()
        app.worker_stop = threading.Event()
        app.persist_settings = Mock(return_value=True)
        return app

    def test_detection_starts_while_window_is_hidden(self):
        app = self.app()
        app.start = Mock()
        app.events.put(('detection', Detection(True, 'M3S - transcript test')))
        app.poll()
        app.start.assert_called_once_with(automatic=True)
        app.root.deiconify.assert_not_called()

    def test_manual_launch_never_auto_hides_even_with_old_hidden_preference(self):
        app = self.app()
        app.background.set(True)
        app.launch_background = False
        app.hide = Mock()
        app.events.put(('tray_ready', None))
        app.poll()
        app.hide.assert_not_called()

    def test_windows_background_launch_hides_only_after_setup_and_tray_ready(self):
        app = self.app()
        app.launch_background = True
        app.background.set(True)
        app.hide = Mock()
        app.events.put(('tray_ready', None))
        app.poll()
        app.hide.assert_called_once()

    def test_unconfigured_launch_does_not_hide_or_auto_record(self):
        app = self.app()
        app.setup_complete = False
        app.launch_background = True
        app.background.set(True)
        app.hide = Mock()
        app.start = Mock()
        app.events.put(('tray_ready', None))
        app.events.put(('detection', Detection(True, 'Meeting')))
        app.poll()
        app.hide.assert_not_called()
        app.start.assert_not_called()

    def test_tray_stop_and_transcript_completion(self):
        app = self.app()
        app.busy = True
        app.recorder = Mock()
        recorder = app.recorder
        app.recording = True
        app.events.put(('command', 'stop'))
        app.poll()
        recorder.stop.assert_called_once()
        self.assertIsNone(app.recorder)
        self.assertFalse(app.recording)
        self.assertTrue(app.busy)
        app.events.put(('done', 'reunion.txt'))
        app.poll()
        self.assertFalse(app.busy)
        self.assertIn('reunion.txt', app.status.get())
        app.tray.notify.assert_called_with('Transcript sauvegardé.')

    def test_loading_and_segment_progress_only_reach_100_after_export(self):
        app = self.app()
        app.events.put(('status', 'Chargement du modèle'))
        app.poll()
        app.progress_bar.start.assert_called_once_with(15)
        self.assertIn('Temps écoulé', app.progress_text.get())
        app.events.put(('progress', (45, 90)))
        app.poll()
        app.progress_bar.__setitem__.assert_called_with('value', 50)
        self.assertIn('00:00:45 / 00:01:30', app.progress_text.get())
        app.events.put(('progress', (90, 90)))
        app.poll()
        app.progress_bar.__setitem__.assert_called_with('value', 99)
        app.events.put(('done', 'meeting.txt'))
        app.poll()
        app.progress_bar.__setitem__.assert_called_with('value', 100)
        self.assertIn('Transcript sauvegardé', app.progress_text.get())

    def test_close_cross_hides_instead_of_stopping_worker(self):
        app = self.app()
        app.hide()
        app.root.withdraw.assert_called_once()
        app.root.destroy.assert_not_called()
        self.assertFalse(app.worker_stop.is_set())

    def test_quitting_while_recording_preserves_capture(self):
        app = self.app()
        app.busy = True
        with patch('compagnon.app.messagebox.showinfo'):
            app.close()
        app.root.destroy.assert_not_called()
        app.tray.stop.assert_not_called()
        self.assertFalse(app.worker_stop.is_set())
