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


from dataclasses import dataclass
from pathlib import PureWindowsPath


@dataclass(frozen=True)
class TeamsWindow:
    title: str
    process: str = ''

    @property
    def is_teams(self):
        return PureWindowsPath(self.process).name.casefold() in {'ms-teams.exe', 'teams.exe'} or 'teams' in self.title.casefold()

    def matches(self, custom_fragment=''):
        if not self.is_teams:
            return False
        title = self.title.casefold()
        words = [custom_fragment.strip().casefold()] if custom_fragment.strip() else ['réunion', 'meeting', 'appel', 'call']
        return any(word in title for word in words)


def teams_windows():
    """Inspect visible windows, including minimized ones, without recording audio."""
    import sys
    if sys.platform != 'win32':
        return []
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    windows = []
    errors = []

    @callback_type
    def visit(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            text = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, text, len(text))
            if not text.value:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            handle = kernel32.OpenProcess(0x1000, False, pid.value)
            process = ''
            if handle:
                try:
                    size = wintypes.DWORD(32768)
                    buffer = ctypes.create_unicode_buffer(size.value)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                        process = buffer.value
                finally:
                    kernel32.CloseHandle(handle)
            window = TeamsWindow(text.value, process)
            if window.is_teams:
                windows.append(window)
        except Exception as error:
            errors.append(error)
            return False
        return True

    result = user32.EnumWindows(visit, 0)
    if errors:
        raise errors[0]
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return windows


def teams_meeting_visible(custom_fragment=''):
    return any(window.matches(custom_fragment) for window in teams_windows())
