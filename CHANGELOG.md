# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.3] - 2026-08-26

Compatibility-preserving hardening pass from a review of 0.5.2 — fixes are
all backward-compatible; no public API is removed or changed.

### Fixed

- **`commands.build_command_packet()` — out-of-range `command_id` now raises
  `ValueError`** (was `OverflowError` from the internal `.to_bytes()`), keeping
  the documented exception contract consistent with every other invalid input.
- **`commands.build_command_packet()` — over-long `args` rejected** — an
  argument list longer than 14 bytes silently produced an oversized packet and
  violated the 32-byte framing invariant; it now raises `ValueError`.
- **`transport.CommandError` message could print `"0xNone"`** — a malformed
  `0x8001` failure frame with fewer than 4 args formatted `None` as
  `0xNone`; the message now falls back to `0x0000`.
- **`transport._on_notify` could raise on a worker thread during shutdown** —
  `loop.call_soon_threadsafe()` on a closing/closed loop threw an uncaught
  `RuntimeError` on bleak's worker thread after Ctrl+C/`close()`; it is now
  guarded and the in-flight notification is harmlessly dropped.
- **`transport.wait_frame(timeout=0)` always returned `None`** even with a
  pending frame (the task never got a loop iteration before the 0-timeout
  fired); `timeout == 0` now drains the queue like `latest_frame()`.
- **`parsers.RtcTime` millisecond could exceed 999** — the wire field is 10
  bits (0–1023) but the protocol documents 0–999, so a value ≥ 1000 would make
  `isoformat()` emit an invalid clock string (e.g. `.1023`); it is now clamped
  to `min(999, ...)`.
- **`transport` silently dropped frames with an invalid info packet** — a
  single transiently-corrupted info packet discarded up to 4 individually
  CRC-verified readings in a live stream; such frames are now logged and
  delivered with `info=None` (the state `StreamFrame` already models), so
  valid readings survive and consumers can decide.

### Changed

- **`tools/connection_state.py` now runs on Python 3.9** — replaced a
  `str | None` annotation (3.10+ syntax) with `Optional[str]` so the tool
  works on the package's declared `>=3.9` interpreter.
- **Added `commands.encode_password_args()`** — shared the digit→byte
  password encoding once, removing duplication between
  `build_verify_password_packet` and `transport._connect`.
- **Shared example boilerplate** — `examples/live.py` and
  `examples/debug_stream.py` now reuse a common `examples/_common.py`
  (scan/connect/arg-parse/entry-point), each keeping only its app-specific
  stream loop.
- Documented the settling `await asyncio.sleep(0.5)` after RTC sync in
  `transport._connect`.

## [0.5.2] - 2026-08-20

### Changed

- **Packaging metadata** — added `[project.urls]` (Homepage, Repository,
  Issues) so PyPI surfaces the GitHub project links, and documented the
  install options in the README (`pip install brymenble`, editable source
  checkout, or directly from GitHub).

## [0.5.1] - 2026-08-20

### Changed

- **Renamed the importable module from `brymen` to `brymenble`** — the
  distribution name is unchanged, but `import brymen` is now `import
  brymenble`. `BrymenClient` is now `BrymenbleClient`, and
  `is_brymen_advertisement` is now `is_brymenble_advertisement`. This removes
  the bare trademark as a namespace while keeping the `brymenble` PyPI name.

## [0.5.0] - 2026-08-20

### Added

- **`find_first_meter()`** — discovery wrapped in a retry loop for long-running
  apps (overlay, bridge, connection-state tool). Scans until a BM78xBT meter is
  found, retrying every `retry_interval` seconds and calling
  `on_retry(attempt)` before each re-scan; `retry_interval <= 0` does a
  single-shot scan that returns `None` when nothing is found.
- **`InfoPacket.example()` / `ReadingPacket.example()`** — convenience
  factories that build a realistic, well-formed packet (Multimeter
  `00:11:22:33:44:55` / `607.80 V` DCV, 5-digit) without a meter. The single
  source for demos, tools and test fixtures; any field can be overridden as a
  keyword argument.
- **`RtcTime.isoformat()`** — the canonical `"YYYY-MM-DD HH:MM:SS.mmm"` clock
  string, kept here as the single source of truth instead of each consumer
  re-formatting the fields.
- **`StreamFrame.raw`** — each frame now carries the full raw notification
  bytes (info + reading packets, unmodified), for raw-protocol debugging and
  `to_dict()` round-tripping (`raw_hex`).
- **`brymenble.console` lifecycle/status callbacks** — `state()` (padded
  state-report line), `found()`, `connecting()`, `connected()`,
  `disconnected()`, `scanning_retry()`, and `using()`, so every consumer
  prints identical timestamped output.
- **`examples/debug_stream.py`** — a raw-protocol debug/test script that dumps
  every frame via `examples/display.py`: full raw frame hex, the device-info
  packet, each reading packet, and packet-timing statistics.
- **Single-connection hint** — a failed connect now includes a one-time
  warning + error hint that BLE is 1:1, so a meter that is actually connected
  elsewhere is not mistaken for "out of range".

### Changed

- **`sync_rtc_on_connect` now defaults to `True`** — the meter has no RTC
  battery, so its clock resets on power-off; syncing on connect is now the
  default behaviour (opt out with `sync_rtc_on_connect=False`).
- **`read_stream()` `no_data_timeout` default 3.0s → 1.0s** — a shorter
  link-up silence window before a pause is declared, so function-switch pauses
  are detected more promptly.
- **Renamed `examples/console.py` → `examples/live.py`** — the SDK's
  `brymenble.console` module owns the "console" name now; the old raw-frame
  console was restored as `examples/debug_stream.py`.
