import unittest
from mqtt_handler import MQTTHandler


class DummyMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


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


class TestMQTTHandler(unittest.TestCase):
    def setUp(self):
        self.callback = DummyCallback()
        self.handler = MQTTHandler(
            message_callback=self.callback.message_callback,
            connection_callback=self.callback.connection_callback,
            disconnection_callback=self.callback.disconnection_callback
        )

    def test_initial_state(self):
        self.assertFalse(self.handler.is_connected, "Initial connection state should be False")

    def test_publish_without_connection(self):
        with self.assertRaises(RuntimeError):
            self.handler.publish("test/topic", "message")

    def test_on_message(self):
        dummy = DummyMessage("test/topic", b"test payload")
        self.handler._on_message(None, None, dummy)  # simulate message callback
        self.assertEqual(len(self.callback.msgs), 1)
        self.assertEqual(self.callback.msgs[0].topic, "test/topic")

    def test_connection_callback_success(self):
        # Simulate a successful connection (rc=0)
        self.handler._on_connect(None, None, None, 0)
        self.assertTrue(self.handler.is_connected)
        self.assertEqual(len(self.callback.connections), 1)
        self.assertTrue(self.callback.connections[0][0])

    def test_connection_callback_failure(self):
        # Simulate a failed connection (rc != 0)
        self.handler._on_connect(None, None, None, 1)
        self.assertFalse(self.handler.is_connected)
        self.assertEqual(len(self.callback.connections), 1)
        self.assertFalse(self.callback.connections[0][0])

    def test_disconnect_callback(self):
        # First, simulate a successful connection, then disconnect
        self.handler._on_connect(None, None, None, 0)
        self.handler._on_disconnect(None, None, {}, 0)  # Updated to match new API
        self.assertFalse(self.handler.is_connected)
        self.assertEqual(len(self.callback.disconnections), 1)


if __name__ == '__main__':
    unittest.main()