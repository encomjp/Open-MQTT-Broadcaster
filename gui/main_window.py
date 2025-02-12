import tkinter as tk
from config.theme import ThemeColors
from utils.mqtt_handler import MQTTHandler
from .components.base import StatusBar
from .components.message_components import MessageComponents
from .components.control_components import ControlComponents
import json
from datetime import datetime
import os
import logging

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
        self._broadcast_active = False
        
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
            
            logger.info("Loading channel stats...")
            # Load channel stats
            self._load_channel_stats()
            
            logger.info("Initialization complete")
            
        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            self._show_error("Initialization Error", str(e))

    def _init_gui(self):
        # Configure main window grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        
        # Control components (connection and broadcast)
        self.controls = ControlComponents(
            self.root, 
            self.colors,
            on_connect=self._connect_to_broker,
            on_disconnect=self._disconnect_from_broker,
            on_broadcast=self._start_broadcast
        )
        
        # Message components (channels and messages)
        self.messages_ui = MessageComponents(
            self.root,
            self.colors,
            on_channel_selection=self._on_channel_selection
        )
        self.messages_ui.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        # Status bar
        self.status_bar = StatusBar(self.root, self.colors)
        self.status_bar.frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))

    def _connect_to_broker(self, connection_info):
        """Establish connection to MQTT broker"""
        if connection_info["auto"]:
            try:
                host, port, protocol = MQTTHandler.auto_detect_connection()
                self.mqtt.connect(host, port, protocol, connection_info["topic"])
            except Exception as e:
                self._show_error("Auto-detection failed", str(e))
                self.controls.set_connected_state(False)
                return
        else:
            self.mqtt.connect(
                connection_info["host"],
                connection_info["port"],
                connection_info["protocol"],
                connection_info["topic"]
            )

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

        # Determine message type
        if channel.lower() == "error":
            msg_type = "error"
        elif channel.lower() == "system":
            msg_type = "system"
        elif "broadcast" in message.lower():
            msg_type = "broadcast"
        else:
            msg_type = "normal"

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

        self._perform_broadcast(broadcast_info, target_channels)

    def _perform_broadcast(self, broadcast_info, target_channels):
        """Perform broadcast using Tkinter's event loop"""
        if self._broadcast_active:
            return

        total_messages = broadcast_info["count"] * len(target_channels)
        self._broadcast_active = True
        self._broadcast_stats = {
            'total_sent': 0,
            'failed_sends': 0,
            'total_messages': total_messages,
            'current_msg': 0,
            'current_channel_idx': 0,
            'target_channels': target_channels,
            'broadcast_info': broadcast_info
        }
        
        self.controls.set_broadcast_state(True)
        self._display_message("System", "Starting broadcast...")
        
        # Schedule the first message
        self.root.after(10, self._send_next_message)

    def _send_next_message(self):
        """Send next message in broadcast sequence"""
        if not self._broadcast_active:
            return

        stats = self._broadcast_stats
        try:
            channel = stats['target_channels'][stats['current_channel_idx']]
            message = stats['broadcast_info']['message']  # Remove the message count suffix
            
            try:
                self.mqtt.publish(channel, message)
                self._update_channel_stats(channel, "sent")
                stats['total_sent'] += 1
                
                progress = (stats['total_sent'] / stats['total_messages']) * 100
                self.controls.set_broadcast_state(True, progress)
                
                if stats['total_sent'] % 5 == 0:
                    self._update_progress(stats['total_sent'], stats['failed_sends'], stats['total_messages'])
                
            except Exception as e:
                stats['failed_sends'] += 1
                self._display_message("Error", f"Failed to send to {channel}: {str(e)}")

            # Move to next channel
            stats['current_channel_idx'] += 1
            if stats['current_channel_idx'] >= len(stats['target_channels']):
                stats['current_channel_idx'] = 0
                stats['current_msg'] += 1

            # Check if broadcast is complete
            if stats['current_msg'] >= stats['broadcast_info']['count']:
                self._finalize_broadcast(stats['total_sent'], stats['failed_sends'])
                self._broadcast_active = False
                return

            # Schedule next message with delay
            delay = int(stats['broadcast_info']['delay'] * 1000)  # Convert to milliseconds
            self.root.after(delay, self._send_next_message)
            
        except Exception as e:
            self._display_message("Error", f"Broadcast failed: {str(e)}")
            self._broadcast_active = False
            self.controls.set_broadcast_state(False)

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
            for msg in self.messages:
                if current == "All Channels" or current == msg["channel"]:
                    self._display_message(
                        msg["channel"],
                        msg["message"],
                        msg["timestamp"]
                    )

    def _update_channel_stats(self, channel, action):
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
                self._display_message("System", f"Loaded statistics for {len(self.channel_stats)} channels")
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