from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from compagnon.windows import configure_startup, startup_command, SingleInstance


class StartupTests(unittest.TestCase):
    def registry(self):
        registry = Mock()
        registry.HKEY_CURRENT_USER = 1
        registry.REG_SZ = 1
        registry.CreateKey.return_value.__enter__ = Mock(return_value='key')
        registry.CreateKey.return_value.__exit__ = Mock(return_value=False)
        return registry

    def test_quote_command_with_spaces(self):
        self.assertEqual(startup_command(r'C:\Users\Test User\Compagnon.exe'), '"C:\\Users\\Test User\\Compagnon.exe" --background')

    def test_frozen_exe_is_copied_to_stable_location(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'download' / 'Compagnon.exe'
            source.parent.mkdir()
            source.write_bytes(b'test executable')
            registry = self.registry()
            with patch('sys.platform', 'win32'), patch.dict('sys.modules', {'winreg': registry}):
                configure_startup(True, base / 'profile', frozen=True, executable=source)
            destination = base / 'profile' / 'App' / 'Compagnon.exe'
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertFalse(destination.with_suffix('.new').exists())
            registry.SetValueEx.assert_called_once_with('key', 'Compagnon', 0, 1, startup_command(destination))

    def test_script_startup_uses_pythonw_and_absolute_script(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            executable = base / 'python.exe'
            executable.with_name('pythonw.exe').touch()
            script = base / 'main.py'
            registry = self.registry()
            with patch('sys.platform', 'win32'), patch.dict('sys.modules', {'winreg': registry}):
                configure_startup(True, base, frozen=False, executable=executable, script=script)
            registry.SetValueEx.assert_called_once_with('key', 'Compagnon', 0, 1, startup_command(executable.with_name('pythonw.exe'), script))

    def test_disable_removes_only_startup_entry(self):
        registry = self.registry()
        registry.DeleteValue.side_effect = FileNotFoundError
        with patch('sys.platform', 'win32'), patch.dict('sys.modules', {'winreg': registry}):
            configure_startup(False, '/unused')
        registry.DeleteValue.assert_called_once_with('key', 'Compagnon')
        registry.SetValueEx.assert_not_called()


class SingleInstanceTests(unittest.TestCase):
    def api(self):
        api = Mock()
        api.CreateMutexW.return_value = 100
        api.CreateEventW.return_value = 200
        api.WaitForSingleObject.return_value = 0
        return api

    def test_second_manual_launch_signals_existing_settings_window(self):
        api = self.api()
        with patch('sys.platform', 'win32'), patch('ctypes.WinDLL', return_value=api, create=True), patch('ctypes.get_last_error', return_value=183, create=True):
            instance = SingleInstance(background=False)
        self.assertFalse(instance.primary)
        api.SetEvent.assert_called_once_with(200)
        instance.close()
        self.assertEqual(api.CloseHandle.call_count, 2)

    def test_duplicate_windows_startup_does_not_open_settings(self):
        api = self.api()
        with patch('sys.platform', 'win32'), patch('ctypes.WinDLL', return_value=api, create=True), patch('ctypes.get_last_error', return_value=183, create=True):
            instance = SingleInstance(background=True)
        api.SetEvent.assert_not_called()
        instance.close()

    def test_primary_instance_consumes_activation_event(self):
        api = self.api()
        with patch('sys.platform', 'win32'), patch('ctypes.WinDLL', return_value=api, create=True), patch('ctypes.get_last_error', return_value=0, create=True):
            instance = SingleInstance()
        self.assertTrue(instance.primary)
        self.assertTrue(instance.wants_settings())
        api.WaitForSingleObject.assert_called_once_with(200, 0)
        instance.close()
