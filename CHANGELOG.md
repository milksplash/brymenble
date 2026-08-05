# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  fingerprint); `examples/scan.py` (with `--raw` dump for debugging).
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
