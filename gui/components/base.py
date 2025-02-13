import tkinter as tk
from tkinter import ttk

class BaseComponent:
    def __init__(self, parent, colors):
        self.parent = parent
        self.colors = colors
        self.frame = None
        self.style = ttk.Style()

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
        style_name = 'Success.TLabel' if is_connected else 'Error.TLabel'
        self.style.configure(style_name, background=self.colors['status_success' if is_connected else 'status_error'])
        self.connection_status.configure(text=text, style=style_name)

    def update_status(self, message, status_type="normal"):
        style_name = {
            "error": 'Error.TLabel',
            "success": 'Success.TLabel'
        }.get(status_type, 'Normal.TLabel')
        self.style.configure(style_name, background=self.colors['status_bg'])
        for widget in (self.frame, self.status_label, 
                      self.message_count_label, self.connection_status):
            widget.configure(style=style_name)
        self.status_label.configure(text=message)

    def update_message_count(self, received, sent, channels):
        self.message_count_label.configure(
            text=f"Messages - Received: {received} | Sent: {sent} | Channels: {channels}"
        )