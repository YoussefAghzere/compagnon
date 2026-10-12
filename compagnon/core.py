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


def teams_meeting_visible():
    """Opt-in heuristic; Teams provides no reliable local meeting-state API."""
    import sys
    if sys.platform != 'win32':
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    titles = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]

    @callback_type
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            titles.append(buffer.value.lower())
        return True

    user32.EnumWindows(visit, 0)
    return any('teams' in title and any(word in title for word in ('réunion', 'meeting', 'appel', 'call')) for title in titles)
