import tkinter as tk
from tkinter import ttk, messagebox
from .base import BaseComponent, StyledFrame

class ControlComponents(BaseComponent):
    def __init__(self, parent, colors, on_connect=None, on_disconnect=None, on_broadcast=None):
        super().__init__(parent, colors)
        from tkinter import ttk
        self.frame = ttk.Frame(parent, style='Dark.TFrame')
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_broadcast = on_broadcast
        self._setup_components()

    def _setup_components(self):
        # Connection Frame
        self.connection_frame = self._create_connection_frame()
        self.connection_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))

        # Broadcast Frame
        self.broadcast_frame = self._create_broadcast_frame()
        self.broadcast_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

    def _create_connection_frame(self):
        frame = StyledFrame(self.frame, self.colors, title="Connection Settings")
        
        # Connection Details
        self.conn_details = ttk.Frame(frame.frame, style='Dark.TFrame')
        self.conn_details.grid(row=1, column=0, columnspan=6, pady=5)

        # Create connection fields
        self._create_connection_fields()

        # Connect Button
        self.connect_button = ttk.Button(
            frame.frame,
            text="Connect",
            command=self._toggle_connection,
            style='Dark.TButton'
        )
        self.connect_button.grid(row=1, column=6, padx=5, pady=5)

        return frame

    def _create_connection_fields(self):
        fields = [
            ("IP:", "ip_entry", "10.16.1.246", 15),
            ("Port:", "port_entry", "1883", 6),
            ("Protocol:", "protocol_combo", "mqtt", 6, ["mqtt", "mqtts"]),
            ("Topic:", "topic_entry", "#", 15)
        ]

        for i, (label, attr, default, width, *extra) in enumerate(fields):
            ttk.Label(self.conn_details, text=label, style='Dark.TLabel').grid(row=0, column=i*2, padx=5)
            
            widget = (
                ttk.Combobox(
                    self.conn_details,
                    values=extra[0],
                    width=width,
                    style='Dark.TCombobox'
                ) if extra else
                ttk.Entry(
                    self.conn_details,
                    width=width,
                    style='Dark.TEntry'
                )
            )
            widget.insert(0, default)
            widget.grid(row=0, column=i*2+1, padx=5)
            setattr(self, attr, widget)

    def _create_broadcast_frame(self):
        frame = StyledFrame(self.frame, self.colors, title="Message Broadcasting")
        frame.frame.grid_columnconfigure(1, weight=1)

        # Create broadcast components
        self._create_broadcast_options(frame)
        self._create_broadcast_inputs(frame)
        
        return frame

    def _create_broadcast_options(self, frame):
        options = ttk.Frame(frame.frame, style='Dark.TFrame')
        options.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        options.grid_columnconfigure(1, weight=1)
        options.grid_columnconfigure(3, weight=1)

        # Message count
        ttk.Label(options, text="Number of messages:", style='Dark.TLabel').grid(row=0, column=0, padx=5)
        self.msg_count_var = tk.StringVar(value="1")
        ttk.Entry(options, textvariable=self.msg_count_var, width=5, style='Dark.TEntry').grid(
            row=0, column=1, padx=5, sticky="w"
        )

        # Target selection
        ttk.Label(options, text="Target:", style='Dark.TLabel').grid(row=0, column=2, padx=5)
        self.broadcast_target = ttk.Combobox(
            options,
            values=["Selected Channels", "All Channels"],
            style='Dark.TCombobox',
            width=15,
            state="readonly"
        )
        self.broadcast_target.set("Selected Channels")
        self.broadcast_target.grid(row=0, column=3, padx=5, sticky="ew")

    def _create_broadcast_inputs(self, frame):
        # Message input
        ttk.Label(frame.frame, text="Message Template:", style='Dark.TLabel').grid(
            row=1, column=0, padx=5, pady=2
        )
        self.message_input = ttk.Entry(frame.frame, style='Dark.TEntry')
        self.message_input.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        # Delay control
        delay_frame = ttk.Frame(frame.frame, style='Dark.TFrame')
        delay_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        delay_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(delay_frame, text="Delay:", style='Dark.TLabel').grid(row=0, column=0, padx=5)

        # Create the delay value label first
        self.delay_value_label = ttk.Label(delay_frame, text="1000 ms", style='Dark.TLabel')
        self.delay_value_label.grid(row=0, column=2, padx=5)

        self.delay_slider = ttk.Scale(
            delay_frame,
            from_=0, to=5000,
            orient=tk.HORIZONTAL,
            style='Dark.Horizontal.TScale',
            command=lambda value: self.delay_value_label.config(text=f"{int(float(value))} ms")
        )
        self.delay_slider.set(1000)
        self.delay_slider.grid(row=0, column=1, sticky="ew", padx=5)

        # Broadcast button
        self.broadcast_button = ttk.Button(
            frame.frame,
            text="Broadcast Messages",
            command=self._start_broadcast,
            style='Dark.TButton'
        )
        self.broadcast_button.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

    # Connection methods
    def _toggle_connection(self):
        """Handle connection toggle with loading state"""
        if self.connect_button.cget('text') == "Connect":
            # Disable button and show connecting state
            self.connect_button.configure(text="Connecting...", state='disabled')
            connection_info = self._get_connection_info()
            if connection_info and self.on_connect:
                self.on_connect(connection_info)
        elif self.on_disconnect:
            self.on_disconnect()

    def _get_connection_info(self):
        try:
            host = self.ip_entry.get().strip()
            if not host:
                raise ValueError("IP address cannot be empty")

            try:
                port = int(self.port_entry.get())
                if not (0 <= port <= 65535):
                    raise ValueError()
            except ValueError:
                raise ValueError("Port must be a number between 0 and 65535")

            protocol = self.protocol_combo.get()

            return {
                "host": host,
                "port": port,
                "protocol": protocol,
                "topic": self.topic_entry.get().strip() or "#",
            }
        except ValueError as e:
            messagebox.showerror("Connection Error", str(e))
            return None

    def set_connected_state(self, is_connected):
        """Update connection button state"""
        self.connect_button.configure(
            text="Disconnect" if is_connected else "Connect",
            state='normal'
        )

    # Broadcast methods
    def _start_broadcast(self):
        try:
            msg_count = self._validate_message_count()
            if not msg_count:
                return

            message = self.message_input.get().strip()
            if not message:
                raise ValueError("Message template cannot be empty")

            if self.on_broadcast:
                self.on_broadcast({
                    "message": message,
                    "count": msg_count,
                    "delay": self.delay_slider.get() / 1000.0,
                    "target_type": self.broadcast_target.get()
                })

        except ValueError as e:
            messagebox.showerror("Broadcast Error", str(e))

    def _validate_message_count(self):
        try:
            count = int(self.msg_count_var.get())
            if count < 1:
                raise ValueError("Message count must be at least 1")
            if count > 1000 and not messagebox.askyesno(
                "Warning",
                f"You are about to send {count} messages. This might take a while. Continue?"
            ):
                return None
            return count
        except ValueError:
            raise ValueError("Message count must be a positive number")

    def set_broadcast_state(self, is_broadcasting, progress=None):
        if is_broadcasting:
            text = f"Broadcasting... {progress:.1f}%" if progress else "Broadcasting..."
            style = 'Progress.Dark.TButton'
            state = 'disabled'
        else:
            text = "Broadcast Messages"
            style = 'Dark.TButton'
            state = 'normal'
            
        self.broadcast_button.configure(text=text, style=style, state=state)