import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger("mqtt_handler")

class MQTTHandler:
    def __init__(self,
                 message_callback: Callable[[mqtt.MQTTMessage], None],
                 connection_callback: Callable[[bool, Optional[str]], None],
                 disconnection_callback: Callable[[int], None]) -> None:
        self.message_callback = message_callback
        self.connection_callback = connection_callback
        self.disconnection_callback = disconnection_callback

        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        self._is_connected = False
        self._sub_topic = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self, host: str, port: int, protocol: str, topic: str) -> None:
        # protocol parameter is not used as we use TCP
        self._sub_topic = topic
        try:
            self._client.connect(host, port, keepalive=60)
            self._client.loop_start()  # start background loop
        except Exception as e:
            logger.error("Failed to connect to MQTT broker", exc_info=True)
            self.connection_callback(False, str(e))

    def publish(self, topic: str, message: str) -> None:
        if not self._is_connected:
            raise RuntimeError("Not connected to MQTT broker")
        self._client.publish(topic, message)

    def disconnect(self) -> None:
        if self._is_connected:
            self._client.disconnect()
            self._client.loop_stop()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._is_connected = True
            logger.info("Connected with result code %s", rc)
            if self._sub_topic:
                client.subscribe(self._sub_topic)
            self.connection_callback(True, "")
        else:
            self._is_connected = False
            err_msg = f"Connection failed with result code {rc}"
            logger.error(err_msg)
            self.connection_callback(False, err_msg)

    def _on_message(self, client, userdata, msg):
        self.message_callback(msg)

    def _on_disconnect(self, client, userdata, rc):
        self._is_connected = False
        logger.info("Disconnected with result code %s", rc)
        self.disconnection_callback(rc) 