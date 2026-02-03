import asyncio
import struct
import time
import pyautogui
import keyboard
from bleak import BleakClient, BleakScanner

# --- CONFIGURATION ---
MYO_ADDRESS = "DD:31:D8:40:BC:22"

# SENSITIVITY
JUMP_THRESHOLD = 40    # Hit this spike to CLICK
RESET_THRESHOLD = 20   # Must drop below this to reset (Schmitt Trigger)
REFRACTORY_PERIOD = 0.3 # 100ms hard limit between clicks
HISTORY_SIZE = 40      # Baseline smoothing window

# --- UUIDS ---
CMD_UUID = "d5060401-a904-deb9-4748-2c7f4a124842"
EMG_DATA_UUID = "d5060105-a904-deb9-4748-2c7f4a124842"

class FlappyController:
    def __init__(self):
        self.history = [0] * HISTORY_SIZE
        self.last_click_time = 0
        self.is_holding_flex = False 

    def process_emg(self, sender, data):
        # 1. Unpack Raw Data (2 samples per packet)
        # Raw mode sends 16 signed bytes (-128 to 127)
        try:
            raw_values = struct.unpack('<16b', data[:16])
            sample1 = raw_values[:8]  # Time T
            sample2 = raw_values[8:]  # Time T+5ms
            
            # Sum activity of both samples
            activity1 = sum([abs(x) for x in sample1])
            activity2 = sum([abs(x) for x in sample2])
            
            # Average them for a smoother 100Hz signal
            activity = (activity1 + activity2) / 2
            
        except Exception:
            return

        # 2. Update Baseline
        self.history.pop(0)
        self.history.append(activity)
        baseline = sum(self.history) / len(self.history)
        
        # 3. Calculate Spike
        spike = activity - baseline

        # 4. Logic: Refractory + Threshold + Reset
        current_time = time.time()
        time_since_last_click = current_time - self.last_click_time
        
        # Only click if:
        # A) We crossed the threshold
        # B) We are NOT currently holding the flex (Schmitt trigger)
        # C) We waited at least 100ms since the last click (Refractory)
        if spike > JUMP_THRESHOLD and not self.is_holding_flex:
            if time_since_last_click > REFRACTORY_PERIOD:
                self.trigger_jump(spike)
                self.last_click_time = current_time
                self.is_holding_flex = True 
            
        elif spike < RESET_THRESHOLD:
            self.is_holding_flex = False # Unlock

        # 5. Visuals
        self.print_status(baseline, spike, time_since_last_click)

    def trigger_jump(self, spike):
        pyautogui.click()  # LEFT CLICK
        # Visual feedback for the jump
        print(f"\n*** CLICK! (Spike: {int(spike)}) ***")

    def print_status(self, base, spike, delta):
        # Visual Bar Graph
        bar_len = int(spike / 2)
        bar = '█' * max(0, bar_len)
        
        # Show "COOL" if in refractory period, "RDY" if ready
        status = "COOLDOWN" if delta < REFRACTORY_PERIOD else "READY   "
        if self.is_holding_flex: status = "HOLDING "
            
        print(f"[{status}] Base:{int(base):3} | Spike:{int(spike):3} | {bar:<20}", end="\r")

async def run():
    print(f"Looking for Myo at {MYO_ADDRESS}...")
    device = await BleakScanner.find_device_by_address(MYO_ADDRESS)
    
    if not device:
        print("Myo not found.")
        return

    print("Connecting...")
    async with BleakClient(device) as client:
        print("Connected! Press 'q' to quit.")
        
        # 1. Keep Awake
        await client.write_gatt_char(CMD_UUID, bytes([0x09, 0x01, 0x01]))
        
        # 2. Set Mode to RAW (Important!)
        # 0x01 (Set Mode) -> 0x03 (Len) -> 0x03 (EMG=Raw) -> 0x00 -> 0x00
        await client.write_gatt_char(CMD_UUID, bytes([0x01, 0x03, 0x03, 0x00, 0x00]))
        
        # 3. Start Stream
        controller = FlappyController()
        await client.start_notify(EMG_DATA_UUID, controller.process_emg)

        while True:
            if keyboard.is_pressed('q'):
                print("\nQuitting...")
                break
            await asyncio.sleep(0.01)

if __name__ == "__main__":
    asyncio.run(run())