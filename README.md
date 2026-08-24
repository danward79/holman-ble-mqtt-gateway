# Holman iGardener BLE-to-MQTT Gateway

Reverse-engineered Bluetooth Low Energy (BLE) to MQTT integration for the **Holman Vibrance Warm White Garden Light Controller** (`Vibrance_WW`), designed for **Home Assistant**.

This daemon acts as a persistent bridge between your Home Assistant instance and outdoor Holman Bluetooth lights. It translates Home Assistant light entity commands into the proprietary 20-byte binary protocol expected by the physical hardware.

---

## Key Features

* **Home Assistant Auto-Discovery:** Automatically registers the light entity with Home Assistant on boot via MQTT discovery topics.
* **Asynchronous Debouncing:** Bypasses intermediate lag states when adjusting brightness sliders, ensuring only the final target state is sent to the physical radio.
* **Ephemeral Connection Resilience:** Specifically engineered to handle the controller's aggressive auto-disconnect power-saving behavior.
* **Auto-Healing Service:** Handles network drops, Home Assistant reboots, and Linux Bluetooth stack restarts gracefully.
* **Diagnostic & CLI Tooling:** Includes a passive sniffer to discover hardware and a direct command-line control tool for standalone testing.

---

## Hardware Compatibility

| Parameter | Device Info |
| :--- | :--- |
| **Manufacturer** | Holman Industries |
| **Target Controller** | Vibrance Warm White (WW) Garden Light Controller |
| **Protocol** | Bluetooth Low Energy (BLE) |
| **Manufacturer ID** | `0x0374` (`884`) |
| **Write Characteristic** | `0000f004-0000-1000-8000-00805f9b34fb` (Handle `0x0012`) |
| **Notify Characteristic** | `a876f003-7f10-4d70-b606-7df77c3eee0c` (Handle `0x000f`) |

---

## Protocol Specification

The Holman Vibrance WW controller utilizes a 20-byte payload structure written over GATT characteristic `0000f004-0000-1000-8000-00805f9b34fb` with write-response enabled (`response=True`).

### Connection Handshake
Before sending state changes, notifications must be subscribed on `a876f003-7f10-4d70-b606-7df77c3eee0c`. A 20-byte zero-array authorization frame must then be transmitted:

```text
Handshake Frame: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

### State & Dimming Payloads

#### 1. OFF Payload (20 Bytes)
```text
00 2e ff 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

#### 2. ON / Dimming Payload (20 Bytes Detailed Byte Map)

Brightness is represented as an 8-bit unsigned integer (`0x00` to `0xFF`) scaled from percentage values (`0%` to `100%`) at **Byte 18**:

$$\text{Brightness Byte} = \left\lfloor \frac{\text{Percentage}}{100} \times 255 \right\rfloor$$

| Byte Index | Hex Value (Default) | Function / Description |
| :--- | :--- | :--- |
| `[00 - 01]` | `00 2e` | Frame Header |
| `[02]` | `00` | Scene ID |
| `[03]` | `03` | Schedule Enable Flags (`Bit 0`: Start Time Enable, `Bit 1`: Stop Time Enable. `0x03` = both active) |
| `[04]` | `7f` | Active Days of Week bitmask (`0x7F` = `01111111` = All 7 days) |
| `[05 - 06]` | `11 00` | Schedule Start Time |
| `[07 - 08]` | `14 1e` | Schedule Stop Time |
| `[09]` | `00` | Reserved / Unknown |
| `[10 - 15]` | `ff 00 00 00 00 00` | Payload Padding Block |
| `[16 - 17]` | `64 00` | Fixed Scaling Factor |
| `[18]` | `[0x00 - 0xFF]` | **Target Brightness Value** (`0` to `255`) |
| `[19]` | `00` | Frame Tail |

* **Example (50% Brightness / 127 Dec / `0x7F`):**
  `00 2e 00 03 7f 11 00 14 1e 00 ff 00 00 00 00 00 64 00 7f 00`
* **Example (100% Brightness / 255 Dec / `0xFF`):**
  `00 2e 00 03 7f 11 00 14 1e 00 ff 00 00 00 00 00 64 00 ff 00`

---

## Repository Structure

```text
holman-ble-mqtt-gateway/
├── holman_mqtt_daemon.py       # Main MQTT daemon service
├── holman-mqtt.service         # Systemd service unit template
├── README.md                   # Documentation
├── LICENSE                     # MIT License
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git exclusion rules
└── tools/
    ├── holman_pure_sniffer.py  # Passive BLE sniffer utility
    └── holman_direct_control.py# Command-line direct control tool
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
pip install -r requirements.txt
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

## Diagnostic & Testing Tools

### Passive BLE Sniffer
To discover your controller's MAC address or verify airwave broadcasts:

```bash
python tools/holman_pure_sniffer.py
```

### Direct Command-Line Control
To test light control directly via BLE (bypassing MQTT):

```bash
# Syntax: python tools/holman_direct_control.py <MAC_ADDRESS> <BRIGHTNESS_0_TO_100>
python tools/holman_direct_control.py F3:61:AC:E8:BB:78 50
```
