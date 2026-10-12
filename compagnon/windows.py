"""Per-user Windows startup registration and single-instance activation."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'Compagnon'


def startup_command(executable, script=None):
    arguments = [str(executable)]
    if script is not None:
        arguments.append(str(script))
    arguments.append('--background')
    return subprocess.list2cmdline(arguments)


def configure_startup(enabled, app_directory, *, frozen=None, executable=None, script=None):
    if sys.platform != 'win32':
        if enabled:
            raise RuntimeError('Le démarrage automatique est disponible sous Windows uniquement.')
        return
    import winreg
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    executable = Path(executable or sys.executable)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if not enabled:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass
            return
        if frozen:
            destination = Path(app_directory) / 'App' / 'Compagnon.exe'
            destination.parent.mkdir(parents=True, exist_ok=True)
            if executable.resolve() != destination.resolve():
                internal = executable.parent / '_internal'
                if internal.is_dir():
                    # The optional --onedir variant also needs its native runtime.
                    shutil.copytree(internal, destination.parent / '_internal', dirs_exist_ok=True)
                # Never register the one-file extraction directory (_MEIPASS).
                temporary = destination.with_suffix('.new')
                try:
                    shutil.copy2(executable, temporary)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            command = startup_command(destination)
        else:
            pythonw = executable.with_name('pythonw.exe')
            if pythonw.exists():
                executable = pythonw
            command = startup_command(executable, Path(script or Path(__file__).resolve().parents[1] / 'main.py').resolve())
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)


class SingleInstance:
    """Second manual launches ask the existing process to show its settings."""
    def __init__(self, background=False):
        self.primary = True
        self.mutex = None
        self.event = None
        if sys.platform != 'win32':
            return
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateMutexW.restype = wintypes.HANDLE
        api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateEventW.restype = wintypes.HANDLE
        api.SetEvent.argtypes = [wintypes.HANDLE]
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api = api
        self.mutex = api.CreateMutexW(None, False, 'Local\\CompagnonInstance')
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.primary = ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        self.event = api.CreateEventW(None, False, False, 'Local\\CompagnonShowSettings')
        if not self.event:
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.primary and not background:
            api.SetEvent(self.event)

    def wants_settings(self):
        return bool(self.event and self.api.WaitForSingleObject(self.event, 0) == 0)

    def close(self):
        for name in ('event', 'mutex'):
            handle = getattr(self, name, None)
            if handle:
                self.api.CloseHandle(handle)
                setattr(self, name, None)
