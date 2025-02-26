import os
import sys

# Only set XCB platform on Linux
if sys.platform.startswith('linux'):
    os.environ['QT_QPA_PLATFORM'] = 'xcb'

import logging
import json
import threading
import time
import csv
import socket  # Added socket import for MQTT port scanning
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from queue import Queue
from pathlib import Path
import paho.mqtt.client as mqtt  # Added direct import of mqtt

# Change from PyQt6 to PyQt5
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QComboBox, QPushButton, QTextEdit, QListWidget, QMessageBox, QGroupBox, 
    QFormLayout, QStatusBar, QCheckBox, QSpinBox, QFileDialog
)
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt5.QtGui import QTextCursor, QColor, QIntValidator

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('qt_mqtt_broadcaster')

from mqtt_handler import MQTTHandler, MQTTConfig

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
        
        # Add connection status indicator
        self.connection_indicator = QLabel('•')
        self.connection_indicator.setStyleSheet('color: red; font-size: 24px;')
        self.connection_indicator.setToolTip('Disconnected')
        self.statusBar.addWidget(self.connection_indicator)
        
        # Message counter
        self.msg_counter_label = QLabel('Sent: 0, Received: 0')
        self.statusBar.addPermanentWidget(self.msg_counter_label)

        self.sent_count = 0
        self.received_count = 0

        def update_msg_counter():
            QTimer.singleShot(0, lambda: self.msg_counter_label.setText(f'Sent: {self.sent_count}, Received: {self.received_count}'))
        self.update_msg_counter = update_msg_counter

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
        self.subscriptions_file: str = "mqtt_subscriptions.json"
        self.load_channel_stats()

        # Add SSL settings
        self.ssl_settings = {
            'use_ssl': False,
            'ca_certs': '',
            'certfile': '',
            'keyfile': ''
        }
        
        # Add message history
        self.message_history: List[MQTTMessage] = []
        self.MAX_HISTORY = 10000

        # Add color mapping for topics
        self.topic_colors = {}
        self.next_color_index = 0
        self.color_palette = [
            QColor("#4285F4"),  # Blue
            QColor("#DB4437"),  # Red
            QColor("#F4B400"),  # Yellow
            QColor("#0F9D58"),  # Green
            QColor("#9C27B0"),  # Purple
            QColor("#FF6D00"),  # Orange
            QColor("#795548"),  # Brown
            QColor("#607D8B"),  # Gray
        ]

        # Main layout and tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_broadcaster_tab()
        self.create_scanner_tab()
        self.create_settings_tab()
        
        # Load subscriptions after UI is created
        self.load_subscriptions()

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
        
        # Add username and password fields
        self.edit_username = QLineEdit()
        self.edit_username.setPlaceholderText('Optional')
        self.edit_password = QLineEdit()
        self.edit_password.setPlaceholderText('Optional')
        self.edit_password.setEchoMode(QLineEdit.Password)
        
        self.edit_topic = QLineEdit('test/topic')
        
        self.spin_qos = QSpinBox()
        self.spin_qos.setRange(0, 2)
        self.spin_qos.setToolTip("QoS Level (0-2)")
        
        self.check_retain = QCheckBox("Retain Messages")
        self.check_auto_reconnect = QCheckBox("Auto Reconnect")
        self.check_auto_reconnect.setChecked(True)
        
        conn_layout.addRow('Host:', self.combo_host)
        conn_layout.addRow('Port:', self.edit_port)
        conn_layout.addRow('Username:', self.edit_username)
        conn_layout.addRow('Password:', self.edit_password)
        conn_layout.addRow('Topic:', self.edit_topic)
        conn_layout.addRow('QoS:', self.spin_qos)
        conn_layout.addRow('', self.check_retain)
        conn_layout.addRow('', self.check_auto_reconnect)
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

        # Wildcard subscription
        wildcard_group = QGroupBox('Topic Subscriptions')
        wildcard_layout = QFormLayout(wildcard_group)
        self.edit_wildcard = QLineEdit()
        self.edit_wildcard.setPlaceholderText('Example: sensor/#')
        
        # Add a horizontal layout for subscribe/unsubscribe buttons
        sub_btn_layout = QHBoxLayout()
        self.btn_subscribe = QPushButton('Subscribe')
        self.btn_subscribe.clicked.connect(self.subscribe_to_topic)
        self.btn_unsubscribe = QPushButton('Unsubscribe')
        self.btn_unsubscribe.clicked.connect(self.unsubscribe_from_topic)
        self.btn_unsubscribe.setEnabled(False)  # Disabled by default
        sub_btn_layout.addWidget(self.btn_subscribe)
        sub_btn_layout.addWidget(self.btn_unsubscribe)
        
        # Add a list widget to show active subscriptions
        self.subscription_list = QListWidget()
        self.subscription_list.setMaximumHeight(80)
        self.subscription_list.itemClicked.connect(self.on_subscription_selected)
        
        wildcard_layout.addRow('Topic:', self.edit_wildcard)
        wildcard_layout.addRow('', sub_btn_layout)
        wildcard_layout.addRow('Active Subscriptions:', self.subscription_list)
        layout.addWidget(wildcard_group)

        # Broadcast controls
        broadcast_group = QGroupBox('Broadcast')
        broadcast_layout = QFormLayout(broadcast_group)
        
        self.edit_broadcast_count = QLineEdit('10')
        self.edit_broadcast_count.setValidator(QIntValidator(1, 100000))
        self.edit_broadcast_count.setPlaceholderText('Number of messages to send')
        
        self.edit_broadcast_message = QTextEdit()
        self.edit_broadcast_message.setPlaceholderText('Enter message content here')
        self.edit_broadcast_message.setMaximumHeight(100)
        
        self.check_single_channel = QCheckBox('Use Single Channel')
        self.check_single_channel.setToolTip('When checked, all messages will be sent to the same channel')
        
        self.edit_interval = QLineEdit('100')
        self.edit_interval.setValidator(QIntValidator(0, 10000))
        self.edit_interval.setPlaceholderText('Delay between messages (ms)')
        
        self.check_append_count = QCheckBox('Append Message Counter')
        self.check_append_count.setChecked(False)
        
        # Replaced Fast Broadcast checkbox with thread slider
        self.spin_thread_count = QSpinBox()
        self.spin_thread_count.setRange(1, 100)
        self.spin_thread_count.setValue(1)
        self.spin_thread_count.setToolTip('Number of threads to use for broadcasting (1 = sequential)')

        broadcast_layout.addRow('Message Count:', self.edit_broadcast_count)
        broadcast_layout.addRow('Message Content:', self.edit_broadcast_message)
        broadcast_layout.addRow('Interval (ms):', self.edit_interval)
        broadcast_layout.addRow('', self.check_single_channel)
        broadcast_layout.addRow('', self.check_append_count)
        broadcast_layout.addRow('Thread Count:', self.spin_thread_count)  # Added thread slider

        self.btn_broadcast = QPushButton('Start Broadcast')
        self.btn_broadcast.clicked.connect(self.start_broadcast)
        broadcast_layout.addRow('', self.btn_broadcast)
        layout.addWidget(broadcast_group)

        # Message display area
        self.text_messages = QTextEdit()
        self.text_messages.setReadOnly(True)
        layout.addWidget(self.text_messages)

        # Export button
        self.btn_export = QPushButton('Export Messages')
        self.btn_export.clicked.connect(self.export_messages)
        layout.addWidget(self.btn_export)

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

    def create_settings_tab(self) -> None:
        """Create the settings tab for SSL/TLS configuration"""
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)

        # MQTT Protocol Version
        protocol_group = QGroupBox('MQTT Protocol')
        protocol_layout = QFormLayout(protocol_group)
        
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("MQTT v3.1.1", mqtt.MQTTv311)
        self.protocol_combo.addItem("MQTT v5", mqtt.MQTTv5)
        self.protocol_combo.setCurrentIndex(1)  # Default to MQTTv5
        self.protocol_combo.setToolTip("Some brokers may not support MQTT v5")
        
        protocol_layout.addRow('Protocol Version:', self.protocol_combo)
        layout.addWidget(protocol_group)

        # SSL settings
        ssl_group = QGroupBox('SSL/TLS Settings')
        ssl_layout = QFormLayout(ssl_group)

        self.check_use_ssl = QCheckBox('Enable SSL/TLS')
        self.check_use_ssl.stateChanged.connect(self.update_ssl_state)

        self.edit_ca_certs = QLineEdit()
        self.btn_ca_certs = QPushButton('Browse')
        self.btn_ca_certs.clicked.connect(lambda: self.browse_file('ca_certs'))
        ca_layout = QHBoxLayout()
        ca_layout.addWidget(self.edit_ca_certs)
        ca_layout.addWidget(self.btn_ca_certs)

        self.edit_certfile = QLineEdit()
        self.btn_certfile = QPushButton('Browse')
        self.btn_certfile.clicked.connect(lambda: self.browse_file('certfile'))
        cert_layout = QHBoxLayout()
        cert_layout.addWidget(self.edit_certfile)
        cert_layout.addWidget(self.btn_certfile)

        self.edit_keyfile = QLineEdit()
        self.btn_keyfile = QPushButton('Browse')
        self.btn_keyfile.clicked.connect(lambda: self.browse_file('keyfile'))
        key_layout = QHBoxLayout()
        key_layout.addWidget(self.edit_keyfile)
        key_layout.addWidget(self.btn_keyfile)

        ssl_layout.addRow('', self.check_use_ssl)
        ssl_layout.addRow('CA Certificates:', ca_layout)
        ssl_layout.addRow('Client Certificate:', cert_layout)
        ssl_layout.addRow('Client Key:', key_layout)
        
        layout.addWidget(ssl_group)
        self.tabs.addTab(self.settings_tab, 'Settings')

    def update_ssl_state(self, state: int) -> None:
        """Update SSL/TLS settings state"""
        enabled = bool(state)
        self.edit_ca_certs.setEnabled(enabled)
        self.btn_ca_certs.setEnabled(enabled)
        self.edit_certfile.setEnabled(enabled)
        self.btn_certfile.setEnabled(enabled)
        self.edit_keyfile.setEnabled(enabled)
        self.btn_keyfile.setEnabled(enabled)
        self.ssl_settings['use_ssl'] = enabled

    def browse_file(self, setting_name: str) -> None:
        """Browse for SSL/TLS certificate files"""
        file_path, _ = QFileDialog.getOpenFileName(self, f'Select {setting_name} file')
        if file_path:
            if setting_name == 'ca_certs':
                self.edit_ca_certs.setText(file_path)
            elif setting_name == 'certfile':
                self.edit_certfile.setText(file_path)
            elif setting_name == 'keyfile':
                self.edit_keyfile.setText(file_path)
            self.ssl_settings[setting_name] = file_path

    def connect_to_broker(self) -> None:
        """Connect to the specified MQTT broker with current settings"""
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
            
        # Get username and password if provided
        username = self.edit_username.text().strip() or None
        password = self.edit_password.text().strip() or None
        
        # Get selected protocol version
        mqtt_version = self.protocol_combo.currentData()

        config = MQTTConfig(
            host=host,
            port=port,
            protocol='tcp',
            topic=topic,
            qos=self.spin_qos.value(),
            retain=self.check_retain.isChecked(),
            use_ssl=self.ssl_settings['use_ssl'],
            ca_certs=self.ssl_settings['ca_certs'] or None,
            certfile=self.ssl_settings['certfile'] or None,
            keyfile=self.ssl_settings['keyfile'] or None,
            auto_reconnect=self.check_auto_reconnect.isChecked(),
            username=username,
            password=password,
            mqtt_version=mqtt_version
        )

        # Disable connect button while connecting
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText('Connecting...')
        self.statusBar.showMessage('Connecting...')
        threading.Thread(target=self._thread_connect, args=(config,), daemon=True).start()

    def _thread_connect(self, config: MQTTConfig) -> None:
        """Threaded function to connect to the MQTT broker"""
        try:
            self.mqtt.connect(config)
        except Exception as e:
            logger.error(f'Connection error: {e}', exc_info=True)
            self.emitter.connectionStatus.emit(False, str(e))

    def disconnect_from_broker(self) -> None:
        """Disconnect from the MQTT broker"""
        try:
            # Disable disconnect button while disconnecting
            self.btn_disconnect.setEnabled(False)
            self.btn_disconnect.setText('Disconnecting...')
            self.mqtt.disconnect()
            self.statusBar.showMessage('Disconnected')
            
            # Reset UI states
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText('Connect')
            self.btn_disconnect.setEnabled(False)
            self.btn_disconnect.setText('Disconnect')
            self.btn_subscribe.setEnabled(False)
            self.btn_broadcast.setEnabled(False)
            self.connection_indicator.setStyleSheet('color: red; font-size: 24px;')
            self.connection_indicator.setToolTip('Disconnected')
        except Exception as e:
            logger.error(f'Disconnection error: {e}', exc_info=True)
            self.show_error('Disconnection Error', str(e))
            # Reset button state
            self.btn_disconnect.setEnabled(True)
            self.btn_disconnect.setText('Disconnect')

    def on_connection_status(self, is_connected: bool, error: str) -> None:
        """Handle connection status updates"""
        QTimer.singleShot(0, lambda: self._handle_connection_status(is_connected, error))

    def _handle_connection_status(self, is_connected: bool, error: str) -> None:
        """Update UI based on connection status"""
        if is_connected:
            self.statusBar.showMessage('Connected to broker')
            self.connection_indicator.setStyleSheet('color: green; font-size: 24px;')
            self.connection_indicator.setToolTip('Connected')
            self.append_message('System', 'Connected to broker')
            
            # Update button states
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_subscribe.setEnabled(True)
            self.btn_broadcast.setEnabled(True)
            self.btn_connect.setText('Connect')
        else:
            self.statusBar.showMessage(f'Connection failed: {error}')
            self.connection_indicator.setStyleSheet('color: red; font-size: 24px;')
            self.connection_indicator.setToolTip(f'Disconnected: {error}' if error else 'Disconnected')
            self.append_message('Error', f'Connection failed: {error}')
            
            # Update button states
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.btn_subscribe.setEnabled(False)
            self.btn_broadcast.setEnabled(False)
            self.btn_connect.setText('Connect')

    def handle_disconnection(self, rc: int) -> None:
        """Handle unexpected disconnection"""
        if rc != 0:
            self.append_message('Error', f'Unexpected disconnection, code: {rc}')
        self.statusBar.showMessage('Disconnected from broker')
        self.connection_indicator.setStyleSheet('color: red; font-size: 24px;')
        self.connection_indicator.setToolTip('Disconnected')

    def start_broadcast(self) -> None:
        """Start broadcasting messages"""
        if not getattr(self.mqtt, 'is_connected', False):
            self.show_error('Not Connected', 'Please connect to a broker first')
            return
            
        try:
            count = int(self.edit_broadcast_count.text().strip())
            interval = int(self.edit_interval.text().strip())
        except ValueError:
            self.show_error('Invalid Input', 'Please enter valid numbers for count and interval.')
            return

        message = self.edit_broadcast_message.toPlainText().strip()
        if not message:
            self.show_error('Empty Message', 'Please enter a message to broadcast.')
            return

        threading.Thread(
            target=self._thread_broadcast, 
            args=(count, message, interval_ms), 
            daemon=True
        ).start()

    def _thread_broadcast(self, count: int, message: str, interval_ms: int) -> None:
        """Threaded function to broadcast messages"""
        total_sent = 0
        failed = 0
        use_single_channel = self.check_single_channel.isChecked()
        append_counter = self.check_append_count.isChecked()
        base_topic = self.edit_topic.text().strip()

        thread_count = self.spin_thread_count.value()
        
        if thread_count > 1:
            from concurrent.futures import ThreadPoolExecutor
            futures = []
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                for i in range(count):
                    try:
                        current_message = f"{message} ({i+1}/{count})" if append_counter else message
                        topic = base_topic if use_single_channel else f"{base_topic}/{i+1}"
                        future = executor.submit(self.mqtt.publish, topic, current_message)
                        futures.append((i, topic, current_message, future))
                    except Exception as e:
                        logger.error(f'Broadcast error: {e}', exc_info=True)
                        failed += 1
                        self.append_message('Error', f'Failed to send message {i+1}: {str(e)}')

                for i, topic, current_message, future in futures:
                    try:
                        future.result()
                        total_sent += 1
                        self.sent_count += 1
                        self.append_message('Broadcast', f'Sent to {topic}: {current_message}')
                        self.update_msg_counter()
                    except Exception as e:
                        logger.error(f'Broadcast error: {e}', exc_info=True)
                        failed += 1
                        self.append_message('Error', f'Failed to send message {i+1}: {str(e)}')
        else:
            for i in range(count):
                try:
                    current_message = f"{message} ({i+1}/{count})" if append_counter else message
                    topic = base_topic if use_single_channel else f"{base_topic}/{i+1}"
                    self.mqtt.publish(topic, current_message)
                    total_sent += 1
                    self.sent_count += 1
                    self.append_message('Broadcast', f'Sent to {topic}: {current_message}')
                    self.update_msg_counter()
                except Exception as e:
                    logger.error(f'Broadcast error: {e}', exc_info=True)
                    failed += 1
                    self.append_message('Error', f'Failed to send message {i+1}: {str(e)}')
                if interval_ms > 0:
                    time.sleep(interval_ms / 1000.0)

        self.append_message('System', f'Broadcast complete. Total: {count, Sent: {total_sent}, Failed: {failed}')

    def on_message_received(self, msg: Any) -> None:
        """Handle received MQTT messages"""
        QTimer.singleShot(0, lambda: self._handle_message(msg))

    def _handle_message(self, msg: Any) -> None:
        """Process and display received MQTT messages"""
        try:
            topic = msg.topic
            if hasattr(msg.payload, 'decode'):
                payload = msg.payload.decode()
            else:
                payload = str(msg.payload)
                
            # Try to format JSON payload for improved readability
            try:
                # Check if payload might be JSON
                if (payload.startswith('{') and payload.endswith('}')) or \
                   (payload.startswith('[') and payload.endswith(']')):
                    json_obj = json.loads(payload)
                    payload = json.dumps(json_obj, indent=2)
            except json.JSONDecodeError:
                # Not JSON, keep original payload
                pass
                
        except Exception as e:
            topic = 'Error'
            payload = f'Error decoding message: {e}'
            logger.error(f'Error processing message: {e}', exc_info=True)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mqtt_message = MQTTMessage(topic, payload, timestamp)
        self.message_queue.add_message(mqtt_message)
        
        # Add to history
        self.message_history.append(mqtt_message)
        if len(self.message_history) > self.MAX_HISTORY:
            self.message_history.pop(0)
            
        # Schedule UI update
        QTimer.singleShot(0, lambda: self.refresh_messages())
        self.update_channel_stats(topic)
        self.received_count += 1
        self.update_msg_counter()

    def append_message(self, channel: str, message: str, timestamp: str = '') -> None:
        """Append a message to the display"""
        if not timestamp:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Use QTimer to safely update text from any thread
        QTimer.singleShot(0, lambda: self.text_messages.append(f'[{timestamp}] {channel}: {message}'))

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
        """Threaded function to scan for MQTT servers using sockets"""
        from concurrent.futures import ThreadPoolExecutor
        found_servers = []
        port_to_scan = 1883
        
        # Attempt to get local network base from local IP
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            base_parts = local_ip.split('.')
            if len(base_parts) == 4:
                base = '.'.join(base_parts[:-1]) + '.'
            else:
                base = '192.168.1.'
            ips = [f"{base}{i}" for i in range(1, 255) if f"{base}{i}" != local_ip]
        except Exception as e:
            ips = [f"192.168.1.{i}" for i in range(1, 255)]
        
        def scan_ip(ip):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                result = s.connect_ex((ip, port_to_scan))
                s.close()
                if result == 0:
                    return ip
            except Exception:
                pass
            return None
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(scan_ip, ip): ip for ip in ips}
            for future in futures:
                ip_result = future.result()
                if ip_result is not None:
                    found_servers.append(ip_result)
        
        # Try to resolve Bambu P1S specifically
        try:
            bambu_ip = socket.gethostbyname('bambu-p1s.local')
            if bambu_ip not in found_servers:
                found_servers.insert(0, bambu_ip + ' (Bambu P1S)')
        except Exception:
            pass
        
        QTimer.singleShot(0, lambda: self._handle_scan_results(found_servers))

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

    def subscribe_to_topic(self) -> None:
        """Subscribe to a topic with wildcards"""
        if not self.mqtt.is_connected:
            self.show_error('Not Connected', 'Please connect to a broker first')
            return
            
        topic = self.edit_wildcard.text().strip()
        if not topic:
            self.show_error('Invalid Topic', 'Please enter a valid topic')
            return
            
        try:
            self.mqtt.subscribe(topic, qos=self.spin_qos.value())
            self.append_message('System', f'Subscribed to topic: {topic}')
            
            # Add to subscription list if not already there
            found = False
            for i in range(self.subscription_list.count()):
                if self.subscription_list.item(i).text() == topic:
                    found = True
                    break
            
            if not found:
                self.subscription_list.addItem(topic)
                
        except Exception as e:
            self.show_error('Subscribe Error', str(e))

    def unsubscribe_from_topic(self) -> None:
        """Unsubscribe from a selected topic"""
        if not self.mqtt.is_connected:
            self.show_error('Not Connected', 'Please connect to a broker first')
            return
        
        # Get selected topic from list or from the edit field
        selected_items = self.subscription_list.selectedItems()
        if selected_items:
            topic = selected_items[0].text()
        else:
            topic = self.edit_wildcard.text().strip()
            if not topic:
                self.show_error('Invalid Topic', 'Please select a topic from the list or enter a topic')
                return
        
        try:
            self.mqtt.unsubscribe(topic)
            self.append_message('System', f'Unsubscribed from topic: {topic}')
            
            # Remove from the list
            for i in range(self.subscription_list.count()):
                if self.subscription_list.item(i).text() == topic:
                    self.subscription_list.takeItem(i)
                    break
                    
            # Disable unsubscribe button if no items left
            if self.subscription_list.count() == 0:
                self.btn_unsubscribe.setEnabled(False)
                
        except Exception as e:
            self.show_error('Unsubscribe Error', str(e))

    def on_subscription_selected(self, item) -> None:
        """Handle selection of a subscription from the list"""
        if item:
            self.edit_wildcard.setText(item.text())
            self.btn_unsubscribe.setEnabled(True)
        else:
            self.btn_unsubscribe.setEnabled(False)

    def export_messages(self) -> None:
        """Export message history to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(self, 'Export Messages', '', 'CSV Files (*.csv)')
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Topic', 'Payload'])
                with self.message_queue.lock:
                    messages = list(self.message_queue.queue.queue)
                for msg in messages:
                    writer.writerow([msg.timestamp, msg.topic, msg.payload])
            self.statusBar.showMessage(f'Messages exported to {file_path}')
        except Exception as e:
            self.show_error('Export Error', str(e))

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

    def load_subscriptions(self) -> None:
        """Load saved topic subscriptions"""
        try:
            with open(self.subscriptions_file, 'r') as f:
                subscriptions = json.load(f)
                # Add loaded subscriptions to UI list
                for topic in subscriptions:
                    self.subscription_list.addItem(topic)
            logger.info("Subscriptions loaded.")
        except Exception as e:
            logger.info("Subscriptions file not found or error loading: " + str(e))

    def save_subscriptions(self) -> None:
        """Save topic subscriptions to file"""
        try:
            subscriptions = []
            for i in range(self.subscription_list.count()):
                subscriptions.append(self.subscription_list.item(i).text())
                
            with open(self.subscriptions_file, 'w') as f:
                json.dump(subscriptions, f)
            logger.info("Subscriptions saved.")
        except Exception as e:
            logger.error("Error saving subscriptions: " + str(e))

    def closeEvent(self, event) -> None:
        """Handle window close event"""
        self.save_channel_stats()
        self.save_subscriptions()
        event.accept()

    def update_message_filter(self, filter_text: str) -> None:
        """Update the message filter and refresh displayed messages"""
        self.message_filter = filter_text
        self.refresh_messages()

    def refresh_messages(self) -> None:
        """Refresh the displayed messages based on current filter"""
        self.text_messages.clear()
        messages_to_display = []
        
        with self.message_queue.lock:
            messages = list(self.message_queue.queue.queue)
            for msg in messages:
                if not self.message_filter or self.message_filter.lower() in msg.topic.lower():
                    messages_to_display.append(msg)
        
        for msg in messages_to_display:
            # Get color for this topic
            if msg.topic not in self.topic_colors:
                self.topic_colors[msg.topic] = self.color_palette[self.next_color_index % len(self.color_palette)]
                self.next_color_index += 1
            
            color = self.topic_colors[msg.topic]
            
            # Apply formatted text with color
            self.text_messages.setTextColor(color)
            self.text_messages.append(f'[{msg.timestamp}] {msg.topic}:')
            self.text_messages.setTextColor(QColor("black"))  # Reset to default for payload
            self.text_messages.insertPlainText(f' {msg.payload}\n')

    def clear_messages(self) -> None:
        """Clear all displayed messages"""
        self.text_messages.clear()
        with self.message_queue.lock:
            self.message_queue.queue.queue.clear()
        self.message_history.clear()


def main() -> None:
    """Main function to start the application"""
    app = QApplication(sys.argv)
    window = MQTTBroadcasterWindow()
    window.show()
    sys.exit(app.exec_())  # Changed from app.exec() to app.exec_() for PyQt5


if __name__ == '__main__':
    main()