import threading
import wave
from concurrent.futures import ThreadPoolExecutor


class Recorder:
    def __init__(self, path, include_mic=True):
        self.path = path
        self.include_mic = include_mic
        self.stop_event = threading.Event()
        self.rate = 16000

    def stop(self):
        self.stop_event.set()

    def record(self, ready):
        import numpy as np
        import soundcard as sc
        from contextlib import ExitStack
        speaker = sc.default_speaker()
        if speaker is None:
            raise RuntimeError('Aucune sortie audio Windows détectée.')
        loopback = sc.get_microphone(id=speaker.id, include_loopback=True)
        devices = [loopback]
        if self.include_mic:
            mic = sc.default_microphone()
            if mic is None:
                raise RuntimeError('Aucun microphone détecté. Désactivez la capture du micro ou branchez-le.')
            devices.append(mic)
        with ExitStack() as stack, wave.open(str(self.path), 'wb') as output, ThreadPoolExecutor(max_workers=len(devices)) as pool:
            streams = [stack.enter_context(device.recorder(samplerate=self.rate)) for device in devices]
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.rate)
            ready()
            while not self.stop_event.is_set():
                futures = [pool.submit(stream.record, numframes=1600) for stream in streams]
                chunks = [future.result().mean(axis=1) for future in futures]
                mixed = np.mean(chunks, axis=0)
                output.writeframes((np.clip(mixed, -1, 1) * 32767).astype('<i2').tobytes())
