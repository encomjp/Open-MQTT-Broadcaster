import tkinter as tk
from tkinter import ttk

class BaseComponent:
    def __init__(self, parent, colors):
        self.parent = parent
        self.colors = colors
        self.frame = None

class StyledFrame(BaseComponent):
    def __init__(self, parent, colors, title=None, style='Dark.TFrame'):
        super().__init__(parent, colors)
        self.frame = (
            ttk.LabelFrame(parent, text=title, style='Dark.TLabelframe')
            if title else
            ttk.Frame(parent, style=style)
        )

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

class StatusBar(BaseComponent):
    def __init__(self, parent, colors):
        super().__init__(parent, colors)
        self.frame = ttk.Frame(parent, style='Dark.TFrame')
        self.frame.grid_columnconfigure(1, weight=1)
        self._setup_labels()

    def _setup_labels(self):
        labels = {
            'connection_status': ('Disconnected', 'w', 0),
            'status_label': ('Ready', 'w', 1),
            'message_count_label': ('Messages: 0', 'e', 2)
        }
        
        for name, (text, sticky, col) in labels.items():
            label = ttk.Label(
                self.frame,
                text=text,
                style='Dark.TLabel',
                padding=(8, 4)
            )
            label.grid(row=0, column=col, sticky=sticky)
            setattr(self, name, label)

    def update_connection_status(self, is_connected):
        text = "Connected" if is_connected else "Disconnected"
        bg = self.colors['status_success' if is_connected else 'status_error']
        self.connection_status.configure(text=text, background=bg)

    def update_status(self, message, status_type="normal"):
        bg_color = {
            "error": self.colors['status_error'],
            "success": self.colors['status_success']
        }.get(status_type, self.colors['status_bg'])
        
        for widget in (self.frame, self.status_label, 
                      self.message_count_label, self.connection_status):
            widget.configure(background=bg_color)
        self.status_label.configure(text=message)

    def update_message_count(self, received, sent, channels):
        self.message_count_label.configure(
            text=f"Messages - Received: {received} | Sent: {sent} | Channels: {channels}"
        )