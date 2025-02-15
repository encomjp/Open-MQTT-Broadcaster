import tkinter as tk
from config.theme import ThemeColors
from modules.mqtt_connection import MQTTHandler
from .components.base import StatusBar
from .components.message_components import MessageComponents
from .components.control_components import ControlComponents
import json
from datetime import datetime
import os
import logging
import threading
import tkinter.ttk as ttk
import time
from queue import Queue

logger = logging.getLogger('main_window')

class MQTTBroadcaster:
    def __init__(self, root):
        self.root = root
        self.root.title("MQTT Broadcaster")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        
        # Initialize basic properties
        self.colors = ThemeColors()
        
        self.messages = []
        self.stats_file = "channel_stats.json"
        self.channel_stats = {}
        self._stats_lock = threading.Lock()
        self._broadcast_active = False
        self.num_threads = 1  # Default number of threads
        self.batch_size = 200  # Internal batch processing size (fixed)
        self.refresh_interval = 0    # Refresh Interval (ms) between UI update batches
        self.cached_messages_limit = 200  # Maximum number of messages to keep in the display
        
        # Initialize GUI first
        self._init_gui()
        self._initialize_after_gui()
        
        # Register cleanup handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        """Handle window closing"""
        try:
            # Save stats before closing
            self._save_channel_stats()
            
            # Disconnect MQTT if connected
            if hasattr(self, 'mqtt') and self.mqtt:
                self.mqtt.disconnect()
            
            # Destroy the window
            self.root.destroy()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            self.root.destroy()

    def _initialize_after_gui(self):
        """Initialize components after GUI is ready"""
        try:
            logger.info("Initializing MQTT handler...")
            # Initialize MQTT handler
            self.mqtt = MQTTHandler(
                message_callback=self._on_message,
                connection_callback=self._on_connection_status,
                disconnection_callback=self._on_disconnection
            )
            
            self._initialize_modules()
            
            logger.info("Loading channel stats...")
            # Load channel stats
            self._load_channel_stats()
            
            logger.info("Initialization complete")
            
        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            self._show_error("Initialization Error", str(e))

    def _init_gui(self):
        from tkinter import ttk
        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Create a container frame for the Notebook and Status Bar
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=0)
        container.grid_columnconfigure(0, weight=1)
        
        # Create Notebook inside container
        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        
        # Broadcaster Tab (existing functionality)
        broadcaster_tab = ttk.Frame(self.notebook)
        broadcaster_tab.grid_columnconfigure(0, weight=1)
        broadcaster_tab.grid_rowconfigure(1, weight=1)
        self.notebook.add(broadcaster_tab, text="Broadcaster")
        
        # Control components (connection and broadcast) in Broadcaster Tab
        self.controls = ControlComponents(
            broadcaster_tab, 
            self.colors,
            on_connect=self._connect_to_broker,
            on_disconnect=self._disconnect_from_broker,
            on_broadcast=self._start_broadcast
        )
        self.controls.frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 0))
        
        # Message components (channels and messages) in Broadcaster Tab
        self.messages_ui = MessageComponents(
            broadcaster_tab,
            self.colors,
            on_channel_selection=self._on_channel_selection
        )
        self.messages_ui.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # MQTT Scanner Tab
        scanner_tab = ttk.Frame(self.notebook)
        scanner_tab.grid_columnconfigure(0, weight=1)
        scanner_tab.grid_rowconfigure(1, weight=1)
        self.notebook.add(scanner_tab, text="MQTT Scanner")

        # Scanner UI: a frame with a button to scan and a listbox for results
        scanner_frame = ttk.Frame(scanner_tab, padding=10)
        scanner_frame.grid(row=0, column=0, sticky="nsew")
        scanner_frame.grid_columnconfigure(0, weight=1)
        scanner_frame.grid_rowconfigure(1, weight=1)

        scan_button = ttk.Button(scanner_frame, text="Scan for MQTT Servers", command=self._start_scan)
        scan_button.grid(row=0, column=0, sticky="w", pady=5)

        # Listbox to display scan results
        self.scan_results = tk.Listbox(scanner_frame, bg=self.colors['bg_lighter'], fg=self.colors['fg'])
        self.scan_results.grid(row=1, column=0, sticky="nsew", pady=5)

        # Button to connect to selected scanned server
        connect_scanned_button = ttk.Button(scanner_frame, text="Connect to Selected Server", command=self._connect_scanned_server)
        connect_scanned_button.grid(row=2, column=0, sticky="w", pady=5)

        # Status bar below the Notebook, within the container
        self.status_bar = StatusBar(container, self.colors)
        self.status_bar.frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))

    def _connect_to_broker(self, connection_info):
        """Establish connection to MQTT broker"""
        def connect_thread():
            try:
                self.mqtt.connect(
                    connection_info["host"],
                    connection_info["port"],
                    connection_info["protocol"],
                    connection_info["topic"]
                )
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda error_msg=error_msg: self._on_connection_status(False, error_msg))

        # Start connection in separate thread
        threading.Thread(target=connect_thread, daemon=True).start()
        self._display_message("System", "Connecting to broker...")

    def _disconnect_from_broker(self):
        self.mqtt.disconnect()
        self.controls.set_connected_state(False)
        self._display_message("System", "Disconnected from broker")

    def _on_connection_status(self, is_connected, error=None):
        """Handle connection status changes"""
        if is_connected:
            self._display_message("System", "Connected to broker")
            self.controls.set_connected_state(True)
        else:
            self._display_message("Error", f"Connection failed: {error}")
            self.controls.set_connected_state(False)
        self.status_bar.update_connection_status(is_connected)

    def _on_disconnection(self, rc):
        if rc != 0:
            self._display_message("Error", f"Unexpected disconnection (code: {rc})")
        self.status_bar.update_connection_status(False)

    def _on_message(self, message):
        try:
            channel = message.topic
            payload = message.payload.decode()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if channel not in self.messages_ui.get_channels():
                self.messages_ui.add_channel(channel)
            else:
                self.messages_ui.mark_channel_seen(channel)
            
            self._update_channel_stats(channel, "received")
            self._display_message(channel, payload, timestamp)
            
        except Exception as e:
            self._display_message("Error", f"Failed to process message: {str(e)}")

    def _display_message(self, channel, message, timestamp=None):
        """Display a message in the message area"""
        if not timestamp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # More robust message type detection
        msg_type = "normal"
        if channel.lower() in ["error", "system"]:
            msg_type = channel.lower()
        elif isinstance(message, str) and "broadcast" in message.lower():
            msg_type = "broadcast"

        # Display if relevant
        current = self.messages_ui.get_current_channel()
        if current in (None, "All Channels") or current == channel:
            self.messages_ui.display_message(channel, message, timestamp, msg_type)

    def _start_broadcast(self, broadcast_info):
        if not self.mqtt.is_connected:
            self._show_error("Not Connected", "Please connect to a broker first")
            return
            
        target_channels = (self.messages_ui.get_selected_channels() 
                         if broadcast_info["target_type"] == "Selected Channels"
                         else [ch for ch in self.messages_ui.get_channels() if ch != "All Channels"])
        
        if not target_channels:
            self._show_error("No Channels", "No channels selected for broadcast")
            return

        try:
            self.num_threads = int(self.thread_entry.get())
        except ValueError:
            self.num_threads = 1
        self._perform_broadcast(broadcast_info, target_channels)

    def _perform_broadcast(self, broadcast_info, target_channels):
        """Perform broadcast using Tkinter's event loop"""
        from queue import Queue
        total_messages = broadcast_info["count"] * len(target_channels)
        self._broadcast_active = True
        self._broadcast_stats = {
            'total_sent': 0,
            'failed_sends': 0,
            'total_messages': total_messages
        }

        # Create a queue with each channel repeated for the number of messages to send
        self._broadcast_queue = Queue()
        for _ in range(broadcast_info["count"]):
            for channel in target_channels:
                self._broadcast_queue.put(channel)

        self.controls.set_broadcast_state(True)
        self._display_message("System", "Starting broadcast...")

        self._broadcast_lock = threading.Lock()
        self._broadcast_threads = []
        for _ in range(self.num_threads):
            thread = threading.Thread(target=self._worker_send_message, args=(broadcast_info["message"], broadcast_info["delay"]))
            thread.daemon = True
            thread.start()
            self._broadcast_threads.append(thread)
        self.root.after(100, self._check_broadcast_complete)

    def _worker_send_message(self, message, delay):
        import time
        while True:
            try:
                channel = self._broadcast_queue.get_nowait()
            except Exception:
                break
            try:
                self.mqtt.publish(channel, message)
                self._update_channel_stats(channel, "sent")
                with self._broadcast_lock:
                    self._broadcast_stats['total_sent'] += 1
            except Exception as e:
                with self._broadcast_lock:
                    self._broadcast_stats['failed_sends'] += 1
                self.root.after(0, lambda: self._display_message("Error", f"Failed to send to {channel}: {str(e)}"))

            with self._broadcast_lock:
                progress = (self._broadcast_stats['total_sent'] / self._broadcast_stats['total_messages']) * 100
            self.root.after(0, lambda: self.controls.set_broadcast_state(True, progress))

            time.sleep(delay)
            self._broadcast_queue.task_done()

    def _check_broadcast_complete(self):
        if self._broadcast_queue.empty():
            self._finalize_broadcast(self._broadcast_stats['total_sent'], self._broadcast_stats['failed_sends'])
            self.controls.set_broadcast_state(False)
        else:
            self.root.after(100, self._check_broadcast_complete)

    def _update_progress(self, total_sent, failed_sends, total_messages):
        """Update broadcast progress"""
        progress = (total_sent / total_messages) * 100
        success_rate = ((total_sent - failed_sends) / total_sent) * 100 if total_sent > 0 else 100
        status = f"Broadcasting... {progress:.1f}% ({total_sent}/{total_messages})"
        self.status_bar.update_status(status)

    def _finalize_broadcast(self, total_sent, failed_sends):
        """Complete the broadcast operation"""
        success_rate = ((total_sent - failed_sends) / total_sent) * 100 if total_sent > 0 else 0
        status = f"Broadcast complete - Messages sent: {total_sent}"
        
        if failed_sends == 0:
            self.status_bar.update_status(status, "success")
        else:
            self.status_bar.update_status(f"{status} ({failed_sends} failed)", "error")
        
        self._display_message("System", status)
        self._save_channel_stats()
        self.controls.set_broadcast_state(False)

    def _on_channel_selection(self):
        # Refresh message display
        self.messages_ui.clear_messages()
        current = self.messages_ui.get_current_channel()
        
        if current:
            messages_to_display = [msg for msg in self.messages if current == "All Channels" or current == msg["channel"]]
            self._display_messages_async(messages_to_display, 0)

    def _display_messages_async(self, messages, index, batch_size=50):
        if index < len(messages):
            texts = []
            for msg in messages[index:index+self.batch_size]:
                channel = msg["channel"]
                message = msg["message"]
                timestamp = msg["timestamp"]
                msg_type = "normal"
                if channel.lower() in ["error", "system"]:
                    msg_type = channel.lower()
                elif isinstance(message, str) and "broadcast" in message.lower():
                    msg_type = "broadcast"
                texts.append((f"[{timestamp}] ", "timestamp"))
                texts.append((f"{channel}: {message}\n", msg_type))

            # Group consecutive texts with the same tag for faster processing
            grouped = []
            if texts:
                current_text, current_tag = texts[0]
                for text, tag in texts[1:]:
                    if tag == current_tag:
                        current_text += text
                    else:
                        grouped.append((current_text, current_tag))
                        current_text, current_tag = text, tag
                grouped.append((current_text, current_tag))

            # Combine grouped texts into one single string and record tag positions
            combined_text = ""
            tag_positions = []
            for text, tag in grouped:
                start_offset = len(combined_text)
                combined_text += text
                end_offset = len(combined_text)
                tag_positions.append((tag, start_offset, end_offset))

            self.messages_ui.text.config(state='normal')
            start_index = self.messages_ui.text.index(tk.END)
            self.messages_ui.text.insert(tk.END, combined_text)
            for tag, start_offset, end_offset in tag_positions:
                self.messages_ui.text.tag_add(tag, f"{start_index} + {start_offset} chars", f"{start_index} + {end_offset} chars")

            # Trim excessive lines to keep performance
            try:
                current_lines = int(self.messages_ui.text.index("end-1c").split('.')[0])
                max_lines = self.cached_messages_limit
                if current_lines > max_lines:
                    lines_to_delete = current_lines - max_lines
                    self.messages_ui.text.delete("1.0", f"{lines_to_delete + 1}.0")
            except Exception:
                pass

            if self.messages_ui._auto_scroll:
                self.messages_ui.text.see(tk.END)
            self.messages_ui.text.config(state='disabled')
            self.root.after(self.refresh_interval, lambda: self._display_messages_async(messages, index + self.batch_size, self.batch_size))

    def _update_channel_stats(self, channel, action):
        with self._stats_lock:
            if channel not in self.channel_stats:
                self.channel_stats[channel] = {"received": 0, "sent": 0}
            self.channel_stats[channel][action] += 1

            total_received = sum(stats["received"] for stats in self.channel_stats.values())
            total_sent = sum(stats["sent"] for stats in self.channel_stats.values())
        self.status_bar.update_message_count(total_received, total_sent, len(self.channel_stats))

    def _load_channel_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    self.channel_stats = json.load(f)
                self._display_message("System", "Ready to connect")
        except Exception as e:
            self._display_message("Error", f"Failed to load channel statistics: {str(e)}")

    def _save_channel_stats(self):
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.channel_stats, f)
        except Exception as e:
            self._display_message("Error", f"Failed to save channel statistics: {str(e)}")

    def _show_error(self, title, message):
        import tkinter.messagebox as messagebox
        messagebox.showerror(title, message)

    def _start_channel_status_checker(self):
        """This method is no longer needed as status checking is now threaded in MessageComponents"""
        pass

    def _apply_advanced_settings(self):
        try:
            refresh_interval = int(self.refresh_interval_entry.get().strip())
            cached_limit = int(self.cached_messages_limit_entry.get().strip())
            self.refresh_interval = refresh_interval
            self.cached_messages_limit = cached_limit
            self._display_message("System", "Advanced settings applied.")
        except Exception as e:
            self._display_message("Error", f"Failed to apply advanced settings: {str(e)}")

    def _initialize_modules(self):
        """Initialize additional modules using the module loader."""
        try:
            import modules.module_loader as module_loader
            self.modules = module_loader.load_all_modules()
            logger.info(f"Loaded modules: {list(self.modules.keys())}")
        except Exception as e:
            logger.error(f"Module initialization error: {e}", exc_info=True)
            self.modules = {}

    def _start_scan(self):
        """Scan local network for MQTT servers (dummy implementation)."""
        import tkinter as tk
        # Clear previous scan results
        self.scan_results.delete(0, tk.END)

        # Dummy scan results; replace with real network scanning logic
        dummy_results = ["192.168.1.10:1883", "192.168.1.15:1883"]
        for server in dummy_results:
            self.scan_results.insert(tk.END, server)

        # Optionally, display a system message about scan completion
        self._display_message("System", f"Scan complete. Found {len(dummy_results)} servers.")

    def _connect_scanned_server(self):
        """Connect to the selected scanned MQTT server."""
        import tkinter as tk
        from tkinter import messagebox
        selection = self.scan_results.curselection()
        if not selection:
            messagebox.showerror("No Selection", "Please select a server from the scan results.")
            return

        server = self.scan_results.get(selection[0])
        try:
            host, port = server.split(":")
            port = int(port)
        except Exception as e:
            messagebox.showerror("Invalid Format", "Selected server is not in the correct 'ip:port' format.")
            return

        # Update connection fields in the ControlComponents of Broadcaster tab
        self.controls.ip_entry.delete(0, tk.END)
        self.controls.ip_entry.insert(0, host)

        self.controls.port_entry.delete(0, tk.END)
        self.controls.port_entry.insert(0, str(port))

        # Set protocol to 'mqtt' and topic to '#' as defaults
        self.controls.protocol_combo.set("mqtt")
        self.controls.topic_entry.delete(0, tk.END)
        self.controls.topic_entry.insert(0, "#")

        # Retrieve connection info using the existing method
        connection_info = self.controls._get_connection_info()
        if connection_info and self.controls.on_connect:
            self.controls.on_connect(connection_info)
        else:
            messagebox.showerror("Connection Error", "Unable to retrieve connection info.")