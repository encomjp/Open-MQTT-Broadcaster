import paho.mqtt.client as mqtt
from typing import Optional, Callable, Any, Dict
import logging
import ssl
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MQTTConfig:
    """Configuration for MQTT connection"""
    host: str
    port: int
    protocol: str
    topic: str
    qos: int = 0
    retain: bool = False
    use_ssl: bool = False
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auto_reconnect: bool = True
    reconnect_delay: int = 5

class MQTTHandler:
    """Handles MQTT client connections and message handling"""
    
    def __init__(self, message_callback: Callable, connection_callback: Callable, disconnection_callback: Callable):
        """Initialize MQTT handler with callbacks"""
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.message_callback = message_callback
        self.connection_callback = connection_callback
        self.disconnection_callback = disconnection_callback
        self.config: Optional[MQTTConfig] = None
        self.is_connected: bool = False
        self.wildcard_subscriptions: Dict[str, int] = {}  # topic: QoS

    def configure(self, config: MQTTConfig) -> None:
        """Configure MQTT client settings"""
        self.config = config
        
        if config.username and config.password:
            self.client.username_pw_set(config.username, config.password)
            
        if config.use_ssl:
            context = ssl.create_default_context()
            if config.ca_certs:
                context.load_verify_locations(config.ca_certs)
            if config.certfile and config.keyfile:
                context.load_cert_chain(config.certfile, config.keyfile)
            self.client.tls_set_context(context)
            
        if config.auto_reconnect:
            self.client.reconnect_delay_set(min_delay=1, max_delay=config.reconnect_delay)

    def connect(self, config: Optional[MQTTConfig] = None) -> None:
        """Connect to MQTT broker using current or new configuration"""
        if config:
            self.configure(config)
        elif not self.config:
            raise ValueError("No configuration provided")
            
        try:
            if self.config.protocol == 'ws':
                self.client.ws_set_options(path="/mqtt")
            self.client.connect(self.config.host, self.config.port, keepalive=60)
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
            self.wildcard_subscriptions.clear()
        except Exception as e:
            logger.error(f"Disconnection error: {e}")
            raise

    def publish(self, topic: str, payload: str, qos: Optional[int] = None, retain: Optional[bool] = None) -> None:
        """Publish message to topic with optional QoS and retain settings"""
        if not self.is_connected:
            raise RuntimeError("Not connected to broker")
            
        try:
            effective_qos = qos if qos is not None else (self.config.qos if self.config else 0)
            effective_retain = retain if retain is not None else (self.config.retain if self.config else False)
            
            self.client.publish(
                topic, 
                payload, 
                qos=effective_qos,
                retain=effective_retain
            )
        except Exception as e:
            logger.error(f"Publish error: {e}")
            raise

    def subscribe(self, topic: str, qos: int = 0) -> None:
        """Subscribe to a topic with optional wildcard support"""
        if not self.is_connected:
            raise RuntimeError("Not connected to broker")
            
        try:
            self.client.subscribe(topic, qos)
            self.wildcard_subscriptions[topic] = qos
            logger.info(f"Subscribed to topic: {topic} with QoS: {qos}")
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            raise

    def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic"""
        if not self.is_connected:
            raise RuntimeError("Not connected to broker")
            
        try:
            self.client.unsubscribe(topic)
            self.wildcard_subscriptions.pop(topic, None)
            logger.info(f"Unsubscribed from topic: {topic}")
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            raise

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, reason_code: int, properties: Any = None) -> None:
        """Handle connection callback"""
        if reason_code == 0:
            self.is_connected = True
            # Resubscribe to all previous topics
            for topic, qos in self.wildcard_subscriptions.items():
                client.subscribe(topic, qos)
            if self.config and self.config.topic:
                client.subscribe(self.config.topic, self.config.qos)
            self.connection_callback(True, '')
        else:
            error = mqtt.error_string(reason_code)
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
        if rc != 0 and self.config and self.config.auto_reconnect:
            logger.info("Attempting to reconnect...")
        self.disconnection_callback(rc)