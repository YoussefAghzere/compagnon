"""Tray callbacks enqueue commands; all Tk work stays on the main thread."""
class Tray:
    def __init__(self, events):
        import pystray
        self.pystray = pystray
        self.events = events
        self.state = {'auto': False, 'busy': False, 'recording': False}
        self.icon = pystray.Icon('Compagnon', self.image('idle'), 'Compagnon — prêt', menu=pystray.Menu(
            pystray.MenuItem('Ouvrir les paramètres', self.command('show'), default=True),
            pystray.MenuItem('Capture automatique Teams', self.command('toggle_auto'), checked=lambda _: self.state['auto']),
            pystray.MenuItem('Démarrer la capture', self.command('start'), enabled=lambda _: not self.state['busy']),
            pystray.MenuItem('Arrêter et transcrire', self.command('stop'), enabled=lambda _: self.state['recording']),
            pystray.MenuItem('Ouvrir les transcripts', self.command('open_folder')),
            pystray.MenuItem('Quitter Compagnon', self.command('quit')),
        ))

    def command(self, name):
        return lambda *_: self.events.put(('command', name))

    @staticmethod
    def image(state):
        from PIL import Image, ImageDraw
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = {'idle': '#2563eb', 'recording': '#dc2626', 'busy': '#d97706'}[state]
        draw.ellipse((4, 4, 60, 60), fill=color)
        draw.rounded_rectangle((26, 14, 38, 38), radius=6, fill='white')
        draw.arc((19, 23, 45, 46), 0, 180, fill='white', width=4)
        draw.line((32, 46, 32, 53), fill='white', width=4)
        return image

    def start(self):
        import threading
        def setup(icon):
            icon.visible = True
            self.events.put(('tray_ready', None))
        def run():
            try:
                self.icon.run(setup=setup)
            except Exception as error:
                self.events.put(('tray_error', str(error)))
        threading.Thread(target=run, daemon=True).start()

    def update(self, auto, busy, recording):
        state = {'auto': auto, 'busy': busy, 'recording': recording}
        if state != self.state:
            self.state = state
            mode = 'recording' if recording else 'busy' if busy else 'idle'
            self.icon.icon = self.image(mode)
            self.icon.title = 'Compagnon — ' + {'recording': 'capture en cours', 'busy': 'transcription en cours', 'idle': 'prêt'}[mode]
            self.icon.update_menu()

    def notify(self, text):
        try:
            self.icon.notify(text, 'Compagnon')
        except Exception:
            pass  # Notification availability must not interrupt capture or export.

    def stop(self):
        self.icon.stop()
