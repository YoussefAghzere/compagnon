from datetime import datetime
from pathlib import Path
import re


def save_transcript(folder, title, segments, now=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[^\w -]', '_', title).strip(' .')[:80] or 'reunion'
    stamp = (now or datetime.now()).strftime('%Y-%m-%d_%H-%M-%S')
    text = '\n'.join(f'[{int(start)//60:02d}:{int(start)%60:02d}] {line.strip()}' for start, line in segments)
    # Exclusive creation preserves earlier exports, including simultaneous meetings.
    for index in range(10000):
        suffix = f'_{index}' if index else ''
        path = folder / f'{stamp}_{name}{suffix}.txt'
        try:
            with path.open('x', encoding='utf-8') as output:
                output.write(text + '\n')
            return path
        except FileExistsError:
            continue
    raise RuntimeError('Trop de fichiers portant le même nom.')
