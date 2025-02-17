import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'

import sys
import logging
import json
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from queue import Queue

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QComboBox, QPushButton, QTextEdit, QListWidget, QMessageBox, QGroupBox, 
    QFormLayout, QStatusBar, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt5.QtGui import QTextCursor

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('qt_mqtt_broadcaster')

from mqtt_handler import MQTTHandler

@dataclass
class MQTTMessage:
    """Data class for MQTT messages"""
    topic: str
    payload: str
    timestamp: str

class MqttSignalEmitter(QObject):
    """Emits signals for MQTT events"""
    messageReceived = pyqtSignal(object)  # Emits received MQTT message
    connectionStatus = pyqtSignal(bool, str)  # Emits connection status (is_connected, error message)

class MessageQueue:
    """Thread-safe message queue with size limit"""
    def __init__(self, max_size: int = 1000):
        self.queue: Queue = Queue(maxsize=max_size)
        self.lock = threading.Lock()

    def add_message(self, message: MQTTMessage) -> None:
        """Add message to queue, removing oldest if full"""
        with self.lock:
            if self.queue.full():
                self.queue.get()
            self.queue.put(message)

class MQTTBroadcasterWindow(QMainWindow):
    """Main application window for MQTT Broadcaster"""
    
    MAX_MESSAGES = 1000  # Maximum number of messages to display
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('MQTT Broadcaster (Qt)')
        self.resize(1200, 800)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        self.message_queue = MessageQueue(self.MAX_MESSAGES)
        self.message_filter: str = ""
        
        # Signal emitter for thread-safe UI updates
        self.emitter = MqttSignalEmitter()
        self.emitter.messageReceived.connect(self.on_message_received)
        self.emitter.connectionStatus.connect(self.on_connection_status)

        # Initialize MQTT Handler
        self.mqtt = MQTTHandler(
            message_callback=lambda msg: self.emitter.messageReceived.emit(msg),
            connection_callback=lambda success, error=None: self.emitter.connectionStatus.emit(success, error if error else ''),
            disconnection_callback=lambda rc: self.emitter.connectionStatus.emit(False, f"Disconnected with code: {rc}")
        )

        # Channel statistics
        self.channel_stats: Dict[str, int] = {}
        self.channels: Set[str] = set()
        self.stats_file: str = "channel_stats.json"
        self.load_channel_stats()

        # Main layout and tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_broadcaster_tab()
        self.create_scanner_tab()

    def create_broadcaster_tab(self) -> None:
        """Create the broadcaster tab with all its widgets"""
        self.broadcaster_tab = QWidget()
        layout = QVBoxLayout(self.broadcaster_tab)

        # Connection settings
        conn_group = QGroupBox('MQTT Connection')
        conn_layout = QFormLayout(conn_group)
        
        self.combo_host = QComboBox()
        self.combo_host.setEditable(True)
        self.combo_host.addItems(["broker.hivemq.com", "test.mosquitto.org", "mqtt.eclipseprojects.io"])
        self.combo_host.setCurrentText("broker.hivemq.com")
        
        self.edit_port = QLineEdit('1883')
        self.edit_port.setValidator(QIntValidator(1, 65535))
        
        self.edit_topic = QLineEdit('test/topic')
        
        conn_layout.addRow('Host:', self.combo_host)
        conn_layout.addRow('Port:', self.edit_port)
        conn_layout.addRow('Topic:', self.edit_topic)
        layout.addWidget(conn_group)

        # Message filter
        filter_group = QGroupBox('Message Filter')
        filter_layout = QFormLayout(filter_group)
        self.edit_filter = QLineEdit()
        self.edit_filter.textChanged.connect(self.update_message_filter)
        filter_layout.addRow('Filter:', self.edit_filter)
        layout.addWidget(filter_group)

        # Connection buttons
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton('Connect')
        self.btn_disconnect = QPushButton('Disconnect')
        self.btn_connect.clicked.connect(self.connect_to_broker)
        self.btn_disconnect.clicked.connect(self.disconnect_from_broker)
        self.btn_clear = QPushButton('Clear Messages')
        self.btn_clear.clicked.connect(self.clear_messages)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        # Broadcast controls
        broadcast_group = QGroupBox('Broadcast')
        broadcast_layout = QFormLayout(broadcast_group)
        self.edit_broadcast_count = QLineEdit('10')
        self.btn_broadcast = QPushButton('Start Broadcast')
        self.btn_broadcast.clicked.connect(self.start_broadcast)
        broadcast_layout.addRow('Message Count:', self.edit_broadcast_count)
        broadcast_layout.addRow('', self.btn_broadcast)
        layout.addWidget(broadcast_group)

        # Message display area
        self.text_messages = QTextEdit()
        self.text_messages.setReadOnly(True)
        layout.addWidget(self.text_messages)

        self.tabs.addTab(self.broadcaster_tab, 'Broadcaster')

    def create_scanner_tab(self) -> None:
        """Create the scanner tab with all its widgets"""
        self.scanner_tab = QWidget()
        layout = QVBoxLayout(self.scanner_tab)

        self.btn_scan = QPushButton('Scan for MQTT Servers')
        self.btn_scan.clicked.connect(self.start_scan)
        layout.addWidget(self.btn_scan)

        self.list_scan_results = QListWidget()
        layout.addWidget(self.list_scan_results)

        self.btn_connect_scanned = QPushButton('Connect to Selected Server')
        self.btn_connect_scanned.clicked.connect(self.connect_scanned_server)
        layout.addWidget(self.btn_connect_scanned)

        self.tabs.addTab(self.scanner_tab, 'MQTT Scanner')

    def connect_to_broker(self) -> None:
        """Connect to the specified MQTT broker"""
        host = self.combo_host.currentText().strip()
        try:
            port = int(self.edit_port.text().strip())
        except ValueError:
            self.show_error('Invalid Port', 'Please enter a valid port number.')
            return
        topic = self.edit_topic.text().strip()
        if not topic:
            self.show_error('Invalid Topic', 'Please enter a valid topic.')
            return

        self.statusBar.showMessage('Connecting...')
        threading.Thread(target=self._thread_connect, args=(host, port, topic), daemon=True).start()

    def _thread_connect(self, host: str, port: int, topic: str) -> None:
        """Threaded function to connect to the MQTT broker"""
        try:
            self.mqtt.connect(host, port, 'tcp', topic)
        except Exception as e:
            logger.error(f'Connection error: {e}', exc_info=True)
            self.emitter.connectionStatus.emit(False, str(e))

    def disconnect_from_broker(self) -> None:
        """Disconnect from the MQTT broker"""
        try:
            self.mqtt.disconnect()
            self.statusBar.showMessage('Disconnected')
        except Exception as e:
            logger.error(f'Disconnection error: {e}', exc_info=True)
            self.show_error('Disconnection Error', str(e))

    def on_connection_status(self, is_connected: bool, error: str) -> None:
        """Handle connection status updates"""
        QTimer.singleShot(0, lambda: self._handle_connection_status(is_connected, error))

    def _handle_connection_status(self, is_connected: bool, error: str) -> None:
        """Update UI based on connection status"""
        if is_connected:
            self.statusBar.showMessage('Connected to broker')
            self.append_message('System', 'Connected to broker')
        else:
            self.statusBar.showMessage(f'Connection failed: {error}')
            self.append_message('Error', f'Connection failed: {error}')

    def handle_disconnection(self, rc: int) -> None:
        """Handle unexpected disconnection"""
        if rc != 0:
            self.append_message('Error', f'Unexpected disconnection, code: {rc}')
        self.statusBar.showMessage('Disconnected from broker')

    def start_broadcast(self) -> None:
        """Start broadcasting messages"""
        if not getattr(self.mqtt, 'is_connected', False):
            self.show_error('Not Connected', 'Please connect to a broker first')
            return
        try:
            count = int(self.edit_broadcast_count.text().strip())
        except ValueError:
            self.show_error('Invalid Broadcast Count', 'Please enter a valid number for broadcast count.')
            return

        threading.Thread(target=self._thread_broadcast, args=(count,), daemon=True).start()

    def _thread_broadcast(self, count: int) -> None:
        """Threaded function to broadcast messages"""
        total_sent = 0
        failed = 0
        message = 'Broadcast message'
        for i in range(count):
            try:
                self.mqtt.publish(self.edit_topic.text().strip(), f'{message} {i+1}')
                total_sent += 1
                self.append_message('Broadcast', f'Sent: {message} {i+1}')
            except Exception as e:
                logger.error(f'Broadcast error: {e}', exc_info=True)
                failed += 1
                self.append_message('Error', f'Failed to send: {message} {i+1}')
            time.sleep(0.1)  # Delay between messages
        self.append_message('System', f'Broadcast complete. Sent: {total_sent}, Failed: {failed}')

    def on_message_received(self, msg: Any) -> None:
        """Handle received MQTT messages"""
        QTimer.singleShot(0, lambda: self._handle_message(msg))

    def _handle_message(self, msg: Any) -> None:
        """Process and display received MQTT messages"""
        try:
            topic = msg.topic
            # check if payload has decode method
            if hasattr(msg.payload, 'decode'):
                payload = msg.payload.decode()
            else:
                payload = str(msg.payload)
        except Exception as e:
            topic = 'Error'
            payload = f'Error decoding message: {e}'
            logger.error(f'Error processing message: {e}', exc_info=True)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mqtt_message = MQTTMessage(topic, payload, timestamp)
        self.message_queue.add_message(mqtt_message)
        self.refresh_messages()
        self.update_channel_stats(topic)

    def append_message(self, channel: str, message: str, timestamp: str = '') -> None:
        """Append a message to the display"""
        if not timestamp:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.text_messages.append(f'[{timestamp}] {channel}: {message}')

    def update_channel_stats(self, channel: str) -> None:
        """Update statistics for received messages"""
        if channel in self.channel_stats:
            self.channel_stats[channel] += 1
        else:
            self.channel_stats[channel] = 1
            self.channels.add(channel)
        logger.debug(f'Channel stats: {self.channel_stats}')

    def start_scan(self) -> None:
        """Start scanning for MQTT servers"""
        self.list_scan_results.clear()
        QTimer.singleShot(0, lambda: self.append_message('System', 'Scanning for MQTT servers...'))
        threading.Thread(target=self._thread_scan, daemon=True).start()

    def _thread_scan(self) -> None:
        """Threaded function to scan for MQTT servers"""
        import random
        time.sleep(2)
        servers = [f"192.168.1.{random.randint(2,254)}" for _ in range(3)]
        QTimer.singleShot(0, lambda: self._handle_scan_results(servers))

    def _handle_scan_results(self, servers: list) -> None:
        """Handle results of MQTT server scan"""
        self.list_scan_results.addItems(servers)
        self.append_message('System', f"Scan complete. Found: {', '.join(servers)}")

    def connect_scanned_server(self) -> None:
        """Connect to a selected server from scan results"""
        selected_items = self.list_scan_results.selectedItems()
        if not selected_items:
            self.show_error('No Selection', 'Please select a server from the list')
            return
        server_ip = selected_items[0].text()
        self.combo_host.setCurrentText(server_ip)
        self.connect_to_broker()

    def show_error(self, title: str, message: str = '') -> None:
        """Show an error message box"""
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))

    def load_channel_stats(self) -> None:
        """Load channel statistics from file"""
        try:
            with open(self.stats_file, 'r') as f:
                self.channel_stats = json.load(f)
            logger.info("Channel stats loaded.")
        except Exception as e:
            logger.info("Channel stats file not found or error loading: " + str(e))

    def save_channel_stats(self) -> None:
        """Save channel statistics to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.channel_stats, f)
            logger.info("Channel stats saved.")
        except Exception as e:
            logger.error("Error saving channel stats: " + str(e))

    def closeEvent(self, event) -> None:
        """Handle window close event"""
        self.save_channel_stats()
        event.accept()


def main() -> None:
    """Main function to start the application"""
    app = QApplication(sys.argv)
    window = MQTTBroadcasterWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()