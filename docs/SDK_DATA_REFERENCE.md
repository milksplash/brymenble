# SDK Data Reference

> What data `brymenble` parses from the meter, and what each field means.
> This is the reference for consuming the SDK's parsed output — for example,
> to drive a display emulation of the meter's LCD.

The SDK's parsers turn raw BLE frames into four dataclasses — `InfoPacket`,
`ReadingPacket`, `RtcTime`, and `StreamFrame` (the parsed container for a full
notification) — plus a `CommandResponse` for the command/response layer. All
parsed packets also keep the original `raw` bytes, so nothing is ever lost.

> **⚠️ Data source.** The SDK reads the meter's **official wireless data
> protocol** over BLE — the numeric value, units, and status flags the meter
> transmits. It does **not** read, capture, or analyze the meter's physical
> display; anything rendered from this data is an emulation, not a video feed.

---

## `ReadingPacket`

Parsed from each 32-byte Device Reading packet. This is the primary source of
data for display work.

### Value (the main reading)

This is the canonical value surface — prefer these over re-deriving the
display value yourself:

| Field | Type | Meaning |
|---|---|---|
| `mantissa` | `int` | Displayed digits as a **non-negative magnitude**, already scaled by the meter's prefix — do **not** apply an extra prefix multiplier. |
| `signed_value` | `int` | `mantissa` with the sign flag applied (`-mantissa` when `is_negative`). |
| `decimal_pos` | `int` | Decimal point position (0 = no decimal point). |
| `decimals` | `int` | Digits after the decimal point (0–6) = `display_digit_count - decimal_pos`. |
| `value` | `float \| None` | Fully-scaled signed measurement (`signed_value / 10**decimals`), or `None` for overload/ASCII modes. |
| `display_digit_count` | `int` | Number of digits the meter displays (3–6). |
| `prefix` | `str` | Metric prefix symbol: `""`, `"n"`, `"µ"`, `"m"`, `"k"`, `"M"`, `"G"`. |
| `unit` | `str` | Unit symbol: `"V"`, `"A"`, `"Ω"`, `"S"`, `"F"`, `"Hz"`, `"%"`, `"°C"`, `"°F"`, `"%4~20mA"`. |

The sign lives ONLY in `is_negative` / `signed_value` / `value` — `mantissa`
is always a magnitude, so don't apply the sign twice (the protocol encodes it
in exactly one place, the SIGN bit).

Use `brymenble.formatter.format_reading(reading)` to get the complete display
string (e.g. `"123.45 V"`), or `reading.to_dict()` for a stable
JSON-serializable dict.

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
| `is_overload` | `bool` | `OL` (ignore `mantissa` / `value`) |
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
`mantissa` maps to text in `ascii_text`:

`"Auto"`, `"InEr"`, `"-"`, `"--"`, `"---"`, `"----"`, `"-----"`, `"EF-H"`,
`"EF-L"`.

In ASCII and overload modes `value` is `None` — render `ascii_text` / `OL`
instead of a number.

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

| Method | Returns |
|---|---|
| `to_dict()` | Stable JSON-serializable dict. |
| `isoformat()` | `"YYYY-MM-DD HH:MM:SS.mmm"` — the canonical clock string every consumer (overlay render state, console apps, tools) prints. |

---

## `StreamFrame`

One 152-byte notification parsed into its parts — this is what
`BrymenbleClient` yields (and what `parse_stream_frame` returns).

| Field | Type | Meaning |
|---|---|---|
| `info` | `InfoPacket \| None` | The frame's device-info packet (`None` if invalid). |
| `readings` | `list[ReadingPacket \| None]` | Up to 4 reading packets; empty/all-zero trailing ones are `None`. |

`to_dict()` on `StreamFrame`, `InfoPacket`, `ReadingPacket`, and `RtcTime`
returns a stable, JSON-serializable dict (raw `bytes` serialized as
`raw_hex`).

### Convenience factories

