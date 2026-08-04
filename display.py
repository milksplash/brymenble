from typing import List

import formatter
from parsers import InfoPacket, ReadingPacket


def print_info(info: InfoPacket):
    """Print the device-info packet."""
    if info is None:
        return
    print("--- Device Information Packet ---")
    cat = ("Multimeter" if info.device_category == 0x02
           else "Clamp-on" if info.device_category == 0x03
           else f"0x{info.device_category:02X}")
    batt = "Low" if info.battery_status == 0x02 else "Normal"
    mac = ':'.join(f'{b:02X}' for b in info.mac)
    print(f"Category: {cat}, MAC: {mac}, Battery: {batt}, CRC OK: {info.crc_ok}")


def print_reading(idx: int, r: ReadingPacket):
    """Print a single reading packet (raw hex + parsed values)."""
    if r is None:
        return
    print("--- Device Reading Packet ---")
    for chunk_start in range(0, len(r.raw), 16):
        chunk = r.raw[chunk_start:chunk_start + 16]
        line = ' '.join(f"[{i:02d}] {b:02X}" for i, b in enumerate(chunk, start=chunk_start))
        print(line)
    display = formatter.format_reading(r)
    rtc = r.rtc
    time_str = f"{rtc.hour:02d}:{rtc.minute:02d}:{rtc.second:02d}.{rtc.millisecond:03d} {rtc.year}-{rtc.month:02d}-{rtc.date:02d}"
    print(f"  Parsed: {display}   Func: {r.function_name}   Time: {time_str}   CRC OK: {r.crc_ok}")


def print_frame(info, readings):
    """Print a full : InfoPacket, readings: List[ReadingPacket]me: info packet plus all reading packets."""
    print("\n")
    print_info(info)
    for idx, r in enumerate(readings):
        print_reading(idx, r)
