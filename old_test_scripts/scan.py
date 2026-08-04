import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning for 10 seconds... Make sure your Brymen BT is FLASHING!")
    devices = await BleakScanner.discover(timeout=10)
    print("\n--- Scan Results ---")
    for device in devices:
        print(f"Name: {device.name} | Address: {device.address}")
    print("--- Scan Complete ---")

asyncio.run(main())