`InfoPacket.example()` and `ReadingPacket.example()` build a realistic,
well-formed packet (Multimeter `00:11:22:33:44:55` / `607.80 V` DCV,
5-digit) without a meter — the single source for demos, tools and test
fixtures. Pass any field as a keyword to override it, e.g.
`ReadingPacket.example(is_overload=True)`.

---

## `CommandResponse`

Parsed reply to a command sent via `BrymenbleClient.send_command()`. A failed
command raises `brymenble.CommandError` (carrying the response) rather than
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

Most users never call these directly — `BrymenbleClient` streams already-parsed
`StreamFrame` objects (`frame.info` + `frame.readings`). They're exposed for
testing and tooling:

| Function | Returns |
|---|---|
| `parse_stream_frame(data)` | `StreamFrame \| None` from a 152-byte notification (`None` = unexpected frame size) |
| `parse_info_packet(packet)` | `InfoPacket \| None` |
| `parse_reading_packet(packet)` | `ReadingPacket \| None` |
| `parse_command_response(packet)` | `CommandResponse \| None` |

### Discovery

`find_meters(timeout)` scans once for BM78xBT meters. For long-running apps
(overlay, bridge), `find_first_meter(timeout, retry_interval, on_retry)`
scans until one is found — retrying every `retry_interval` seconds and
calling `on_retry(attempt)` before each re-scan (`retry_interval <= 0` scans
once and returns `None` if nothing is found).

`None` results mean the packet was invalid (wrong length/header) or, for the 3
trailing reading packets in a frame, empty/all-zero. A returned
`StreamFrame.info` is `None` if the frame's info packet was invalid.

---

## Notes for building a display emulation

- The 7-segment digits come from `mantissa` + `decimal_pos` +
  `display_digit_count` (or use the precomputed `value` / `decimals`);
  the `prefix` and `unit` select the unit/prefix labels.
- The sign is `is_negative` — `mantissa` is always a magnitude, so never apply
  both (that split — `abs(raw_value)` + flag — was a footgun the SDK removed).
- Annunciator visibility maps 1:1 to the `is_*` booleans in the Status flags
  table above.
- When `is_overload`, light `OL` and ignore the value.
- When `is_ascii`, render `ascii_text` instead of a numeric value.
- `InfoPacket.battery_name` drives a low-battery icon.
- The protocol carries **no bar-graph level** — if your overlay includes a bar
  graph it must be derived or omitted.

### Known display behaviors the SDK cannot replicate

Two behaviors of the physical LCD have no representation in the protocol, so a
display driven purely by SDK data cannot reproduce them exactly:

- **Blank reading on function change.** Turning the meter's function selector
  blanks the reading on the real display for the moment of the switch. The
  protocol has no "display blanked" state and no "function changing" event:
  while switching, the meter simply stops emitting reading packets (the BLE
  link stays up) and resumes with the new function's first frame. The SDK
  surfaces this only as a data gap — `read_stream()` treats a link-up gap as
  a pause (`on_pause`) and keeps the last reading on screen, so an emulation
  holds the previous value instead of blanking. If you want a blank/paused
  look, render it yourself when you observe a pause; there is no flag to key
  off.

- **Decimal-place shifting on aggressive auto-range changes.** In an
  auto-ranging function — most apparent in Resistance — a large, sudden
  change in the measured value makes the meter step ranges and move the
  decimal point (with the prefix changing together, e.g. `kΩ` ↔ `MΩ`).
  Every frame the SDK delivers is internally correct: `mantissa`,
  `decimal_pos` and `prefix` describe that frame's settled display, so
  swapping all three together reproduces each frame the meter reports. What
  the SDK cannot replicate is the *transition*: there is no auto-ranging /
  range-change signal and no animation data, so an emulation sees one
  settled frame jump to the next. Treat each frame as an atomic display
  state — never interpolate or animate `decimal_pos` / `prefix` between
  frames, because holding the old dp/prefix while new digits arrive (or the
  reverse) renders a misplaced decimal the real meter never shows.
