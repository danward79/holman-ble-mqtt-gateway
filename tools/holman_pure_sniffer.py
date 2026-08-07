import asyncio
from bleak import BleakScanner

HOLMAN_MANUFACTURER_ID = 884  # 0x0374 in decimal

def detection_callback(device, advertisement_data):
    # Check if manufacturer data is present
    if advertisement_data.manufacturer_data:
        for mfg_id, data in advertisement_data.manufacturer_data.items():
            if mfg_id == HOLMAN_MANUFACTURER_ID:
                print(f"\n[DISCOVERED HOLMAN DEVICE]")
                print(f"  Name: {device.name or 'Unknown'}")
                print(f"  MAC Address: {device.address}")
                print(f"  RSSI (Signal Strength): {advertisement_data.rssi} dBm")
                print(f"  Raw Hex Data: {data.hex()}")

async def main():
    print("=" * 60)
    print("Holman BLE Passive Sniffer")
    print("Scanning for devices broadcasting Manufacturer ID 884 (0x0374)...")
    print("Press Ctrl+C to stop scanning.")
    print("=" * 60)

    scanner = BleakScanner(detection_callback)
    await scanner.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await scanner.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSniffer stopped cleanly.")
