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
        app.status = Value('')
        app.detection_status = Value('')
        app.start_button = Mock()
        app.stop_button = Mock()
        app.import_button = Mock()
        app.worker_stop = threading.Event()
        app.persist_settings = Mock()
        return app

    def test_detection_starts_while_window_is_hidden(self):
        app = self.app()
        app.start = Mock()
        app.events.put(('detection', Detection(True, 'M3S - transcript test')))
        app.poll()
        app.start.assert_called_once_with(automatic=True)
        app.root.deiconify.assert_not_called()

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