- **`tools/connection_state.py`** now uses the shared `brymenble.console` helpers
  and `find_first_meter()`, and honours the RTC-sync default (`--no-sync-rtc`
  opts out); `--interval` / `--heartbeat` defaults tightened to 1.0s.
- **`tools/capture.py`** reuses the SDK's exported UUIDs / default password
  instead of re-declaring them.
- **`tools/probe.py`** reads `StreamFrame` fields directly (it is a named
  dataclass, not a tuple).
- **README / `docs/SDK_DATA_REFERENCE.md`** — added the "data source" disclaimer
  (the SDK reads the official wireless protocol, not the physical display) and
  documented two display behaviors the protocol cannot replicate (blank-on-
  function-change, decimal-shift on aggressive auto-range).

### Fixed

- **Bleak transport errors normalized to `ConnectionError`** — `BleakError`
  and its subclasses (e.g. "device not found") from `connect()` now surface as
  `ConnectionError` so the retry policy can act on them; `CommandError` /
  `ValueError` (wrong password, bad MAC) still pass through unchanged.
- **GATT timeouts no longer leak `asyncio.CancelledError`** — the command
  round-trip now uses `asyncio.wait` + manual cancel instead of `wait_for`, so
  bleak's winrt backend can't surface a bare `CancelledError` on timeout (a
  genuine external cancellation still propagates).

## [0.4.0] - 2026-08-11

### Added

- **`BrymenbleClient.read_stream()`** — a high-level streaming iterator for
  long-running consumers. It owns the pause-vs-power-off decision that used
  to be duplicated in every app: a data gap while the BLE link is up is a
  meter pause (e.g. mid function-switch) and is waited out, while a link drop
  is confirmed with a `link_down_grace` window and transparently reconnected
  (bounded, or forever with `retries=None`). Lifecycle callbacks:
  `on_pause()`, `on_lost(reason)` (`"link_down"` or `"pause_cap"`),
  `on_reconnected()`, plus `on_retry` passthrough. `pause_cap` bounds how
  long a link-up silence is tolerated before a forced reconnect (`None` =
  wait out pauses indefinitely). Auto-connects on first use if the client
  isn't connected yet.
- **`brymenble.console`** — shared console output helpers (`ts()`, `status()`,
  `reading_line()`, lifecycle callbacks `retry` / `paused` / `lost` /
  `reconnected` / `scanning` / `using`) so every consumer (SDK examples,
  overlay, TC bridge) prints identical timestamped output.
- **`StreamFrame.raw`** — each frame now carries the full raw notification
  bytes (info + reading packets, unmodified), for raw-protocol debugging and
  `to_dict()` round-tripping (`raw_hex`).
- **`examples/debug_stream.py`** — a raw-protocol debug/test script that
  dumps every frame via `examples/display.py`: full raw frame hex, the
  device-info packet, each reading packet, and packet-timing statistics.

### Changed

- **Console, overlay and bridge now use `read_stream()`** — the duplicated
  gap/pause/reconnect loops in `examples/live.py`,
  `brymenble-overlay/main.py` and `brymenble-tc-bridge/bridge.py` were
  collapsed onto the SDK primitive; the bridge's `silence_since`/`pause_cap`
  state machine was removed entirely.
- **Renamed `examples/console.py` → `examples/live.py`** — the SDK's
  `brymenble.console` module owns the "console" name now; the old raw-frame
  console was restored as `examples/debug_stream.py`.
- **Single-connection hint** — a failed connect now includes a one-time
  warning + error hint that BLE is 1:1, so a meter that is actually connected
  elsewhere is not mistaken for "out of range".

## [0.3.1] - 2026-08-10

### Added

- **`BrymenbleClient.is_connected`** — a live link-liveness signal that
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

- **`BrymenbleClient.ensure_connected(retries=None)`** — infinite reconnect mode
  for long-running consumers (overlays, loggers): keeps retrying until the
  meter returns or the task is cancelled, instead of giving up after a bounded
  count. `on_retry` receives `max_retries=None` in this mode.
- **`ReadingPacket` canonical value surface** — `mantissa` (magnitude),
  `signed_value`, `decimals`, and `value` (fully-scaled signed measurement,
  `None` for overload/ASCII modes) so consumers stop re-deriving the display
  value themselves; plus stable `to_dict()` JSON serialization on
  `ReadingPacket`, `InfoPacket`, `RtcTime`, and `StreamFrame`.
- **`StreamFrame` dataclass** — `BrymenbleClient` now yields a named
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

- The anonymous `Frame` tuple type alias in `brymenble.transport` (kept as
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
- **`BrymenbleClient.ensure_connected()`** — connects (or reconnects) with a
  bounded retry policy and an `on_retry` callback for progress reporting;
  `close()` is now a public, idempotent way to disconnect.
- **`examples/console.py` auto-scan** — with no MAC argument the console scans
  for the first BM78xBT meter (`find_meters()`) instead of defaulting to a
  placeholder address.

### Changed

- `console.py` uses `BrymenbleClient.ensure_connected()` / `close()` instead of
  reaching into `__aenter__` / `__aexit__`.

### Removed

- **Console manual mode** — `examples/console.py --manual` was removed; the
  on-demand flow is provided by `tools/capture.py` and `tools/probe.py`.

## [0.1.0] - 2026-08-05

### Added

- **`BrymenbleClient`** — async context manager that connects, verifies the
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
- **Discovery** — `find_meters()` / `is_brymenble_advertisement()` locate BM78xBT
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
