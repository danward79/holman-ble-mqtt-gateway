import asyncio
import json
import sys
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakDBusError
from paho.mqtt import client as mqtt_client

# ==============================================================================
# CONFIGURATION - UPDATE THESE VALUES FOR YOUR SETUP
# ==============================================================================
# Hardware Parameters
BLE_MAC = "XX:XX:XX:XX:XX:XX"            # Replace with your Holman Controller MAC Address

# Upstream Network & Security Parameters
MQTT_BROKER_IP = "homeassistant.local"  # IP or hostname of your MQTT Broker
MQTT_PORT = 1883                         # Default MQTT Port
MQTT_USER = "YOUR_MQTT_USERNAME"         # Replace with your MQTT username
MQTT_PASS = "YOUR_MQTT_PASSWORD"         # Replace with your MQTT password

# Radio Stability & Handling Parameters
BLE_SCAN_TIMEOUT = 7.0       # Seconds to wait for sparse advertising beacons
BLE_CONN_TIMEOUT = 10.0      # Timeout allocation for connection negotiation
BLE_MAX_ATTEMPTS = 3         # Max retries before dropping execution pipeline
BLE_RETRY_DELAY  = 2.0       # Delay between failed connection retry sweeps
BLE_COOLDOWN     = 1.2       # Cooldown window before executing next queued action
MQTT_RETRY_DELAY = 15.0      # Seconds between broker connection sweep failures

# Home Assistant Architecture Topics
DISCOVERY_TOPIC = "homeassistant/light/garden_lights/config"
COMMAND_TOPIC   = "homeassistant/light/garden_lights/set"
STATE_TOPIC     = "homeassistant/light/garden_lights/state"
STATUS_TOPIC    = "homeassistant/status"              

# BLE Handle Mappings (Vibrance WW Controller)
NOTIFY_UUID = "a876f003-7f10-4d70-b606-7df77c3eee0c"  
WRITE_UUID  = "0000f004-0000-1000-8000-00805f9b34fb"  
PING = bytearray([0x00] * 20)

# ==============================================================================
# GLOBAL RUNTIME STATE
# ==============================================================================
main_loop = None
mqtt_shared_client = None
last_known_brightness = 100 

# Asynchronous Debouncer Slots
target_level = None       
current_level = None      

# ==============================================================================
# PROTOCOL CONVERSION ENGINE
# ==============================================================================
def build_payload(percentage):
    """Translates dimming percentages into the hardware's 20-byte matrix."""
    if percentage == 0:
        return bytearray([0x00, 0x2e, 0xff, 0x00] + [0x00] * 16)
    else:
        brightness_byte = int((percentage / 100) * 255)
        return bytearray([
            0x00, 0x2e, 0x00, 0x03, 0x7f, 0x11, 0x00, 0x14, 0x1e,
            0x00, 0xff, 0x00, 0x00, 0x00, 0x00, 0x00, 0x64, 0x00,
            brightness_byte, 0x00
        ])

async def execute_ble_command(level):
    """Executes the single-shot transactional radio sequence."""
    payload = build_payload(level)
    
    for attempt in range(1, BLE_MAX_ATTEMPTS + 1):
        try:
            print(f"[BLE] Scanning to locate sleep beacon (Attempt {attempt}/{BLE_MAX_ATTEMPTS})...")
            device = await BleakScanner.find_device_by_address(BLE_MAC, timeout=BLE_SCAN_TIMEOUT)
            
            if not device:
                print(f"[BLE WARNING] Peripheral missed scan window on attempt {attempt}.")
                if attempt < BLE_MAX_ATTEMPTS:
                    await asyncio.sleep(BLE_RETRY_DELAY)
                    continue
                return False

            print("[BLE] Target located. Establishing link via native BLEDevice cache...")
            async with BleakClient(device, timeout=BLE_CONN_TIMEOUT) as client:
                print("[BLE] Link established. Executing authorization sequence...")
                await client.start_notify(NOTIFY_UUID, lambda s, d: None)
                
                await asyncio.sleep(0.3)
                await client.write_gatt_char(WRITE_UUID, PING, response=True)
                
                await asyncio.sleep(0.4)
                print(f"[BLE] Dispatching state alteration instruction ({level}%)...")
                await client.write_gatt_char(WRITE_UUID, payload, response=True)
                
                await asyncio.sleep(0.4)
                print("[BLE] Transaction complete. Hardware acknowledged successfully.")
                return True
                
        except (BleakDBusError, Exception) as e:
            print(f"[BLE WARNING] Interface friction on attempt {attempt}: {e}")
            if attempt < BLE_MAX_ATTEMPTS:
                await asyncio.sleep(BLE_RETRY_DELAY)
            else:
                print("[BLE ERROR] Maximum physical connection retries exhausted.")
                return False

