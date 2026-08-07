# Holman iGardener BLE-to-MQTT Gateway

Reverse-engineered Bluetooth Low Energy (BLE) to MQTT integration for the **Holman Vibrance Warm White Garden Light Controller** (`Vibrance_WW`), designed for **Home Assistant**.

This daemon acts as a persistent bridge between your Home Assistant instance and outdoor Holman Bluetooth lights. It translates Home Assistant light entity commands into the proprietary 20-byte binary protocol expected by the physical hardware.

---

## Key Features

* **Home Assistant Auto-Discovery:** Automatically registers the light entity with Home Assistant on boot via MQTT discovery topics.
* **Asynchronous Debouncing:** Bypasses intermediate lag states when adjusting brightness sliders, ensuring only the final target state is sent to the physical radio.
* **Ephemeral Connection Resilience:** Specifically engineered to handle the controller's aggressive auto-disconnect power-saving behavior.
* **Auto-Healing Service:** Handles network drops, Home Assistant reboots, and Linux Bluetooth stack restarts gracefully.
* **Diagnostic Tooling:** Includes a standalone passive sniffer to discover hardware and verify signal strength without needing MQTT.

---

## Hardware Compatibility

| Parameter | Device Info |
| :--- | :--- |
| **Manufacturer** | Holman Industries |
| **Target Controller** | Vibrance Warm White (WW) Garden Light Controller |
| **Protocol** | Bluetooth Low Energy (BLE) |
| **Manufacturer ID** | `0x0374` (`884`) |
| **Handshake GATT Handle** | `0x0012` (`0000f004-0000-1000-8000-00805f9b34fb`) |
| **Notify GATT Handle** | `0x000f` (`a876f003-7f10-4d70-b606-7df77c3eee0c`) |

---

## Repository Structure

```text
holman-ble-mqtt-gateway/
├── holman_mqtt_daemon.py    # Main MQTT daemon service
├── holman-mqtt.service      # Systemd service unit template
├── README.md                # Documentation
├── .gitignore               # Git exclusion rules
└── tools/
    └── holman_pure_sniffer.py # Diagnostic BLE sniffer utility
```

---

## Prerequisites

Ensure your system has an active Bluetooth adapter (`hci0`) and the required system utilities installed:

```bash
sudo apt update
sudo apt install avahi-daemon libnss-mdns python3-pip git
```

Install the Python dependencies:

```bash
pip install bleak paho-mqtt
```

---

## Configuration

Before running the daemon, update the configuration block at the top of `holman_mqtt_daemon.py`:

| Parameter | Default / Example | Description |
| :--- | :--- | :--- |
| `BLE_MAC` | `"F3:61:AC:E8:BB:78"` | Physical Bluetooth MAC address of your Holman Controller |
| `MQTT_BROKER_IP` | `"homeassistant.local"` | IP or hostname of your MQTT Broker |
| `MQTT_PORT` | `1883` | MQTT Broker port |
| `MQTT_USER` | `"mqtt-terminal"` | Username configured in your MQTT Broker |
| `MQTT_PASS` | `"YOUR_PASSWORD"` | Password for your MQTT user |

---

## Installation & Deployment

### 1. Clone the Repository
```bash
git clone [https://github.com/danward79/holman-ble-mqtt-gateway.git](https://github.com/danward79/holman-ble-mqtt-gateway.git)
cd holman-ble-mqtt-gateway
```

### 2. Test Execution
Run the script manually to confirm connection to both the MQTT broker and the lights:

```bash
python holman_mqtt_daemon.py
```

### 3. Deploy as a Systemd Background Service
To ensure the daemon runs on boot and automatically restarts on failures, copy the included service configuration:

```bash
sudo cp holman-mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable holman-mqtt.service
sudo systemctl start holman-mqtt.service
```

### 4. Monitor Logs
Check the live service logs to monitor state changes and diagnostic streams:

```bash
sudo journalctl -u holman-mqtt.service -f
```

---

## Diagnostic Tools

If you need to discover your controller's MAC address or test BLE signal reception before configuring MQTT, run the provided sniffer tool:

```bash
python tools/holman_pure_sniffer.py
```

This utility listens passively for BLE advertisement packets containing Holman's Manufacturer ID (`884`) and prints the MAC address, signal strength (RSSI), and raw broadcast payload.
