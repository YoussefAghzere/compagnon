"""Scrollable settings panels that remain usable on small or scaled displays."""
import tkinter as tk
from tkinter import ttk


class ScrollablePanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style='Card.TFrame')
        self.canvas = tk.Canvas(self, background='white', highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = ttk.Frame(self.canvas, style='Card.TFrame', padding=24)
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.content.bind('<Configure>', self.layout)
        self.canvas.bind('<Configure>', self.resize)
        self.winfo_toplevel().bind('<MouseWheel>', self.wheel, add='+')
        self.winfo_toplevel().bind('<FocusIn>', self.reveal_focus, add='+')

    def layout(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        def wrap(parent):
            for child in parent.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(wraplength=max(180, event.width - 64))
                wrap(child)
        wrap(self.content)

    def wheel(self, event):
        if not self.canvas.winfo_ismapped():
            return
        x, y = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        if x <= event.x_root < x + self.canvas.winfo_width() and y <= event.y_root < y + self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')

    def reveal_focus(self, event):
        widget = event.widget
        parent = widget
        while parent is not None and parent != self.content:
            parent = getattr(parent, 'master', None)
        if parent is None or not self.canvas.winfo_ismapped():
            return
        top = widget.winfo_rooty() - self.content.winfo_rooty()
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + self.canvas.winfo_height()
        if top < view_top or top + widget.winfo_height() > view_bottom:
            height = max(1, self.content.winfo_height())
            self.canvas.yview_moveto(max(0, top - 12) / height)