# ==============================================================================
# ASYNC DEBOUNCED LOOP WORKER
# ==============================================================================
async def ble_worker_loop():
    """Continuously monitors target state, bypassing stale intermediate commands."""
    global target_level, current_level, mqtt_shared_client, last_known_brightness
    
    print("[ENGINE] Asynchronous Debounce Worker Loop fully initialized.")
    
    while True:
        if target_level is not None:
            job_level = target_level
            target_level = None 
            
            print(f"\n[WORKER] Deploying state update request: {job_level}%")
            success = await execute_ble_command(job_level)
            
            if success:
                current_level = job_level
                if job_level == 0:
                    state_data = {"state": "OFF"}
                else:
                    state_data = {"state": "ON", "brightness": job_level}
                    last_known_brightness = job_level
                    
                if mqtt_shared_client and mqtt_shared_client.is_connected():
                    mqtt_shared_client.publish(STATE_TOPIC, json.dumps(state_data), retain=True)
                    print(f"[MQTT] Confirmed state synchronized to HAOS: {state_data}")
            else:
                print("[WORKER] Target command execution failed permanently.")
                
            await asyncio.sleep(BLE_COOLDOWN)
            
        await asyncio.sleep(0.05)

def set_target_level_threadsafe(level):
    global target_level
    target_level = level

# ==============================================================================
# MQTT SYSTEM INTEGRATION
# ==============================================================================
def publish_discovery(client):
    """Deploys the JSON payload map required for Home Assistant Auto-Discovery."""
    discovery_payload = {
        "name": "Garden Lights",
        "unique_id": f"holman_vibrance_ww_{BLE_MAC.replace(':', '').lower()}",
        "schema": "json",
        "command_topic": COMMAND_TOPIC,
        "state_topic": STATE_TOPIC,
        "brightness": True,
        "brightness_scale": 100,  
        "device": {
            "identifiers": [f"holman_{BLE_MAC}"],
            "name": "Holman Garden Lights",
            "model": "Vibrance WW Controller",
            "manufacturer": "Holman"
        }
    }
    client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
    print("[MQTT] Auto-Discovery registration profile successfully sent.")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Connected & Authenticated with HAOS Broker successfully!")
        publish_discovery(client)
        client.subscribe(COMMAND_TOPIC)
        client.subscribe(STATUS_TOPIC)
    else:
        print(f"[MQTT ERROR] Authentication link failure. Code: {rc}")

def on_disconnect(client, userdata, flags, rc, properties=None):
    print(f"\n[MQTT WARNING] Disconnected from broker (Reason Code: {rc}). Standby engaged.")

def on_message(client, userdata, msg):
    global main_loop, last_known_brightness
    
    if msg.topic == STATUS_TOPIC:
        try:
            status_payload = msg.payload.decode().strip()
            if status_payload == "online":
                print("[MQTT] Home Assistant announced ONLINE. Re-syncing configurations...")
                publish_discovery(client)
        except Exception as e:
            print(f"[MQTT ERROR] Failed to interpret status stream: {e}")
        return

    try:
        payload_str = msg.payload.decode().strip()
        data = json.loads(payload_str)
        target_state = data.get("state", "OFF").upper()
        
        if target_state == "OFF":
            calculated_level = 0
        else:
            calculated_level = data.get("brightness", last_known_brightness)
            
        if main_loop:
            main_loop.call_soon_threadsafe(set_target_level_threadsafe, calculated_level)
            
    except Exception as e:
        print(f"[MQTT ERROR] Failed parsing inbound network payload: {e}")

# ==============================================================================
# ENTRYPOINT INTERFACE
# ==============================================================================
async def main():
    global main_loop, mqtt_shared_client
    main_loop = asyncio.get_running_loop()
    
    print("Initializing Holman Protected MQTT Daemon Engine...")
    asyncio.create_task(ble_worker_loop())
    
    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    client.username_pw_set(MQTT_USER, MQTT_PASS)
        
    connected = False

    while not connected:
        try:
            print(f"Connecting to broker at {MQTT_BROKER_IP}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER_IP, MQTT_PORT, keepalive=60)
            client.loop_start()  
            mqtt_shared_client = client
            connected = True
        except Exception as e:
            print(f"[MQTT INITIALIZATION WARNING] Broker unavailable: {e}")
            print(f"Retrying target network sweep in {MQTT_RETRY_DELAY}s...")
            await asyncio.sleep(MQTT_RETRY_DELAY)
        
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDaemon terminated cleanly by local system host.")
        if mqtt_shared_client:
            mqtt_shared_client.loop_stop()
