import formatter


def print_info(info):
    """Print the device-info packet."""
    if info is None:
        return
    print("--- Device Information Packet ---")
    cat = ("Multimeter" if info['device_category'] == 0x02
           else "Clamp-on" if info['device_category'] == 0x03
           else f"0x{info['device_category']:02X}")
    batt = "Low" if info['battery_status'] == 0x02 else "Normal"
    mac = ':'.join(f'{b:02X}' for b in info['mac'])
    print(f"Category: {cat}, MAC: {mac}, Battery: {batt}, CRC OK: {info['crc_ok']}")


def print_reading(idx, r):
    """Print a single reading packet (raw hex + parsed values)."""
    if r is None:
        return
    print("--- Device Reading Packet ---")
    raw_bytes = [r['raw'][i:i+2].upper() for i in range(0, len(r['raw']), 2)]
    for chunk_start in range(0, len(raw_bytes), 16):
        chunk = raw_bytes[chunk_start:chunk_start + 16]
        line = ' '.join(f"[{i:02d}] {b}" for i, b in enumerate(chunk, start=chunk_start))
        print(line)
    display = formatter.format_reading(r)
    rtc = r.get('rtc', {})
    time_str = f"{rtc.get('hour', 0):02d}:{rtc.get('minute', 0):02d}:{rtc.get('second', 0):02d}.{rtc.get('millisecond', 0):03d} {rtc.get('year', 0)}-{rtc.get('month', 0):02d}-{rtc.get('date', 0):02d}"
    print(f"  Parsed: {display}   Func: {r['function_name']}   Time: {time_str}   CRC OK: {r['crc_ok']}")


def print_frame(info, readings):
    """Print a full stream frame: info packet plus all reading packets."""
    print("\n")
    print_info(info)
    for idx, r in enumerate(readings):
        print_reading(idx, r)
