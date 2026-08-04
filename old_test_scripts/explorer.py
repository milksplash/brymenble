import asyncio
from bleak import BleakClient

async def main():
    address = input("Enter your Brymen address: ").strip()
    if not address:
        return

    print(f"\nConnecting to {address}...")
    async with BleakClient(address, mtu=185) as client:
        print(f"Connected: {client.is_connected}")
        print(f"MTU: {client.mtu_size}")

        print("\n--- ALL SERVICES & CHARACTERISTICS ---")
        for service in client.services:
            print(f"\nService: {service.uuid}")
            for char in service.characteristics:
                print(f"  -> Characteristic: {char.uuid} | Properties: {char.properties}")
        print("\n--- END ---")

if __name__ == "__main__":
    asyncio.run(main())