from pathlib import Path
import queue
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from compagnon.app import App


class TranscriptionTests(unittest.TestCase):
    def test_inference_requests_language_detection_and_transcription_not_translation(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App.__new__(App)
            app.config_path = Path(folder) / 'settings.json'
            app.events = queue.Queue()
            engine = Mock()
            engine.transcribe.return_value = (iter([types.SimpleNamespace(start=0, end=10, text='Hello everyone.')]), types.SimpleNamespace(language='en', duration=10))
            model = Mock(return_value=engine)
            with patch('faster_whisper.WhisperModel', model):
                app.transcribe('meeting.wav', (folder, 'Meeting', 'base'))
            engine.transcribe.assert_called_once_with('meeting.wav', language=None, task='transcribe', vad_filter=True)
            self.assertEqual(app.events.get_nowait()[0], 'status')
            self.assertEqual(app.events.get_nowait(), ('progress', (0.0, 10)))
            self.assertEqual(app.events.get_nowait(), ('progress', (10, 10)))
            kind, filename = app.events.get_nowait()
            self.assertEqual(kind, 'done')
            self.assertIn('Hello everyone.', Path(filename).read_text(encoding='utf-8'))
