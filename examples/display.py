import time
from typing import List, Optional

from brymen import formatter
from brymen.parsers import InfoPacket, ReadingPacket

# Rolling window of inter-packet intervals (seconds), tracked per frame and
# used by the statistics block at the end of print_frame().
_last_frame_time: Optional[float] = None
_intervals: List[float] = []
_MAX_INTERVALS = 20


def _record_frame() -> None:
    """Record the current frame's arrival time for packet statistics."""
    global _last_frame_time, _intervals
    now = time.monotonic()
    if _last_frame_time is not None:
        interval = now - _last_frame_time
        _intervals.append(interval)
        if len(_intervals) > _MAX_INTERVALS:
            _intervals.pop(0)
    _last_frame_time = now


def print_stats() -> None:
    """Print packet timing statistics (last gap, average gap, frequency)."""
    print("--- Packet Statistics ---")
    if not _intervals:
        print("  Time since last packet: (first packet)")
        print("  Average time between packets: (first packet)")
        print("  Packet frequency: (first packet)")
        return
    since_last_ms = _intervals[-1] * 1000
    avg_ms = (sum(_intervals) / len(_intervals)) * 1000
    freq = 1.0 / (avg_ms / 1000) if avg_ms > 0 else 0.0
    print(f"  Time since last packet: {since_last_ms:.1f} ms")
    print(f"  Average time between packets: {avg_ms:.1f} ms")
    print(f"  Packet frequency: {freq:.2f} Hz")


def print_info(info: InfoPacket):
    """Print the device-info packet (raw hex + parsed values)."""
    if info is None:
        return
    print("--- Device Information Packet ---")
    for chunk_start in range(0, len(info.raw), 12):
        chunk = info.raw[chunk_start:chunk_start + 12]
        line = ' '.join(f"[{i:02d}] {b:02X}" for i, b in enumerate(chunk, start=chunk_start))
        print(line)
    print(f"  Parsed: Category: {info.category_name}, MAC: {info.mac_str}, "
          f"Battery: {info.battery_name}, CRC OK: {info.crc_ok}")


def print_reading(idx: int, r: ReadingPacket):
    """Print a single reading packet (raw hex + parsed values)."""
    if r is None:
        return
    print("--- Device Reading Packet ---")
    # for chunk_start in range(0, len(r.raw), 16):
    #     chunk = r.raw[chunk_start:chunk_start + 16]
    #     line = ' '.join(f"[{i:02d}] {b:02X}" for i, b in enumerate(chunk, start=chunk_start))
    #     print(line)
    display = formatter.format_reading(r)
    rtc = r.rtc
    time_str = f"{rtc.year}-{rtc.month:02d}-{rtc.date:02d} {rtc.hour:02d}:{rtc.minute:02d}:{rtc.second:02d}.{rtc.millisecond:03d}"
    print(f"  Value: {display}   Function: {r.function_name}   Device Time: {time_str}   CRC OK: {r.crc_ok}")


def print_frame(info: InfoPacket, readings: List[ReadingPacket]):
    """Print a full stream frame: info packet plus all reading packets."""
    _record_frame()
    print("\n")
    # print_info(info)
    for idx, r in enumerate(readings):
        print_reading(idx, r)
    print_stats()
