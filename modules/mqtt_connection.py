import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTv5
import socket
import logging
import threading

logger = logging.getLogger('mqtt_handler')

class MQTTHandler:
    def __init__(self, message_callback=None, connection_callback=None, disconnection_callback=None):
        self.client = None
        self.is_connected = False
        self.topic = "#"
        self.message_callback = message_callback
        self.connection_callback = connection_callback
        self.disconnection_callback = disconnection_callback
        self._check_connection_timer = None
        self._connection_timeout_occurred = False

    def connect(self, host, port, protocol="mqtt", topic="#"):
        """Connect to MQTT broker with timeout"""
        try:
            self._connection_timeout_occurred = False
            if self._check_connection_timer is not None:
                self._check_connection_timer.cancel()
                self._check_connection_timer = None
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            # Set connection timeout
            self.client.connect_timeout = 10.0  # 10 seconds timeout
            self.client.socket_timeout = 10.0

            # Connect to broker
            self.client.connect(host, port)
            self.topic = topic
            self.client.subscribe(topic)
            self.client.loop_start()
            self._check_connection_timer = threading.Timer(10.0, self._timeout_callback)
            self._check_connection_timer.start()
        except Exception as e:
            if self._check_connection_timer is not None:
                self._check_connection_timer.cancel()
                self._check_connection_timer = None
            logger.error(f"Connection failed: {e}")
            if self.connection_callback:
                self.connection_callback(False, str(e))
            raise

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
            finally:
                self.is_connected = False
                self.client = None

    def publish(self, topic, message):
        """Publish message to topic"""
        if not self.is_connected:
            raise Exception("Not connected to broker")
        self.client.publish(topic, message)

    def _on_connect(self, client, userdata, flags, rc):
        """Handle connection callback"""
        if self._check_connection_timer is not None:
            self._check_connection_timer.cancel()
            self._check_connection_timer = None
        if self._connection_timeout_occurred:
            return
        if rc == 0:
            self.is_connected = True
            if self.connection_callback:
                self.connection_callback(True)
        else:
            error_message = f"Connection failed with code {rc}"
            if self.connection_callback:
                self.connection_callback(False, error_message)

    def _on_message(self, client, userdata, message):
        """Handle message callback"""
        if self.message_callback:
            self.message_callback(message)

    def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection"""
        self.is_connected = False
        if self.disconnection_callback:
            self.disconnection_callback(rc)
        if self._check_connection_timer is not None:
            self._check_connection_timer.cancel()
            self._check_connection_timer = None

    def _timeout_callback(self):
        if self._connection_timeout_occurred:
            return
        if not self.is_connected:
            self._connection_timeout_occurred = True
            logger.error("Connection timeout reached, disconnecting")
            if self.connection_callback:
                self.connection_callback(False, "Connection timeout reached")
            self.disconnect()

    @staticmethod
    def auto_detect_connection(default_host="10.16.1.246"):
        """Auto-detect MQTT broker with timeout"""
        logger.info("Attempting auto-detection of MQTT broker")
        for port in (1883, 8883):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(2.0)  # 2 second timeout for each port attempt
                    logger.debug(f"Trying {default_host}:{port}")
                    result = sock.connect_ex((default_host, port))
                    if result == 0:
                        logger.info(f"Found MQTT service on port {port}")
                        return default_host, port, "mqtt" if port == 1883 else "mqtts"
            except socket.timeout:
                logger.debug(f"Timeout on port {port}")
                continue
            except Exception as e:
                logger.debug(f"Error checking port {port}: {e}")
                continue
        raise Exception("Auto-detection failed: No MQTT service found (timeout)")

    def __del__(self):
        """Ensure cleanup on deletion"""
        self.disconnect()