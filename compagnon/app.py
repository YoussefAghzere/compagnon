import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .audio import Recorder
from .core import save_transcript, teams_meeting_visible, teams_windows


class App:
    def __init__(self, root):
        self.root = root
        root.title('Compagnon — transcription locale')
        root.geometry('700x600')
        self.config_path = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'Compagnon' / 'settings.json'
        try:
            config = json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            config = {}
        self.folder = tk.StringVar(value=config.get('folder', str(Path.home() / 'Documents' / 'Compagnon')))
        self.title = tk.StringVar(value='Réunion Teams')
        self.model = tk.StringVar(value=config.get('model', 'base'))
        self.mic = tk.BooleanVar(value=True)
        self.auto = tk.BooleanVar(value=False)
        self.fragment = tk.StringVar(value=config.get('teams_fragment', ''))
        self.detection_status = tk.StringVar(value='Détection automatique désactivée.')
        self.pending_auto = False
        self.status = tk.StringVar(value='Prêt — démarrez une réunion ou importez un enregistrement.')
        self.events = queue.Queue()
        self.busy = False
        self.recorder = None
        self.started_automatically = False
        self.absent_since = None
        self.last_detected = False
        box = ttk.Frame(root, padding=20)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Compagnon', font=('', 20)).pack(anchor='w')
        ttk.Label(box, text='Audio et transcription traités localement sur votre PC.').pack(anchor='w', pady=8)
        ttk.Label(box, text='Titre de la réunion').pack(anchor='w')
        ttk.Entry(box, textvariable=self.title).pack(fill='x')
        ttk.Label(box, text='Dossier des transcripts').pack(anchor='w', pady=(10, 0))
        row = ttk.Frame(box)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Choisir', command=self.choose_folder).pack(side='right')
        row = ttk.Frame(box)
        row.pack(fill='x', pady=12)
        ttk.Label(row, text='Modèle Whisper').pack(side='left')
        ttk.Combobox(row, textvariable=self.model, values=['tiny', 'base', 'small', 'medium'], state='readonly', width=10).pack(side='left', padx=10)
        ttk.Checkbutton(box, text='Inclure mon microphone avec le son du PC', variable=self.mic).pack(anchor='w')
        ttk.Checkbutton(box, text='Détection Teams expérimentale (titres des fenêtres)', variable=self.auto, command=self.toggle_auto).pack(anchor='w')
        ttk.Label(box, text='Fragment du titre de l’appel (facultatif ; sinon réunion/meeting/appel/call)').pack(anchor='w', pady=(8, 0))
        row = ttk.Frame(box)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.fragment).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Diagnostic Teams', command=self.diagnose_teams).pack(side='right')
        ttk.Label(box, textvariable=self.detection_status, wraplength=650).pack(anchor='w', pady=4)
        ttk.Label(box, text='Informez les participants et respectez les règles de votre entreprise.', wraplength=600).pack(anchor='w', pady=10)
        row = ttk.Frame(box)
        row.pack(fill='x', pady=10)
        self.start_button = ttk.Button(row, text='Démarrer', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(row, text='Arrêter et transcrire', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.import_button = ttk.Button(row, text='Importer un audio', command=self.import_audio)
        self.import_button.pack(side='left')
        ttk.Label(box, textvariable=self.status, wraplength=600).pack(anchor='w', pady=10)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(200, self.poll)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder.set(folder)

    def save_settings(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({'folder': self.folder.get(), 'model': self.model.get(), 'teams_fragment': self.fragment.get()}), encoding='utf-8')

    def toggle_auto(self):
        if self.auto.get():
            accepted = messagebox.askokcancel('Détection expérimentale', 'Une fenêtre Teams correspondant aux mots réunion/appel ou au fragment choisi peut déclencher la capture de tout le son du PC. Cette détection peut se tromper. Activez-la uniquement après avoir informé les participants.')
            self.auto.set(accepted)
        self.last_detected = False
        self.pending_auto = False
        self.detection_status.set('En attente d’une fenêtre d’appel correspondante.' if self.auto.get() else 'Détection automatique désactivée.')

    def diagnose_teams(self):
        try:
            windows = teams_windows()
            lines = [f"{'CORRESPOND' if window.matches(self.fragment.get()) else 'IGNORÉ'} : {window.title} ({Path(window.process).name or 'titre seulement'})" for window in windows]
            text = '\n'.join(lines) if lines else 'Aucune fenêtre Teams détectée.'
            messagebox.showinfo('Diagnostic Teams', text + '\n\nSi le titre de l’appel est ignoré, renseignez un fragment distinctif de ce titre. Évitez « Teams » seul : cela peut capturer hors réunion. Le transcript est créé après l’arrêt de la capture.')
        except Exception as error:
            messagebox.showerror('Diagnostic Teams', str(error))

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
            handle, path = tempfile.mkstemp(suffix='.wav', prefix='compagnon-')
            os.close(handle)
        except Exception as error:
            messagebox.showerror('Compagnon', str(error))
            return
        self.recorder = Recorder(Path(path), self.mic.get())
        self.started_automatically = automatic
        self.absent_since = None
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
            self.recorder.stop()
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
        segments, _ = engine.transcribe(str(path), language='fr', vad_filter=True)
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
                    self.status.set('● Capture en cours — son du PC et micro selon votre choix.')
                    self.stop_button.configure(state='normal')
                elif kind == 'status':
                    self.recorder = None
                    self.stop_button.configure(state='disabled')
                    self.status.set(value)
                else:
                    self.recorder = None
                    self.stop_button.configure(state='disabled')
                    self.set_busy(False)
                    self.status.set(f'Transcript sauvegardé : {value}' if kind == 'done' else f'Erreur : {value}')
                    if kind == 'error':
                        self.auto.set(False)
                        self.detection_status.set('Détection désactivée après une erreur. Consultez le message ci-dessous.')
                        messagebox.showerror('Compagnon', value)
        except queue.Empty:
            pass
        if self.auto.get():
            try:
                detected = teams_meeting_visible(self.fragment.get())
            except Exception as error:
                self.auto.set(False)
                self.detection_status.set(f'Détection interrompue : {error}. Utilisez le mode manuel.')
                detected = False
            if self.auto.get():
                self.detection_status.set('Fenêtre correspondante détectée — transcription après arrêt.' if detected else 'Aucun appel correspondant détecté — utilisez Diagnostic Teams.')
            if detected and not self.last_detected:
                self.pending_auto = True
            if not detected:
                self.pending_auto = False
            if detected and self.pending_auto and not self.busy:
                self.pending_auto = False
                self.start(automatic=True)
            if self.recorder and self.started_automatically:
                if detected:
                    self.absent_since = None
                else:
                    self.absent_since = self.absent_since or time.monotonic()
                    if time.monotonic() - self.absent_since > 20:
                        self.stop()
            self.last_detected = detected
        self.root.after(500, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Traitement en cours', 'Arrêtez la capture et attendez la fin de la transcription avant de fermer.')
            return
        try:
            self.save_settings()
        except OSError as error:
            messagebox.showerror('Configuration', str(error))
            return
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
