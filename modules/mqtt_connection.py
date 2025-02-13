import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTv5
import socket
import logging

logger = logging.getLogger('mqtt_handler')

class MQTTHandler:
    def __init__(self, message_callback=None, connection_callback=None, disconnection_callback=None):
        self.client = None
        self.is_connected = False
        self.message_callback = message_callback
        self.connection_callback = connection_callback
        self.disconnection_callback = disconnection_callback
        self.topic = "#"
        self._check_connection_timer = None

    def connect(self, host, port, protocol="mqtt", topic="#"):
        """Connect to MQTT broker"""
        if self.client:
            self.disconnect()

        self.topic = topic
        
        try:
            logger.info(f"Attempting connection to {host}:{port} using {protocol}")
            connect_properties = mqtt.Properties(mqtt.PacketTypes.CONNECT)
            connect_properties.SessionExpiryInterval = 0

            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                protocol=MQTTv5,
                client_id="",
                reconnect_on_failure=True
            )
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            self.client.keepalive = 60

            if protocol == "mqtts":
                self.client.tls_set()

            # Connect with properties
            self.client.connect(host, port, properties=connect_properties)
            self.client.loop_start()  # Use paho's built-in thread for network loop
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            if self.connection_callback:
                self.connection_callback(False, str(e))
            self._cleanup_connection()
            return False

    def _cleanup_connection(self):
        """Clean up MQTT client resources"""
        if self.client:
            try:
                self.client.loop_stop()  # Stop network loop
                self.client.disconnect()
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")
            finally:
                self.client = None
                self.is_connected = False

    def disconnect(self):
        """Safely disconnect from broker"""
        self._cleanup_connection()

    def publish(self, topic, message):
        """Publish a message"""
        if not self.is_connected:
            raise ConnectionError("Not connected to broker")
        self.client.publish(topic, message)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Handle successful MQTT connection"""
        self.is_connected = reason_code == 0
        if self.is_connected:
            try:
                logger.info("Connected successfully, subscribing to topic")
                self.client.subscribe(self.topic)
                if self.connection_callback:
                    self.connection_callback(True, None)
            except Exception as e:
                logger.error(f"Error during topic subscription: {e}")
                if self.connection_callback:
                    self.connection_callback(False, str(e))
        else:
            logger.error(f"Connection failed with reason code: {reason_code}")
            if self.connection_callback:
                self.connection_callback(False, f"Failed to connect: {mqtt.connack_string(reason_code)}")

    def _on_message(self, client, userdata, message):
        if self.message_callback:
            self.message_callback(message)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"Disconnected with code {rc}")
        self.is_connected = False
        if self.disconnection_callback:
            self.disconnection_callback(rc)

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