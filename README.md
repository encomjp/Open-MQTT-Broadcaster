# Open MQTT Broadcaster

Open MQTT Broadcaster is a Python-based desktop application built using Tkinter. It enables you to connect to an MQTT broker, receive messages, and broadcast messages to multiple channels. The app has been updated with a modern dark theme and advanced network scanning capabilities for detecting MQTT servers on your local network.

## Features

- **MQTT Connection Management**: Manually configure or auto-detect MQTT brokers. Easily connect, disconnect, and reconnect as needed.
- **Modern Dark UI**: A refreshed, modern dark theme with improved widget styles and layout for a sleek user experience.
- **Message Reception and Display**: Receive messages and display them in real time with asynchronous and batched UI updates for smooth performance even with high message volumes.
- **Message Broadcasting**: Send messages to one or more channels. Broadcasting is handled via multiple worker threads to ensure rapid and efficient message delivery.
- **Advanced Options**: Customize worker threads, UI refresh intervals, and message caching limits directly via the GUI.
- **MQTT Scanner**: Scan your local network for MQTT servers using the python-nmap library. The scanner detects services on ports 1883 and 8883 (with support for non-responding devices using the -Pn flag) and allows you to directly connect to scanned servers.
- **Statistics Tracking**: Automatically track and persist statistics such as the number of messages received and sent per channel.
- **Modular Design**: The tabbed interface (via ttk.Notebook) supports easy integration of new modules and functionalities, including the MQTT Scanner and future extensions.

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

   All dependencies are listed in the `requirements.txt` file. In addition to the standard libraries, ensure that the `python-nmap` module is installed:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the Application**

   Launch the MQTT Broadcaster GUI with:

   ```bash
   python3 open-mqtt-broadcaster-client.py
   ```

2. **Connect to an MQTT Broker**

   - Use the connection tab to manually enter broker details (host, port, protocol, and topic) or rely on auto-detection if available.
   - Alternatively, use the MQTT Scanner to find MQTT servers available on your local network.

3. **Scan for MQTT Servers**

   - Navigate to the MQTT Scanner tab and click "Scan for MQTT Servers". The application uses the python-nmap library to probe your local /24 network for MQTT services on ports 1883 and 8883.
   - Found servers are listed in the scanner; you can select any and click "Connect to Selected Server" to automatically populate connection fields in the broadcaster tab.

4. **Broadcast Messages**

   - Enter your message template and select the target channels (either specific channels or all channels).
   - Adjust settings such as the number of messages, delay between messages, and any advanced options.
   - Click "Broadcast Messages" to begin the broadcast.

## Project Structure

- **gui/**: Contains all Tkinter GUI components, including the modular tabbed interface allowing for features like the MQTT Scanner alongside traditional broadcasting tools.
- **config/**: Holds theme configurations and styling information for the modern dark UI.
- **modules/**: Contains utility modules including MQTT connection handling and scanning integrations.
- **open-mqtt-broadcaster-client.py**: Main entry point to launch the application.

## Contributions

Contributions and suggestions are welcome! Feel free to fork the project and submit pull requests.

## License

This project is open source and available under the MIT License. See the [LICENSE](LICENSE) file for more details. 