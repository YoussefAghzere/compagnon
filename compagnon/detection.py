"""Read-only Windows UI Automation inspection of native Teams call controls."""
from dataclasses import dataclass
from pathlib import PureWindowsPath
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c)).strip()


def is_end_call_control(name, automation_id=''):
    label = normalized(name).replace('’', "'")
    label = re.sub(r'\s+', ' ', label)
    label = re.sub(r'\s*\([^)]*\)\s*$', '', label).strip()
    labels = {'quitter', 'raccrocher', "quitter l'appel", 'quitter la reunion', 'leave', 'hang up', 'leave call', 'leave meeting', 'end call'}
    identifier = re.sub(r'[^a-z0-9]', '', automation_id.casefold())
    return label in labels or identifier in {'hangupbutton', 'hangup', 'callhangup', 'leavebutton', 'hangupbtn', 'endcallbutton'}


def inspect_controls(window):
    """WebView2 toolbars can be deeper than 12 levels and expose Custom controls."""
    controls = window.descendants()  # No depth/type filter: inspect the provider's complete tree.
    samples = []
    matched = False
    for control in controls:
        info = control.element_info
        kind = info.control_type
        identifier = info.automation_id or ''
        name = control.window_text() or ''
        interactive = kind in {'Button', 'SplitButton', 'MenuItem', 'Custom', 'Hyperlink'}
        relevant = is_end_call_control(name, identifier)
        if interactive or relevant:
            enabled = control.is_enabled()
            visible = control.is_visible()
            if len(samples) < 40 or relevant:
                samples.append(f'{kind} | {name[:120]!r} | id={identifier[:100]!r} | actif={enabled} | visible={visible}')
            if relevant and interactive and enabled and visible:
                matched = True
    report = f'{len(controls)} éléments UI Automation inspectés.\n' + ('\n'.join(samples) if samples else 'Aucun contrôle interactif exposé par Teams.')
    return matched, report


@dataclass(frozen=True)
class Detection:
    active: bool | None
    title: str = ''
    detail: str = ''


class TeamsDetector:
    def __init__(self):
        self.active_handles = set()

    def scan(self):
        import sys
        if sys.platform != 'win32':
            return Detection(None, detail='Détection disponible uniquement sous Windows.')
        import psutil
        import ctypes
        from ctypes import wintypes
        is_minimized = ctypes.windll.user32.IsIconic
        is_minimized.argtypes = [wintypes.HWND]
        is_minimized.restype = wintypes.BOOL
        is_visible = ctypes.windll.user32.IsWindowVisible
        is_visible.argtypes = [wintypes.HWND]
        is_visible.restype = wintypes.BOOL
        from pywinauto import Desktop
        handles = set()
        errors = []
        titles = []
        reports = []
        active_title = ''
        desktop = Desktop(backend='uia')
        for window in desktop.windows():
            if not window.handle or not is_visible(window.handle):
                continue
            try:
                process = psutil.Process(window.process_id()).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if PureWindowsPath(process).name.casefold() not in {'teams.exe', 'ms-teams.exe'}:
                continue
            try:
                title = window.window_text()
                titles.append(title)
                handle = window.handle
                # Do not interpret an inaccessible minimized UI as the end of a call.
                if is_minimized(handle) and handle in self.active_handles:
                    handles.add(handle)
                    active_title = active_title or title
                    continue
                matched, report = inspect_controls(window)
                reports.append(f'Fenêtre : {title}\n{report}')
                if matched:
                    handles.add(handle)
                    active_title = active_title or title
            except Exception as error:
                errors.append(f'{type(error).__name__}: {error}')
        diagnostic = '\n\n'.join(reports)
        if errors:
            # Unknown is distinct from "no call": never stop a recording on scan failures.
            return Detection(None, detail='Inspection Teams incomplète : ' + '; '.join(errors) + '\n\n' + diagnostic)
        self.active_handles = handles
        if handles:
            return Detection(True, active_title, 'Bouton de fin d’appel détecté (ou fenêtre d’appel réduite déjà détectée).\n\n' + diagnostic)
        return Detection(False, detail='Aucun bouton de fin d’appel détecté. Fenêtres Teams : ' + (' ; '.join(titles) or 'aucune') + '\n\n' + diagnostic)


class CallLifecycle:
    """Debounce absence and prevent re-recording a manually stopped ongoing call."""
    def __init__(self, grace=20):
        self.grace = grace
        self.handled = False
        self.absent_since = None

    def observe(self, active, now, busy, auto_recording):
        if active is None:
            self.absent_since = None
            return None
        if active:
            self.absent_since = None
            if not busy and not self.handled:
                self.handled = True
                return 'start'
        else:
            if self.absent_since is None:
                self.absent_since = now
            if now - self.absent_since >= self.grace:
                self.handled = False
                if auto_recording:
                    return 'stop'
        return None
