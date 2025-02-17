# MQTT Broadcaster (Qt Edition)

A powerful and user-friendly MQTT client application built with Python and Qt, designed for testing, debugging, and working with MQTT-enabled devices and services.

## Features

- **Modern Qt-based GUI**: Clean and intuitive interface with tab-based organization
- **Advanced MQTT Functionality**:
  - Connect to any MQTT broker
  - Support for QoS levels 0-1-2
  - SSL/TLS encryption support
  - Message retention control
  - Auto-reconnect capability
  - Wildcard topic subscriptions
  - Multi-threaded message broadcasting
  
- **Smart Network Features**:
  - MQTT server scanner
  - Automatic Bambu P1S printer detection
  - Support for multiple broker protocols (TCP, WebSocket)

- **Message Management**:
  - Real-time message display
  - Message filtering
  - Message history with export to CSV
  - Channel statistics tracking
  - Message counter

## Requirements

- Python 3.8 or higher
- Dependencies (automatically installed with pip):
  - PyQt6 6.4.0 or higher
  - paho-mqtt 2.0.0 or higher
  - pytest 8.3.4 (for tests)

## Installation

### From Packages (Recommended)

Download the appropriate package for your system from the [latest release](https://github.com/yourusername/Open-MQTT-Broadcaster-4/releases/latest):

- **Windows**: Download and run `mqtt-broadcaster-VERSION-win.exe`
- **macOS**: Download and mount `mqtt-broadcaster-VERSION-mac.dmg`
- **Linux**: 
  - AppImage: Download `mqtt-broadcaster-VERSION-appimage.AppImage`, make executable (`chmod +x`) and run
  - Debian/Ubuntu: Install with `sudo dpkg -i mqtt-broadcaster-VERSION-deb.deb`
  - Arch Linux: Install with `sudo pacman -U mqtt-broadcaster-VERSION-arch.pkg.tar.zst`

### From Source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Open-MQTT-Broadcaster-4.git
cd Open-MQTT-Broadcaster-4
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python qt_mqtt_broadcaster.py
```

## Usage

### Basic Operation

1. **Connect to a Broker**:
   - Enter broker details (host, port)
   - Configure optional SSL/TLS settings if needed
   - Click "Connect"

2. **Subscribe to Topics**:
   - Enter a topic pattern (supports wildcards)
   - Set QoS level
   - Click "Subscribe"

3. **Send Messages**:
   - Enter message content
   - Set number of messages and interval
   - Configure thread count for parallel sending
   - Click "Start Broadcast"

### Advanced Features

- **Server Scanner**: Use the Scanner tab to discover MQTT brokers on your network
- **SSL/TLS**: Configure secure connections in the Settings tab
- **Message Export**: Export message history to CSV for analysis
- **Filter Messages**: Use the filter field to show only relevant messages

## Development

### Project Structure

- `qt_mqtt_broadcaster.py`: Main application and GUI implementation
- `mqtt_handler.py`: MQTT client handling and connection management
- `requirements.txt`: Project dependencies
- `Unit_tests/`: Test files for the application
- `channel_stats.json`: Persistent storage for channel statistics

### Running Tests

```bash
pytest Unit_tests/
```

## Building from Source

To build packages for different platforms:

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Build for your platform:
- Windows: Creates an EXE
- macOS: Creates a DMG
- Linux: Creates AppImage and Arch package

The GitHub Actions workflow automatically builds all packages on release.

## Version History

- 3.0.8: Fixed packaging issues
  - Improved AppImage creation with proper FUSE handling
  - Enhanced package metadata for all platforms
  - Fixed packaging dependencies
- 3.0.7: Enhanced Arch Linux support
  - Added proper package metadata
  - Improved package layout
  - Added desktop integration
- 3.0.6: Fixed Arch Linux package creation
- 3.0.5: Cross-platform build improvements
- 3.0.4: Improved packaging
  - Standardized package naming across platforms
  - Added Debian package support
  - Enhanced build system reliability
  - Fixed dependencies for each platform
- 3.0.3: Multi-platform packaging support
  - Added AppImage for Linux
  - Added DMG for macOS
  - Added Arch Linux package
  - Improved build system
- 3.0.2: PyQt6 Migration
  - Updated to PyQt6
  - Fixed MQTT dependencies
  - Improved compatibility
- 3.0: Complete Qt port with enhanced features
  - Modern Qt-based GUI
  - Multi-threaded message broadcasting
  - Network scanning capabilities
  - SSL/TLS support
  - Improved error handling

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is open source and available under the MIT License.

## Support

For issues and feature requests, please use the GitHub issue tracker.