import paho.mqtt.client as mqtt
from typing import Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)

class MQTTHandler:
    """Handles MQTT client connections and message handling"""
    
    def __init__(self, message_callback: Callable, connection_callback: Callable, disconnection_callback: Callable):
        """
        Initialize MQTT handler with callbacks
        
        Args:
            message_callback: Called when a message is received
            connection_callback: Called on connection status changes
            disconnection_callback: Called when disconnected
        """
        # Use MQTT v5 protocol
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.message_callback = message_callback
        self.connection_callback = connection_callback
        self.disconnection_callback = disconnection_callback
        self.topic: Optional[str] = None
        self.is_connected: bool = False

    def connect(self, host: str, port: int, protocol: str, topic: str) -> None:
        """
        Connect to MQTT broker
        
        Args:
            host: Broker hostname
            port: Broker port
            protocol: Connection protocol (tcp/ws)
            topic: Topic to subscribe to
        """
        try:
            self.topic = topic
            if protocol == 'ws':
                self.client.ws_set_options(path="/mqtt")
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.connection_callback(False, str(e))
            raise

    def disconnect(self) -> None:
        """Disconnect from MQTT broker"""
        try:
            self.client.disconnect()
            self.client.loop_stop()
            self.is_connected = False
        except Exception as e:
            logger.error(f"Disconnection error: {e}")
            raise

    def publish(self, topic: str, payload: str) -> None:
        """
        Publish message to topic
        
        Args:
            topic: Topic to publish to
            payload: Message payload
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to broker")
        try:
            self.client.publish(topic, payload, qos=1)
        except Exception as e:
            logger.error(f"Publish error: {e}")
            raise

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int, properties: Any = None) -> None:
        """Handle connection callback"""
        if rc == 0:
            self.is_connected = True
            if self.topic:
                client.subscribe(self.topic)
            self.connection_callback(True, '')
        else:
            error = mqtt.error_string(rc)
            logger.error(f"Connection failed: {error}")
            self.connection_callback(False, error)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        """Handle received message"""
        try:
            self.message_callback(message)
        except Exception as e:
            logger.error(f"Message handling error: {e}")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int, properties: Any = None) -> None:
        """Handle disconnection"""
        self.is_connected = False
        self.disconnection_callback(rc)