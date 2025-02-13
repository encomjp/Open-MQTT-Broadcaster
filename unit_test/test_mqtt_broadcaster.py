import unittest
from gui.main_window import MQTTBroadcaster
import tkinter as tk

class TestMQTTBroadcaster(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = MQTTBroadcaster(self.root)

    def tearDown(self):
        self.root.destroy()

    def test_initialization(self):
        self.assertIsNotNone(self.app)
        self.assertEqual(self.app.root.title(), "MQTT Broadcaster")

if __name__ == '__main__':
    unittest.main() 