import json
import argparse
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .audio import Recorder
from .core import save_transcript
from .detection import TeamsDetector, Detection, CallLifecycle
from .windows import configure_startup, SingleInstance


class App:
    def __init__(self, root, launch_background=False):
        self.root = root
        root.title('Compagnon 0.2')
        width = min(980, max(480, root.winfo_screenwidth() - 120))
        height = min(820, max(420, root.winfo_screenheight() - 100))
        root.geometry(f'{width}x{height}')
        root.minsize(min(640, width), min(500, height))
        root.configure(background='#f3f5fa')
        from PIL import ImageTk
        from .tray import Tray
        self.window_icon = ImageTk.PhotoImage(Tray.image('idle'), master=root)
        root.iconphoto(True, self.window_icon)
        self.config_path = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'Compagnon' / 'settings.json'
        try:
            config = json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
        if not isinstance(config, dict):
            config = {}
        self.setup_complete = bool(config.get('setup_complete', False))
        self.launch_background = launch_background and self.setup_complete
        self.registered_autostart = bool(config.get('autostart', False))
        self.autostart = tk.BooleanVar(value=bool(config.get('autostart', sys.platform == 'win32')))
        self.folder = tk.StringVar(value=config.get('folder', str(Path.home() / 'Documents' / 'Compagnon')))
        self.title = tk.StringVar(value='Réunion Teams')
        self.model = tk.StringVar(value=config.get('model', 'base'))
        self.mic = tk.BooleanVar(value=bool(config.get('microphone', True)))
        self.auto = tk.BooleanVar(value=bool(config.get('automatic', False)) and self.setup_complete)
        self.background = tk.BooleanVar(value=bool(config.get('background', False)))
        self.detection_status = tk.StringVar(value='Détection automatique désactivée.')
        self.lifecycle = CallLifecycle()
        self.status = tk.StringVar(value='Prêt — démarrez une réunion ou importez un enregistrement.')
        self.events = queue.Queue()
        self.busy = False
        self.recorder = None
        self.started_automatically = False
        self.detection = Detection(None, detail='Inspection Teams en attente…')
        self.detection_time = 0.0
        self.worker_stop = threading.Event()
        self.tray = None
        self.tray_ready = False
        self.recording = False
        self.build_ui()
        root.protocol('WM_DELETE_WINDOW', self.hide)
        if sys.platform == 'win32':
            try:
                from .tray import Tray
                self.tray = Tray(self.events)
                self.tray.start()
            except Exception as error:
                self.status.set(f'Icône indisponible : {error}. La fenêtre reste ouverte.')
        threading.Thread(target=self.detection_worker, daemon=True).start()
        root.after(200, self.poll)
        if self.launch_background and self.background.get():
            root.withdraw()
            root.after(5000, self.restore_if_tray_unavailable)

    def build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        from tkinter import font
        from .ui import ScrollablePanel
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont'):
            font.nametofont(name).configure(family='Segoe UI', size=12)
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 12))
        style.configure('.', font=('Segoe UI', 12))
        style.configure('TFrame', background='#f3f5fa')
        style.configure('Card.TFrame', background='white')
        style.configure('TLabel', background='#f3f5fa', foreground='#253047')
        style.configure('Card.TLabel', background='white', foreground='#253047')
        style.configure('Hint.TLabel', background='white', foreground='#526077', font=('Segoe UI', 11))
        style.configure('TEntry', padding=(10, 9))
        style.configure('TCombobox', padding=(10, 8))
        style.configure('Heading.TLabel', font=('Segoe UI', 28, 'bold'), foreground='#16233b')
        style.configure('Section.TLabel', background='white', font=('Segoe UI', 15, 'bold'))
        style.configure('TButton', padding=(14, 10))
        style.configure('Primary.TButton', background='#2563eb', foreground='white', padding=(20, 12))
        style.map('Primary.TButton', background=[('active', '#1d4ed8'), ('disabled', '#9ca3af')])
        style.configure('TCheckbutton', background='white', padding=(0, 7))
        style.configure('TNotebook', background='#f3f5fa', borderwidth=0)
        style.configure('TNotebook.Tab', padding=(20, 12))
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x', pady=(0, 16))
        ttk.Label(header, text='Compagnon', style='Heading.TLabel').pack(side='left')
        ttk.Label(header, text='0.2  •  PRIVÉ & LOCAL', foreground='#64748b').pack(side='right')
        ttk.Label(outer, text='Vos réunions deviennent des notes. Votre audio reste sur votre PC.').pack(anchor='w', pady=(0, 16))
        notebook = ttk.Notebook(outer)
        notebook.pack(fill='both', expand=True)
        home_panel = ScrollablePanel(notebook)
        settings_panel = ScrollablePanel(notebook)
        home, settings = home_panel.content, settings_panel.content
        notebook.add(home_panel, text='Tableau de bord')
        notebook.add(settings_panel, text='Configuration')
        if not self.setup_complete:
            notebook.select(settings_panel)
        ttk.Label(home, text='Activité', style='Section.TLabel').pack(anchor='w')
        ttk.Label(home, textvariable=self.status, style='Card.TLabel', wraplength=710).pack(anchor='w', pady=14)
        ttk.Label(home, textvariable=self.detection_status, style='Card.TLabel', wraplength=710).pack(anchor='w', pady=(0, 16))
        ttk.Label(home, text='Capture manuelle', style='Section.TLabel').pack(anchor='w', pady=(10, 8))
        ttk.Label(home, text='Titre du fichier (en automatique, le titre Teams est utilisé)', style='Card.TLabel').pack(anchor='w')
        ttk.Entry(home, textvariable=self.title).pack(fill='x', pady=8)
        row = ttk.Frame(home, style='Card.TFrame')
        row.pack(fill='x', pady=8)
        self.start_button = ttk.Button(row, text='Démarrer', command=self.start, style='Primary.TButton')
        self.start_button.pack(fill='x', pady=4)
        self.stop_button = ttk.Button(row, text='Arrêter et transcrire', command=self.stop, state='disabled')
        self.stop_button.pack(fill='x', pady=4)
        self.import_button = ttk.Button(row, text='Importer un audio', command=self.import_audio)
        self.import_button.pack(fill='x', pady=4)
        ttk.Button(home, text='Ouvrir mes transcripts', command=self.open_folder).pack(anchor='w', pady=10)
        ttk.Button(home, text='Diagnostic Teams', command=self.diagnose_teams).pack(anchor='w')
        ttk.Label(settings, text='Configurez une fois. Retrouvez vos réunions en texte.', style='Section.TLabel').pack(anchor='w', pady=(0, 16))
        ttk.Label(settings, text='1. Où enregistrer vos transcripts ?', style='Card.TLabel').pack(anchor='w')
        row = ttk.Frame(settings, style='Card.TFrame')
        row.pack(fill='x', pady=(6, 14))
        ttk.Entry(row, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Parcourir…', command=self.choose_folder).pack(side='right', padx=(8, 0))
        ttk.Label(settings, text='2. Choisissez la qualité de transcription', style='Card.TLabel').pack(anchor='w')
        ttk.Combobox(settings, textvariable=self.model, values=['tiny', 'base', 'small', 'medium'], state='readonly', width=20).pack(anchor='w', pady=6)
        ttk.Label(settings, text='Tiny : rapide · Base : équilibré · Small / Medium : plus précis, mais plus lents', style='Hint.TLabel').pack(anchor='w', pady=(0, 12))
        ttk.Label(settings, text='La langue est détectée automatiquement. Le texte conserve la langue parlée.', style='Hint.TLabel').pack(anchor='w', pady=(0, 8))
        ttk.Label(settings, text='3. Capture et démarrage', style='Section.TLabel').pack(anchor='w', pady=(12, 8))
        ttk.Checkbutton(settings, text='Inclure mon microphone avec le son du PC', variable=self.mic).pack(anchor='w')
        ttk.Checkbutton(settings, text='Capturer automatiquement les appels Teams', variable=self.auto, command=self.toggle_auto).pack(anchor='w')
        ttk.Checkbutton(settings, text='Lancer Compagnon à l’ouverture de ma session Windows', variable=self.autostart).pack(anchor='w')
        ttk.Checkbutton(settings, text='Masquer la fenêtre au démarrage automatique', variable=self.background).pack(anchor='w')
        ttk.Label(settings, text='Le premier téléchargement du modèle nécessite Internet.\nInformez les participants avant toute capture. La détection Teams reste expérimentale.', style='Hint.TLabel', wraplength=710).pack(anchor='w', pady=18)
        ttk.Button(settings, text='Enregistrer et activer', style='Primary.TButton', command=self.complete_setup).pack(anchor='w')
        footer = ttk.Frame(outer)
        footer.pack(fill='x', pady=(16, 0))
        ttk.Label(footer, text='Bleu : prêt · Rouge : capture · Orange : traitement', foreground='#64748b').pack(anchor='w', pady=(0, 10))
        actions = ttk.Frame(footer)
        actions.pack(fill='x')
        ttk.Button(actions, text='Masquer dans la zone de notification', command=self.hide).pack(side='right')
        ttk.Button(actions, text='Quitter', command=self.close).pack(side='right', padx=8)

    def restore_if_tray_unavailable(self):
        if not self.tray_ready:
            self.show()

    def complete_setup(self):
        try:
            folder = Path(self.folder.get().strip())
            if not self.folder.get().strip():
                raise ValueError('Choisissez un dossier de sauvegarde.')
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=folder):
                pass
            configure_startup(self.autostart.get(), self.config_path.parent)
            self.registered_autostart = self.autostart.get()
            previous = self.setup_complete
            self.setup_complete = True
            try:
                self.save_settings()
            except Exception:
                self.setup_complete = previous
                raise
        except Exception as error:
            self.show()
            messagebox.showerror('Configuration non enregistrée', str(error))
            return
        self.lifecycle = CallLifecycle()
        self.status.set('Configuration enregistrée. Compagnon est prêt.')
        self.notify('Configuration enregistrée. Compagnon est prêt.')
        messagebox.showinfo('Compagnon est prêt', 'Vos réglages sont enregistrés. Vous pouvez masquer cette fenêtre et la rouvrir depuis l’icône ou en relançant Compagnon. Le démarrage Windows suit votre choix.')

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder.set(folder)

    def save_settings(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'folder': self.folder.get(), 'model': self.model.get(), 'automatic': self.auto.get(), 'background': self.background.get(), 'microphone': self.mic.get(), 'setup_complete': self.setup_complete, 'autostart': self.registered_autostart}), encoding='utf-8')
        temporary.replace(self.config_path)

    def persist_settings(self):
        try:
            self.save_settings()
            return True
        except OSError as error:
            messagebox.showerror('Configuration', str(error))
            return False

    def toggle_auto(self):
        if self.auto.get():
            self.show()
            accepted = messagebox.askokcancel('Capture automatique', 'Compagnon détecte les boutons de fin d’appel Teams et capture tout le son du PC, même avec sa fenêtre masquée. Cette détection est expérimentale. Informez les participants et respectez les règles de votre entreprise. Activer et mémoriser ce choix ?')
            self.auto.set(accepted)
        self.lifecycle = CallLifecycle()
        self.detection_status.set('En attente d’un appel Teams actif.' if self.auto.get() else 'Capture automatique désactivée.')
        self.persist_settings()

    def detection_worker(self):
        # Import pywinauto in this worker so its COM apartment belongs to this thread.
        detector = TeamsDetector()
        while not self.worker_stop.is_set():
            try:
                result = detector.scan()
            except Exception as error:
                result = Detection(None, detail=f'Détection indisponible : {type(error).__name__}: {error}')
            self.events.put(('detection', result))
            self.worker_stop.wait(2)

    def diagnose_teams(self):
        self.show()
        detail = self.detection.detail
        if time.monotonic() - self.detection_time > 10:
            detail += '\nInspection en attente ou bloquée. Utilisez la capture manuelle.'
        dialog = tk.Toplevel(self.root)
        dialog.title('Diagnostic Teams — contrôles accessibles')
        dialog.geometry('850x550')
        from tkinter.scrolledtext import ScrolledText
        text = ScrolledText(dialog, wrap='word')
        text.pack(fill='both', expand=True, padx=12, pady=12)
        text.insert('1.0', detail + '\n\nSi aucun contrôle n’est exposé, l’accessibilité de Teams/WebView2 peut être indisponible. Si Quitter apparaît sans capture, copiez le diagnostic pour analyser son type, son identifiant et son état. Ne modifiez pas les paramètres Teams de votre entreprise sans son accord.')
        text.configure(state='disabled')
        def copy():
            dialog.clipboard_clear()
            dialog.clipboard_append(text.get('1.0', 'end-1c'))
        ttk.Button(dialog, text='Copier le diagnostic', command=copy).pack(pady=(0, 12))


    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        if not self.tray_ready:
            messagebox.showinfo('Compagnon', 'L’icône n’est pas disponible. La fenêtre doit rester ouverte ; elle peut être réduite.')
            return
        if not self.setup_complete:
            messagebox.showinfo('Configuration', 'Cliquez sur Enregistrer et activer avant de masquer Compagnon.')
            return
        if self.persist_settings():
            self.root.withdraw()

    def notify(self, text):
        if self.tray_ready:
            self.tray.notify(text)

    def open_folder(self):
        try:
            folder = Path(self.folder.get())
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))
        except Exception as error:
            self.show()
            messagebox.showerror('Dossier des transcripts', str(error))

    def set_busy(self, busy):
        self.busy = busy
        self.start_button.configure(state='disabled' if busy else 'normal')
        self.import_button.configure(state='disabled' if busy else 'normal')

    def options(self):
        if not self.folder.get().strip():
            raise ValueError('Choisissez un dossier de sauvegarde.')
        self.save_settings()
        return self.folder.get(), self.title.get(), self.model.get()

    def start(self, automatic=False):
        if self.busy:
            return
        try:
            options = self.options()
            if automatic and self.detection.title:
                options = (options[0], self.detection.title, options[2])
            handle, path = tempfile.mkstemp(suffix='.wav', prefix='compagnon-')
            os.close(handle)
        except Exception as error:
            self.auto.set(False)
            self.persist_settings()
            self.show()
            messagebox.showerror('Compagnon', str(error))
            return
        self.recorder = Recorder(Path(path), self.mic.get())
        if self.detection.active is True:
            self.lifecycle.handled = True
        self.started_automatically = automatic
        self.set_busy(True)
        self.status.set('Ouverture des périphériques audio…')
        recorder = self.recorder

        def work():
            try:
                recorder.record(lambda: self.events.put(('recording', None)))
                self.transcribe(path, options)
            except Exception as error:
                self.events.put(('error', str(error)))
            finally:
                Path(path).unlink(missing_ok=True)
        threading.Thread(target=work, daemon=True).start()

    def stop(self):
        if self.recorder:
            self.lifecycle.handled = True
            self.recording = False
            self.recorder.stop()
            self.recorder = None
            self.stop_button.configure(state='disabled')
            self.status.set('Fin de capture — préparation de la transcription…')

    def import_audio(self):
        path = filedialog.askopenfilename(filetypes=[('Audio', '*.wav *.mp3 *.m4a *.mp4 *.ogg *.flac'), ('Tous les fichiers', '*')])
        if not path:
            return
        try:
            options = self.options()
        except Exception as error:
            messagebox.showerror('Compagnon', str(error))
            return
        self.set_busy(True)
        def work():
            try:
                self.transcribe(path, options)
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=work, daemon=True).start()

    def transcribe(self, path, options):
        from faster_whisper import WhisperModel
        folder, title, model = options
        self.events.put(('status', 'Chargement du modèle (téléchargement au premier usage), puis transcription…'))
        cache = self.config_path.parent / 'models'
        engine = WhisperModel(model, device='cpu', compute_type='int8', download_root=str(cache))
        segments, _ = engine.transcribe(str(path), language=None, task='transcribe', vad_filter=True)
        lines = [(segment.start, segment.text) for segment in segments]
        if not lines:
            raise RuntimeError('Aucune parole détectée. Vérifiez le fichier ou les périphériques audio.')
        output = save_transcript(folder, title, lines)
        self.events.put(('done', str(output)))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'recording':
                    if self.recorder is None:
                        continue
                    self.recording = True
                    self.notify('Capture démarrée — son du PC et microphone selon votre choix.')
                    self.status.set('● Capture en cours — son du PC et micro selon votre choix.')
                    self.stop_button.configure(state='normal')
                elif kind == 'tray_ready':
                    self.tray_ready = True
                    if self.launch_background and self.background.get() and self.setup_complete:
                        self.hide()
                elif kind == 'tray_error':
                    self.tray_ready = False
                    self.show()
                    self.status.set(f'Icône indisponible : {value}')
                elif kind == 'command':
                    if value == 'toggle_auto':
                        self.auto.set(not self.auto.get())
                        self.toggle_auto()
                    else:
                        {'show': self.show, 'start': self.start, 'stop': self.stop, 'open_folder': self.open_folder, 'quit': self.close}[value]()
                    if self.worker_stop.is_set():
                        return
                elif kind == 'detection':
                    self.detection = value
                    self.detection_time = time.monotonic()
                elif kind == 'status':
                    self.recorder = None
                    self.recording = False
                    self.stop_button.configure(state='disabled')
                    self.status.set(value)
                else:
                    self.recorder = None
                    self.recording = False
                    self.stop_button.configure(state='disabled')
                    self.set_busy(False)
                    self.status.set(f'Transcript sauvegardé : {value}' if kind == 'done' else f'Erreur : {value}')
                    self.notify('Transcript sauvegardé.' if kind == 'done' else 'Erreur : ouvrez Compagnon pour consulter le détail.')
                    if kind == 'error':
                        self.auto.set(False)
                        self.detection_status.set('Détection désactivée après une erreur. Consultez le message ci-dessous.')
                        self.persist_settings()
                        self.show()
                        messagebox.showerror('Compagnon', value)
        except queue.Empty:
            pass
        if self.auto.get() and self.setup_complete:
            active = self.detection.active
            if time.monotonic() - self.detection_time > 10:
                active = None
                self.detection_status.set('Inspection Teams en attente ou bloquée ; utilisez le mode manuel.')
            else:
                self.detection_status.set(self.detection.detail.split('\n', 1)[0])
            action = self.lifecycle.observe(active, time.monotonic(), self.busy, self.recorder is not None and self.started_automatically)
            if action == 'start':
                self.start(automatic=True)
            elif action == 'stop':
                self.stop()
        else:
            self.detection_status.set('Capture automatique désactivée.')
        if self.tray_ready:
            try:
                self.tray.update(self.auto.get(), self.busy, self.recording)
            except Exception as error:
                self.tray_ready = False
                self.show()
                self.status.set(f'Icône indisponible : {error}')
        self.root.after(500, self.poll)

    def close(self):
        if self.busy:
            self.show()
            messagebox.showinfo('Traitement en cours', 'Arrêtez la capture et attendez la fin de la transcription avant de fermer.')
            return
        try:
            self.save_settings()
        except OSError as error:
            messagebox.showerror('Configuration', str(error))
            return
        self.worker_stop.set()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Compagnon — transcription locale')
    parser.add_argument('--background', action='store_true', help='Démarrage Windows dans la zone de notification après configuration')
    parser.add_argument('--smoke-test', metavar='REPORT', help='Vérifier les bibliothèques embarquées sans capturer ni télécharger')
    arguments = parser.parse_args()
    if arguments.smoke_test:
        from .smoke import check_runtime
        raise SystemExit(check_runtime(arguments.smoke_test))
    instance = SingleInstance(arguments.background)
    try:
        if not instance.primary:
            return
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                pass
        root = tk.Tk()
        app = App(root, launch_background=arguments.background)
        def activation():
            if instance.wants_settings():
                app.launch_background = False
                app.show()
            root.after(500, activation)
        root.after(500, activation)
        root.mainloop()
    finally:
        instance.close()
