import asyncio
import sys
from bleak import BleakClient, BleakScanner

# Default values - Update or pass as CLI arguments
BLE_MAC = "XX:XX:XX:XX:XX:XX"  
NOTIFY_UUID = "a876f003-7f10-4d70-b606-7df77c3eee0c"  
WRITE_UUID  = "0000f004-0000-1000-8000-00805f9b34fb"  
PING = bytearray([0x00] * 20)

def build_payload(percentage):
    if percentage == 0:
        return bytearray([0x00, 0x2e, 0xff, 0x00] + [0x00] * 16)
    else:
        brightness_byte = int((percentage / 100) * 255)
        return bytearray([
            0x00, 0x2e, 0x00, 0x03, 0x7f, 0x11, 0x00, 0x14, 0x1e,
            0x00, 0xff, 0x00, 0x00, 0x00, 0x00, 0x00, 0x64, 0x00,
            brightness_byte, 0x00
        ])

async def send_command(mac, level):
    print(f"Scanning for {mac}...")
    device = await BleakScanner.find_device_by_address(mac, timeout=8.0)
    if not device:
        print("Device not found on the airwaves!")
        return

    print("Connecting...")
    async with BleakClient(device, timeout=10.0) as client:
        print("Connected. Authenticating...")
        await client.start_notify(NOTIFY_UUID, lambda s, d: None)
        await asyncio.sleep(0.3)
        await client.write_gatt_char(WRITE_UUID, PING, response=True)
        await asyncio.sleep(0.4)
        
        print(f"Sending brightness ({level}%)...")
        payload = build_payload(level)
        await client.write_gatt_char(WRITE_UUID, payload, response=True)
        await asyncio.sleep(0.4)
        print("Command executed successfully!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python holman_direct_control.py <MAC_ADDRESS> <BRIGHTNESS_0_TO_100>")
        print("Example: python holman_direct_control.py F3:61:AC:E8:BB:78 50")
        sys.exit(1)
        
    target_mac = sys.argv[1]
    brightness = int(sys.argv[2])
    
    asyncio.run(send_command(target_mac, brightness))
