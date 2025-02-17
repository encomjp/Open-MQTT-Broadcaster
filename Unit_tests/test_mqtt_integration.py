import unittest
import time
from mqtt_handler import MQTTHandler, MQTTConfig


class DummyCallback:
    def __init__(self):
        self.msgs = []
        self.connections = []
        self.disconnections = []

    def message_callback(self, msg):
        self.msgs.append(msg)

    def connection_callback(self, success, error):
        self.connections.append((success, error))

    def disconnection_callback(self, rc):
        self.disconnections.append(rc)


class TestMQTTIntegration(unittest.TestCase):
    def setUp(self):
        self.callback = DummyCallback()
        self.handler = MQTTHandler(
            message_callback=self.callback.message_callback,
            connection_callback=self.callback.connection_callback,
            disconnection_callback=self.callback.disconnection_callback
        )

    def tearDown(self):
        try:
            self.handler.disconnect()
        except Exception:
            pass

    def test_connect_publish_disconnect(self):
        # Create config for HiveMQ public broker
        config = MQTTConfig(
            host="broker.hivemq.com",
            port=1883,
            protocol="tcp",
            topic="unittest/test"
        )
        
        # Connect using the config object
        self.handler.connect(config)

        # Wait for connection to be established
        timeout = 20  # seconds
        start = time.time()
        while not self.handler.is_connected and time.time() - start < timeout:
            time.sleep(0.5)
        self.assertTrue(self.handler.is_connected, "Failed to connect to HiveMQ broker")
        
        # Publish a test message (should not raise exception if connected)
        try:
            self.handler.publish("unittest/test", "integration test message")
        except Exception as e:
            self.fail("Publish operation raised an exception: " + str(e))
        
        # Allow some time for any subscription callbacks (if present)
        time.sleep(1)
        
        # Disconnect
        self.handler.disconnect()
        time.sleep(1)
        self.assertFalse(self.handler.is_connected, "Handler should be disconnected")
        # Check that at least one disconnection callback was invoked
        self.assertGreaterEqual(len(self.callback.disconnections), 1, "Disconnection callback was not invoked")


if __name__ == '__main__':
    unittest.main()