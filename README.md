# Open MQTT Broadcaster

Open MQTT Broadcaster is a Python-based desktop application built using Tkinter that enables you to connect to an MQTT broker, receive messages, and broadcast messages to multiple channels. It is designed to be responsive and performant, making use of asynchronous UI updates and advanced configurations for broadcasting large numbers of messages.

## Features

- **MQTT Connection Management**: Connect to an MQTT broker with either auto-detection or manual configuration. Easily disconnect and reconnect as needed.
- **Message Reception and Display**: Receive messages and display them in real time. The UI uses asynchronous and batched updates to ensure smooth performance even with high volumes of messages.
- **Message Broadcasting**: Send messages to one or more channels. Broadcasts are handled via multiple worker threads to ensure fast and efficient message dissemination.
- **Advanced Options**: Configure worker threads, refresh interval (delay between UI update batches), and cached messages limit directly from the GUI to customize performance according to your needs.
- **Channel Management**: Automatically show channels and update channel statuses (e.g., online/offline) based on message activity.
- **Statistics Tracking**: Maintain and persist statistics such as the number of messages received and sent per channel.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/Open-MQTT-Broadcaster.git
   cd Open-MQTT-Broadcaster
   ```

2. **Set Up a Python Virtual Environment** (Optional but recommended)

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies**

   All dependencies are listed in the `requirements.txt` file. Install them with:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the Application**

   Run the client script to launch the MQTT Broadcaster GUI:

   ```bash
   python3 open-mqtt-broadcaster-client.py
   ```

2. **Connect to an MQTT Broker**

   - You can configure the connection manually by providing the host, port, protocol, and topic.
   - Alternatively, if your setup supports it, use the auto-detection feature.

3. **Broadcast Messages**

   - Enter your message template.
   - Choose target channels (either selected channels or all channels).
   - Set the number of messages, delay, and advanced options as needed.
   - Click on "Broadcast Messages" to start broadcasting.

4. **Advanced Options**

   In the Advanced Options section of the broadcast controls, you can customize:
   - **Worker Threads**: Number of concurrent threads handling message sending.
   - **Refresh Interval (ms)**: Delay between UI update batches.
   - **Cached Messages Limit**: Maximum number of messages retained in the GUI before older messages are trimmed.
   
   Click the "Apply" button after changing these settings.

## Project Structure

- **gui/**: Contains all Tkinter GUI components (main windows, control panels, message displays, etc.).
- **config/**: Contains theme configurations and styling information.
- **utils/**: Contains utility modules including the MQTT handler.
- **open-mqtt-broadcaster-client.py**: Entry point to launch the application.

## Contributions

Contributions and suggestions are welcome! Feel free to fork the project and submit pull requests.

## License

This project is open source and available under the MIT License. See the [LICENSE](LICENSE) file for more details. 