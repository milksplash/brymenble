from typing import List

from brymen import formatter
from brymen.parsers import InfoPacket, ReadingPacket


def print_info(info: InfoPacket):
    """Print the device-info packet (raw hex + parsed values)."""
    if info is None:
        return
    print("--- Device Information Packet ---")
    for chunk_start in range(0, len(info.raw), 16):
        chunk = info.raw[chunk_start:chunk_start + 16]
        line = ' '.join(f"[{i:02d}] {b:02X}" for i, b in enumerate(chunk, start=chunk_start))
        print(line)
    print(f"  Parsed: Category: {info.category_name}, MAC: {info.mac_str}, "
          f"Battery: {info.battery_name}, CRC OK: {info.crc_ok}")


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


def print_frame(info: InfoPacket, readings: List[ReadingPacket]):
    """Print a full stream frame: info packet plus all reading packets."""
    print("\n")
    print_info(info)
    for idx, r in enumerate(readings):
        print_reading(idx, r)
