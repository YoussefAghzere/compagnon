"""Exercise the actual faster-whisper/PyAV boundary without model downloads."""
from pathlib import Path
import tempfile
import unittest
import wave
import numpy as np
from faster_whisper.audio import decode_audio


class DecodeTests(unittest.TestCase):
    def test_decode_and_resample_wav_for_whisper(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audio.wav'
            source = (np.sin(2 * np.pi * 440 * np.arange(48000) / 48000) * 10000).astype('<i2')
            with wave.open(str(path), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(48000)
                output.writeframes(source.tobytes())
            decoded = decode_audio(str(path))
            self.assertEqual(decoded.dtype, np.float32)
            self.assertEqual(len(decoded), 16000)
            self.assertGreater(float(np.max(np.abs(decoded))), 0.2)
            self.assertTrue(np.all(np.isfinite(decoded)))
