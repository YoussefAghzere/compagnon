from contextlib import contextmanager
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import wave
import numpy as np
from compagnon.audio import Recorder


class AudioTests(unittest.TestCase):
    def test_mix_microphone_and_loopback_to_mono_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.wav'
            recorder = Recorder(path)
            @contextmanager
            def stream(value):
                def record(numframes):
                    recorder.stop()
                    return np.full((numframes, 2), value)
                yield types.SimpleNamespace(record=record)
            speaker = types.SimpleNamespace(id='speaker')
            loopback = types.SimpleNamespace(recorder=lambda **_: stream(0.5))
            mic = types.SimpleNamespace(recorder=lambda **_: stream(0.25))
            soundcard = types.SimpleNamespace(default_speaker=lambda: speaker, get_microphone=lambda **_: loopback, default_microphone=lambda: mic)
            ready = []
            with patch.dict('sys.modules', {'soundcard': soundcard}):
                recorder.record(lambda: ready.append(True))
            self.assertEqual(ready, [True])
            with wave.open(str(path), 'rb') as audio:
                self.assertEqual(audio.getframerate(), 16000)
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getnframes(), 1600)
                values = np.frombuffer(audio.readframes(1600), dtype='<i2')
                self.assertTrue(np.all(values == int(0.375 * 32767)))
