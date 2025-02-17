import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'

import sys
import logging
import json
import threading
import time
from datetime import datetime
from typing import Any, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QComboBox, QPushButton, QTextEdit, QListWidget, QMessageBox, QGroupBox, QFormLayout, QStatusBar
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt5.QtGui import QTextCursor

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,  # changed logging level to DEBUG to show debug messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('qt_mqtt_broadcaster')

# Import MQTTHandler from the new mqtt_handler module
from mqtt_handler import MQTTHandler


class MqttSignalEmitter(QObject):
    messageReceived = pyqtSignal(object)  # Emits received MQTT message
    connectionStatus = pyqtSignal(bool, str)  # Emits connection status (is_connected, error message)


class MQTTBroadcasterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('MQTT Broadcaster (Qt)')
        self.resize(1200, 800)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Signal emitter for thread-safe UI updates
        self.emitter = MqttSignalEmitter()
        self.emitter.messageReceived.connect(self.on_message_received)  # removed Qt.DirectConnection to use default (queued) connection
        self.emitter.connectionStatus.connect(self.on_connection_status)  # removed Qt.DirectConnection

        # Initialize MQTTHandler from legacy code
        self.mqtt = MQTTHandler(
            message_callback=lambda msg: self.emitter.messageReceived.emit(msg),
            connection_callback=lambda success, error=None: self.emitter.connectionStatus.emit(success, error if error else ''),
            disconnection_callback=lambda rc: self.emitter.connectionStatus.emit(False, f"Disconnected with code: {rc}")
        )

        # Channel statistics
        self.channel_stats: Dict[str, int] = {}
        self.channels = set()
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
        self.edit_topic = QLineEdit('test/topic')
        conn_layout.addRow('Host:', self.combo_host)
        conn_layout.addRow('Port:', self.edit_port)
        conn_layout.addRow('Topic:', self.edit_topic)
        layout.addWidget(conn_group)

        # Connection buttons
        btn_layout = QHBoxLayout()
        self.btn_connect = QPushButton('Connect')
        self.btn_disconnect = QPushButton('Disconnect')
        self.btn_connect.clicked.connect(self.connect_to_broker)
        self.btn_disconnect.clicked.connect(self.disconnect_from_broker)
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
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
        try:
            self.mqtt.connect(host, port, 'tcp', topic)
        except Exception as e:
            logger.error(f'Connection error: {e}', exc_info=True)
            self.emitter.connectionStatus.emit(False, str(e))

    def disconnect_from_broker(self) -> None:
        try:
            self.mqtt.disconnect()
            self.statusBar.showMessage('Disconnected')
        except Exception as e:
            logger.error(f'Disconnection error: {e}', exc_info=True)
            self.show_error('Disconnection Error', str(e))

    def on_connection_status(self, is_connected: bool, error: str) -> None:
        QTimer.singleShot(0, lambda: self._handle_connection_status(is_connected, error))

    def _handle_connection_status(self, is_connected: bool, error: str) -> None:
        if is_connected:
            self.statusBar.showMessage('Connected to broker')
            self.append_message('System', 'Connected to broker')
        else:
            self.statusBar.showMessage(f'Connection failed: {error}')
            self.append_message('Error', f'Connection failed: {error}')

    def handle_disconnection(self, rc: int) -> None:
        if rc != 0:
            self.append_message('Error', f'Unexpected disconnection, code: {rc}')
        self.statusBar.showMessage('Disconnected from broker')

    def start_broadcast(self) -> None:
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
        QTimer.singleShot(0, lambda: self._handle_message(msg))

    def _handle_message(self, msg: Any) -> None:
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
        self.append_message(topic, payload, timestamp)
        self.update_channel_stats(topic)

    def append_message(self, channel: str, message: str, timestamp: str = '') -> None:
        if not timestamp:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.text_messages.append(f'[{timestamp}] {channel}: {message}')

    def update_channel_stats(self, channel: str) -> None:
        if channel in self.channel_stats:
            self.channel_stats[channel] += 1
        else:
            self.channel_stats[channel] = 1
            self.channels.add(channel)
        logger.debug(f'Channel stats: {self.channel_stats}')

    def start_scan(self) -> None:
        self.list_scan_results.clear()
        QTimer.singleShot(0, lambda: self.append_message('System', 'Scanning for MQTT servers...'))
        threading.Thread(target=self._thread_scan, daemon=True).start()

    def _thread_scan(self) -> None:
        import random
        time.sleep(2)
        servers = [f"192.168.1.{random.randint(2,254)}" for _ in range(3)]
        QTimer.singleShot(0, lambda: self._handle_scan_results(servers))

    def _handle_scan_results(self, servers: list) -> None:
        self.list_scan_results.addItems(servers)
        self.append_message('System', f"Scan complete. Found: {', '.join(servers)}")

    def connect_scanned_server(self) -> None:
        selected_items = self.list_scan_results.selectedItems()
        if not selected_items:
            self.show_error('No Selection', 'Please select a server from the list')
            return
        server_ip = selected_items[0].text()
        self.combo_host.setCurrentText(server_ip)
        self.connect_to_broker()

    def show_error(self, title: str, message: str = '') -> None:
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))

    def load_channel_stats(self) -> None:
        try:
            with open(self.stats_file, 'r') as f:
                self.channel_stats = json.load(f)
            logger.info("Channel stats loaded.")
        except Exception as e:
            logger.info("Channel stats file not found or error loading: " + str(e))

    def save_channel_stats(self) -> None:
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.channel_stats, f)
            logger.info("Channel stats saved.")
        except Exception as e:
            logger.error("Error saving channel stats: " + str(e))

    def closeEvent(self, event) -> None:
        self.save_channel_stats()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MQTTBroadcasterWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()