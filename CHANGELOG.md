# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-08-10

### Added

- **`BrymenClient.is_connected`** — a live link-liveness signal that
  distinguishes a meter that is merely paused (BLE link still up, e.g. mid
  function-switch) from one that powered off (link dropped). Resolves the old
  `TODO(investigate)` about spurious reconnects: consumers should pair
  `wait_frame()`'s timeout with `is_connected` instead of treating every data
  gap as a power-off. (bleak >= 0.21 exposes `is_connected`; the test seam's
  `connected` attribute is also honoured.)
- **Notify-gap instrumentation** — `notify_gap_log_threshold` (default 2.0s)
  logs gaps of that size or more at DEBUG, tagged with the reading's function,
  so the meter's per-function pause cadence can be characterised on real
  hardware.

## [0.3.0] - 2026-08-08

### Added

- **`BrymenClient.ensure_connected(retries=None)`** — infinite reconnect mode
  for long-running consumers (overlays, loggers): keeps retrying until the
  meter returns or the task is cancelled, instead of giving up after a bounded
  count. `on_retry` receives `max_retries=None` in this mode.
- **`ReadingPacket` canonical value surface** — `mantissa` (magnitude),
  `signed_value`, `decimals`, and `value` (fully-scaled signed measurement,
  `None` for overload/ASCII modes) so consumers stop re-deriving the display
  value themselves; plus stable `to_dict()` JSON serialization on
  `ReadingPacket`, `InfoPacket`, `RtcTime`, and `StreamFrame`.
- **`StreamFrame` dataclass** — `BrymenClient` now yields a named
  `StreamFrame(info, readings)` instead of an anonymous tuple, and
  `parse_stream_frame()` returns `StreamFrame | None`.

### Changed

- **Renamed `ReadingPacket.raw_value` → `mantissa`** and made it always a
  non-negative magnitude. The sign now lives only in `is_negative` /
  `signed_value` / `value`, removing the old `abs(raw_value)` + flag footgun
  (formatter and overlay previously disagreed on sign handling and the
  `decimal_pos == 0` edge case).
- **`parse_stream_frame()` logs instead of printing** to stdout on an
  unexpected frame length (an SDK shouldn't write to the console).

### Removed

- The anonymous `Frame` tuple type alias in `brymen.transport` (kept as
  `Frame = parsers.StreamFrame` for import compatibility).

## [0.2.0] - 2026-08-05

### Added

- **Status-flag support** — `ReadingPacket` decodes every Status Flag 0/1 bit
  into named booleans (`is_crest` / `is_relative` / `is_held` /
  `is_auto_range` / `is_auto_hold` from byte 14; `is_negative` / `is_overload`
  / `is_recording` / `is_max` / `is_min` / `is_avg` from byte 15), plus the
  Logging Data Set ID, Device Reading PK ID, and Device Type. Raw `status0` /
  `status1` are kept so unknown bits are never lost; `display.py` renders the
  active indicators.
- **`BrymenClient.ensure_connected()`** — connects (or reconnects) with a
  bounded retry policy and an `on_retry` callback for progress reporting;
  `close()` is now a public, idempotent way to disconnect.
- **`examples/console.py` auto-scan** — with no MAC argument the console scans
  for the first BM78xBT meter (`find_meters()`) instead of defaulting to a
  placeholder address.

### Changed

- `console.py` uses `BrymenClient.ensure_connected()` / `close()` instead of
  reaching into `__aenter__` / `__aexit__`.

### Removed

- **Console manual mode** — `examples/console.py --manual` was removed; the
  on-demand flow is provided by `tools/capture.py` and `tools/probe.py`.

## [0.1.0] - 2026-08-05

### Added

- **`BrymenClient`** — async context manager that connects, verifies the
  connection password (reading and decoding the `0x8001` failure response, so
  a bad password fails the connect), subscribes to notifications, and streams
  parsed frames. Supports connect/GATT timeouts and `reconnect()`.
- **Command/response layer** — `send_command()` plus `CommandResponse` /
  `parse_command_response()` with `0x8001` failure and error-code decoding;
  full command table in `constants` (firmware version, RTC calibration, model
  series, password and device-name get/set).
- **RTC time sync** — `build_rtc_time_packet()` / `sync_rtc()` and an opt-in
  `sync_rtc_on_connect` flag (the meter has no RTC battery, so its clock
  resets on power-off).
- **Discovery** — `find_meters()` / `is_brymen_advertisement()` locate BM78xBT
  meters from their BLE advertisements (service UUID or manufacturer-data
  fingerprint).
- **Examples & tools** — `examples/console.py` + `examples/display.py` (raw-hex
  dumps, packet statistics), `tools/capture.py`, `tools/probe.py` (validates
  the command set against real hardware with value checks and a pass/fail
  exit code).
- **Tests** — transport unit tests with an injected fake `BleakClient`,
  scanner tests, and formatter overload/ASCII tests (55 offline tests).

### Fixed

- **Reading-packet RTC hour decode** — the hour is `byte10[7:6]` (low 2 bits)
  + `byte11[2:0]` (high 3 bits); a stored hour of 20 was previously misread
  as 5. Verified against real hardware.
- **Connect/GATT timeouts no longer leak `asyncio.CancelledError`** — bleak's
  winrt backend raises a bare `CancelledError` when `connect()` is cancelled
  mid-flight; timeouts now surface as `ConnectionError` (and genuine external
  cancellation still propagates).
- **`frames()` stale queue after reconnect** — the iterator now re-resolves
  its queue each iteration, so a long-lived iterator survives reconnects.
- **Thread-safe notifications** — callbacks are marshalled onto the event loop
  via `call_soon_threadsafe`, so queue/timestamp updates are race-free
  regardless of which thread bleak delivers on.
