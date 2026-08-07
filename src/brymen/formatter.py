# Convert a parsed reading packet into a human-readable string

from .parsers import ReadingPacket

def format_reading(reading: ReadingPacket) -> str:
    """
    Given a parsed ReadingPacket, return a string like "123.45 V".
    Handles overload, ASCII displays, and signs.
    """
    # TODO(sdk-output): this scaling logic duplicates overlay/state.py and the
    # decimal_pos == 0 special case below ("as if decimal_pos is 5") is a
    # protocol quirk leaking here. Once ReadingPacket exposes `value`/`decimals`,
    # derive the string from those instead of re-scaling from raw fields.
    if reading is None:
        return "Invalid packet"
    if reading.is_overload:
        return "OL"
    if reading.is_ascii:
        return reading.ascii_text or "???"

    raw = reading.raw_value
    decimal_pos = reading.decimal_pos
    display_digits = reading.display_digit_count
    
    if decimal_pos == 0:
        scaling = 1 # when decimal_pos is 0 it is as if decimal_pos is 5
    else:
        scaling = 10 ** (display_digits - decimal_pos)
    
    value = raw / scaling # The reported raw value already reflects the prefix scaling from the meter, do not apply any additional prefix multiplier here.
    
    # Determine number of decimal places to show.
    if decimal_pos == 0:
        decimals = 0
    else:
        decimals = display_digits - decimal_pos
        # Safety cap to avoid excessive decimals
        if decimals > 6:
            decimals = 6
    
    # Format the number
    format_str = f"{{:.{decimals}f}}"
    number_str = format_str.format(value)
    
    # Combine with prefix and unit
    prefix = reading.prefix  # symbol like 'k', 'm', etc.
    unit = reading.unit
    if prefix:
        return f"{number_str} {prefix}{unit}"
    else:
        return f"{number_str} {unit}".strip()