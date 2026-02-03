import asyncio
from bleak import BleakClient, BleakScanner

# --- CONFIGURATION ---
MYO_ADDRESS = "DD:31:D8:40:BC:22"
CMD_UUID = "d5060401-a904-deb9-4748-2c7f4a124842"

async def shutdown():
    print(f"Connecting to Myo at {MYO_ADDRESS} to reset sleep mode...")
    
    device = await BleakScanner.find_device_by_address(MYO_ADDRESS)
    if not device:
        print("Myo not found. It might already be asleep or out of range.")
        return

    async with BleakClient(device) as client:
        print("Connected.")
        
        # COMMAND: Set Sleep Mode (0x09) -> Normal Sleep (0x00)
        # 0x01 was "Never Sleep", 0x00 is "Normal Sleep"
        command = bytes([0x09, 0x01, 0x00])
        
        await client.write_gatt_char(CMD_UUID, command)
        print("Sleep mode reset to NORMAL.")
        print("The Myo will now power down automatically when taken off.")

if __name__ == "__main__":
    asyncio.run(shutdown())