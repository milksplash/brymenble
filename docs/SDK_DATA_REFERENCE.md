# SDK Data Reference

> What data `brymenble` parses from the meter, and what each field means.
> This is the reference for consuming the SDK's parsed output — for example,
> to drive a display emulation of the meter's LCD.

The SDK's parsers turn raw BLE frames into three dataclasses —
`InfoPacket`, `ReadingPacket`, and `RtcTime` — plus a `CommandResponse` for the
command/response layer. All parsed packets also keep the original `raw` bytes,
so nothing is ever lost.

---

## `ReadingPacket`

Parsed from each 32-byte Device Reading packet. This is the primary source of
data for display work.

### Value (the main reading)

| Field | Type | Meaning |
|---|---|---|
| `raw_value` | `int` | Raw display value (signed 24-bit). Already scaled by the meter's prefix — do **not** apply an extra prefix multiplier. |
| `decimal_pos` | `int` | Decimal point position (0 = no decimal point). |
| `display_digit_count` | `int` | Number of digits the meter displays (3–6). |
| `prefix` | `str` | Metric prefix symbol: `""`, `"n"`, `"µ"`, `"m"`, `"k"`, `"M"`, `"G"`. |
| `unit` | `str` | Unit symbol: `"V"`, `"A"`, `"Ω"`, `"S"`, `"F"`, `"Hz"`, `"%"`, `"°C"`, `"°F"`, `"%4~20mA"`. |

Use `brymen.formatter.format_reading(reading)` to get the complete display
string (e.g. `"123.45 V"`).

### Measurement context

| Field | Type | Meaning |
|---|---|---|
| `function_name` | `str` | Human-readable function/mode, e.g. `"DCV"`, `"ACmA"`, `"Resistance"`. |
| `logging_data_set_id` | `int` | Logging dataset ID (`0x000001` for BM78XBT). |
| `device_reading_pk_id` | `int` | Reading packet ID (`0x01` for single-display devices). |
| `device_type` | `int` | `0` = Sensor, `1` = Meter. |

### Status flags (annunciators)

Each maps to a named `bool` — show/hide the corresponding LCD icon:

| Field | Type | LCD icon |
|---|---|---|
| `is_negative` | `bool` | minus sign |
| `is_overload` | `bool` | `OL` (ignore `raw_value`) |
| `is_held` | `bool` | `HOLD` |
| `is_relative` | `bool` | `REL` |
| `is_auto_range` | `bool` | `AUTO` |
| `is_auto_hold` | `bool` | `A-HOLD` |
| `is_crest` | `bool` | `CREST` |
| `is_recording` | `bool` | `REC` |
| `is_max` | `bool` | `MAX` |
| `is_min` | `bool` | `MIN` |
| `is_avg` | `bool` | `AVG` |
| `is_ascii` | `bool` | ASCII display active (see below) |

The raw flag bytes are also kept as `status0` / `status1` (`int`) in case the
meter ever sets a bit the SDK hasn't named.

### ASCII display

When `is_ascii` is set, the meter is showing a non-numerical state and
`raw_value` maps to text in `ascii_text`:

`"Auto"`, `"InEr"`, `"-"`, `"--"`, `"---"`, `"----"`, `"-----"`, `"EF-H"`,
`"EF-L"`.

### Timestamp

| Field | Type | Meaning |
|---|---|---|
| `rtc` | `RtcTime` | Meter's RTC timestamp carried in the packet (see below). |

### Data integrity

| Field | Type | Meaning |
|---|---|---|
| `crc_ok` | `bool` | Whether the packet's CRC-16 verified. Treat `False` as suspect data. |
| `raw` | `bytes` | The original 32-byte packet, unchanged. |

---

## `InfoPacket`

Parsed from each 24-byte Device Information packet (one per stream frame).
Useful for status/battery indicators and confirming which meter you're
connected to.

| Field | Type | Meaning |
|---|---|---|
| `device_category` | `int` | Category ID; use `category_name` for text. |
| `category_name` | `str` | `"Multimeter"` or `"Clamp-on"`. |
| `mac` / `mac_str` | `bytes` / `str` | Meter MAC address (display order). |
| `battery_status` | `int` | `0x00` Normal, `0x02` Low; use `battery_name` for text. |
| `battery_name` | `str` | `"Normal"` or `"Low"`. |
| `power_source` | `int` | Power source flag. |
| `reading_packet_count` | `int` | Number of reading packets that follow (usually 4). |
| `device_reading_pk_id` | `int` | Device reading packet ID. |
| `crc_ok` | `bool` | Whether the packet's CRC-16 verified. |
| `raw` | `bytes` | The original 24-byte packet, unchanged. |

---

## `RtcTime`

Decoded time-of-day carried in each reading packet.

| Field | Type | Range |
|---|---|---|
| `year` | `int` | 2000–2127 |
| `month` | `int` | 1–12 |
| `date` | `int` | 1–31 |
| `hour` | `int` | 0–23 |
| `minute` | `int` | 0–59 |
| `second` | `int` | 0–59 |
| `millisecond` | `int` | 0–999 |

---

## `CommandResponse`

Parsed reply to a command sent via `BrymenClient.send_command()`. A failed
command raises `brymen.CommandError` (carrying the response) rather than
returning normally.

| Field / Property | Type | Meaning |
|---|---|---|
| `command_id` | `int` | Echoed command ID, or `0x8001` on failure. |
| `is_failure` | `bool` | True for a `0x8001` failure frame. |
| `failed_command_id` | `int \| None` | The command that failed (failure frames only). |
| `error_code` | `int \| None` | Meter error code (failure frames only). |
| `error_message` | `str \| None` | Human-readable error (`"Invalid password"`, etc.). |
| `args` | `bytes` | Raw 14-byte argument payload. |
| `crc_ok` | `bool` | Whether the packet's CRC-16 verified. |

---

## Parsing entry points

Most users never call these directly — `BrymenClient` streams already-parsed
`Frame` tuples (`(InfoPacket, list[ReadingPacket | None])`). They're exposed
for testing and tooling:

| Function | Returns |
|---|---|
| `parse_stream_frame(data)` | `(InfoPacket, [ReadingPacket \| None ×4])` from a 152-byte notification |
| `parse_info_packet(packet)` | `InfoPacket \| None` |
| `parse_reading_packet(packet)` | `ReadingPacket \| None` |
| `parse_command_response(packet)` | `CommandResponse \| None` |

`None` results mean the packet was invalid (wrong length/header) or, for the 3
trailing reading packets in a frame, empty/all-zero.

---

## Notes for building a display emulation

- The 7-segment digits come from `raw_value` + `decimal_pos` +
  `display_digit_count`; the `prefix` and `unit` select the unit/prefix labels.
- Annunciator visibility maps 1:1 to the `is_*` booleans in the Status flags
  table above.
- When `is_overload`, light `OL` and ignore the value.
- When `is_ascii`, render `ascii_text` instead of a numeric value.
- `InfoPacket.battery_name` drives a low-battery icon.
- The protocol carries **no bar-graph level** — if your overlay includes a bar
  graph it must be derived or omitted.
