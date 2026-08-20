# Convert a parsed reading packet into a human-readable string

from .parsers import ReadingPacket

def format_reading(reading: ReadingPacket) -> str:
    """
    Given a parsed ReadingPacket, return a string like "123.45 V".
    Handles overload, ASCII displays, and signs.
    """
    if reading is None:
        return "Invalid packet"
    if reading.is_overload:
        return "OL"
    if reading.is_ascii:
        return reading.ascii_text or "???"

    # Derived from the packet's canonical value/decimals surface rather than
    # re-scaling the raw fields here — so this can never drift from other
    # consumers (overlay, to_dict(), etc.) on edge cases like decimal_pos == 0.
    value = reading.value
    if value is None:   # defensive; unreachable after the overload/ASCII checks
        return "???"
    number_str = f"{value:.{reading.decimals}f}"

    # Combine with prefix and unit
    prefix = reading.prefix  # symbol like 'k', 'm', etc.
    unit = reading.unit
    if prefix:
        return f"{number_str} {prefix}{unit}"
    else:
        return f"{number_str} {unit}".strip()