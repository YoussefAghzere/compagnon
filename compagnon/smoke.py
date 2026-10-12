"""Packaged runtime check: no recording, model download, or registry changes."""
import io
import json
from pathlib import Path
import sys
import tempfile
import wave


def check_runtime(report_path):
    report = {'version': '0.2', 'platform': sys.platform, 'ok': False}
    try:
        import av
        import ctranslate2
        import numpy as np
        from faster_whisper.audio import decode_audio
        from PIL import Image
        from .tray import Tray
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'sample.wav'
            with wave.open(str(audio), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(np.zeros(16000, dtype='<i2').tobytes())
            decoded = decode_audio(str(audio))
            if len(decoded) != 16000:
                raise RuntimeError('Audio decoder produced an unexpected length.')
        Tray.image('idle').save(io.BytesIO(), format='PNG')
        if sys.platform == 'win32':
            import soundcard
            import pystray
            from pywinauto import Desktop
            Desktop(backend='uia')
        report.update(ok=True, av=av.__version__, ctranslate2=ctranslate2.__version__)
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1
