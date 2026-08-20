"""Probe the BM78xBT command set against a real meter.

Connects and authenticates (the client verifies the connection password on
connect), then runs each command through BrymenbleClient.send_command() and
prints the raw + parsed result. This is a DEVELOPMENT tool for validating the
command/response layer (TODO #1) against real hardware — including confirming
the read-after-write response delivery.

It also exercises state-changing commands (RTC calibration, connection
password, device name) and restores them afterwards. If it crashes mid-run,
the meter is left with the values in the TEST_* constants (recovery keys).

Usage:
    .venv\\Scripts\\python.exe tools\\probe.py [MAC] [PASSWORD]
"""
import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

# Allow running directly as `python tools\\probe.py` from anywhere in the repo.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
))

from brymenble import (
    BrymenbleClient,
    CommandError,
    CommandResponse,
    DEFAULT_PASSWORD,
    constants,
)

DEFAULT_MAC = "00:11:22:33:44:55"

# Fixed probe values: easy to eyeball in the output, and the recovery keys if
# the script is interrupted mid-run (the meter keeps these values).
#
# TEST_RTC must use NON-ZERO, bit-sensitive values: the RTC is packed across
# split bit fields (e.g. hour = byte10[7:6] | byte11[2:0]<<2), and an all-zero
# time (00:00:00) decodes identically under any bit order, so it would hide
# decode bugs. 20:34:56 exercises the time fields (hour 20 is the exact case
# that previously misread as 5). Note: the 0x0010 command has no ms field.
TEST_RTC = datetime(2026, 1, 2, 20, 34, 56)
TEST_PASSWORD = "1234"                      # temporary connection password
TEST_DEVICE_NAME = "PROBE-01"               # temporary device name (1-12 chars)

# Labels of steps that failed (filled by probe()/confirm_rtc), used for the
# end-of-run summary and the process exit code.
FAILED_STEPS: list = []


def _password_str(args: bytes) -> str:
    """Password args are raw digit values (0-9 per byte), not ASCII."""
    return ''.join(str(b) for b in args[0:4])


def _name_str(args: bytes) -> str:
    """Device name args are ASCII, null-padded to 12 bytes."""
    return bytes(args[0:12]).decode('ascii', 'replace').rstrip('\x00')


def _expect_equal(value: str, expected: str, label: str) -> None:
    """Mark the step as failed if a confirmed value doesn't match the set one."""
    if value != expected:
        print(f"  MISMATCH: got {value!r}, expected {expected!r}")
        FAILED_STEPS.append(f"{label} (value mismatch)")


def _decode(args: bytes, command_id: int) -> str:
    """Human-readable decode of a success response's args."""
    if command_id == constants.CMD_GET_FIRMWARE_VERSION:
        return f"firmware version bytes: {args[0:3].hex()}"
    if command_id == constants.CMD_GET_MODEL_SERIES_ID:
        return f"model series id: 0x{args[0]:02X}"
    if command_id in (constants.CMD_GET_CONNECTION_PASSWORD,
                      constants.CMD_SET_CONNECTION_PASSWORD):
        return f"password: {_password_str(args)!r}"
    if command_id in (constants.CMD_GET_DEVICE_NAME, constants.CMD_SET_DEVICE_NAME):
        return f"device name: {_name_str(args)!r}"
    if command_id == constants.CMD_RTC_TIME_CALIBRATION:
        return f"rtc args echoed: {args[0:7].hex()}"
    return f"args: {args.hex()}"


async def probe(client: BrymenbleClient, label: str, command_id, args: bytes = b"") -> Optional[CommandResponse]:
    """Run one send_command, print raw + parsed result, return the response."""
    print(f"\n--- {label} ---")
    try:
        resp = await client.send_command(command_id, args)
    except CommandError as exc:
        print(f"  FAILED: {exc}")
        print(f"  failure frame args: {exc.response.args.hex()}")
        FAILED_STEPS.append(label)
        return None
    except ConnectionError as exc:
        print(f"  ERROR: {exc}")
        FAILED_STEPS.append(label)
        return None
    print(f"  OK command=0x{resp.command_id:04X} crc_ok={resp.crc_ok}")
    print(f"  args: {resp.args.hex()}")
    print(f"  {_decode(resp.args, command_id)}")
    return resp


async def probe_rtc(client: BrymenbleClient) -> None:
    """Run the SDK's sync_rtc() (RTC Time Calibration) and print the result."""
    # The 0x0010 command has no sub-second field, so trim microseconds.
    print(f"\n--- RTC Time Calibration (0x0010) -> "
          f"{TEST_RTC.replace(microsecond=0)} (via sync_rtc) ---")
    try:
        resp = await client.sync_rtc(TEST_RTC)
    except CommandError as exc:
        print(f"  FAILED: {exc}")
        FAILED_STEPS.append("RTC Time Calibration (0x0010)")
        return
    except ConnectionError as exc:
        print(f"  ERROR: {exc}")
        FAILED_STEPS.append("RTC Time Calibration (0x0010)")
        return
    print(f"  OK command=0x{resp.command_id:04X} crc_ok={resp.crc_ok}")
    print(f"  args: {resp.args.hex()}")
    print(f"  {_decode(resp.args, resp.command_id)}")


async def confirm_rtc(client: BrymenbleClient) -> None:
    """Wait for the next stream frame and print the meter's reported clock."""
    print("\n--- Confirm RTC (next stream frame) ---")
    frame = await client.wait_frame(timeout=3)
    if frame is None:
        print("  no frame within 3s — cannot confirm the meter's clock yet")
        FAILED_STEPS.append("Confirm RTC (no stream frame within 3s)")
        return
    # frame is a parsers.StreamFrame (not a tuple) — use its fields directly.
    readings = frame.readings
    r = readings[0] if readings else None
    if r is None:
        print("  frame received but first reading packet is empty")
        FAILED_STEPS.append("Confirm RTC (empty reading packet)")
        return
    rtc = r.rtc
    print(f"  Device Time: {rtc.isoformat()}")
    # Assert the meter adopted our time (bit-packed layout round-trip). The
    # meter takes ~0.5s to register the new RTC and keeps ticking, so allow a
    # small skew; ms is ignored (the meter doesn't preserve sub-second
    # precision). A bit-order bug (e.g. hour 20 read as 5) is a ~15h delta and
    # is caught well beyond the tolerance.
    read_back = datetime(rtc.year, rtc.month, rtc.date,
                         rtc.hour, rtc.minute, rtc.second)
    delta = abs((read_back - TEST_RTC.replace(microsecond=0)).total_seconds())
    if delta > 10:
        print(f"  MISMATCH: got {read_back}, expected {TEST_RTC} "
              f"(delta {delta:.0f}s)")
        FAILED_STEPS.append("Confirm RTC (time mismatch)")


async def main(mac: str, password: str) -> int:
    print(f"Connecting to {mac} (password {password!r})...")
    # The probe drives the RTC itself with a fixed TEST_RTC value below, so
    # keep the (now default-on) connect-time sync off here.
    async with BrymenbleClient(mac, password, sync_rtc_on_connect=False) as client:
        print("Connected and subscribed.")

        # Password verification happens on connect and is validated there — the
        # client reads the 0x8001 response in __aenter__ and fails the connect
        # on a bad password. So there's no explicit step here; the first
        # send_command below doubles as the sanity check for the command/
        # response layer.

        # 1. RTC calibration — highest-value check, done early; the fixed
        #    value makes the echoed args + subsequent Device Time easy to
        #    compare by eye. Uses the SDK's sync_rtc() so the probe exercises
        #    the real library path.
        await probe_rtc(client)
        # The meter echoes the calibration command immediately, but its RTC
        # needs a moment to register before the new time shows up in reading
        # packets.
        await asyncio.sleep(0.5)
        await confirm_rtc(client)

        # 2-5. Read-only info.
        await probe(client, "Get BLE Firmware Version (0x0004)",
                    constants.CMD_GET_FIRMWARE_VERSION)
        await probe(client, "Get Model Series ID (0x0116)",
                    constants.CMD_GET_MODEL_SERIES_ID)
        await probe(client, "Get Connection Password (0x0141)",
                    constants.CMD_GET_CONNECTION_PASSWORD)
        resp_name = await probe(client, "Get Device Name (0x0143)",
                                constants.CMD_GET_DEVICE_NAME)
        original_name = None
        if resp_name is not None:
            original_name = _name_str(resp_name.args)

        # 6-9. Mutations + confirms, then revert to the captured originals.
        # try/finally guarantees the revert runs even if a command fails.
        print("\n=== Mutating meter state (password/name) — will revert ===")
        try:
            await probe(client, f"Set Connection Password (0x0140) -> {TEST_PASSWORD!r}",
                        constants.CMD_SET_CONNECTION_PASSWORD,
                        bytes(int(ch) for ch in TEST_PASSWORD))
            await probe(client, f"Set Device Name (0x0142) -> {TEST_DEVICE_NAME!r}",
                        constants.CMD_SET_DEVICE_NAME, TEST_DEVICE_NAME.encode())
            resp_pwd = await probe(client, "Get Connection Password (0x0141) — confirm",
                                   constants.CMD_GET_CONNECTION_PASSWORD)
            resp_name = await probe(client, "Get Device Name (0x0143) — confirm",
                                    constants.CMD_GET_DEVICE_NAME)
            if resp_pwd is not None:
                _expect_equal(_password_str(resp_pwd.args), TEST_PASSWORD,
                              "Set Connection Password")
            if resp_name is not None:
                _expect_equal(_name_str(resp_name.args), TEST_DEVICE_NAME,
                              "Set Device Name")
        finally:
            print("\n=== Reverting password/name to original state ===")
            await probe(client, f"Set Connection Password (0x0140) -> {password!r}",
                        constants.CMD_SET_CONNECTION_PASSWORD,
                        bytes(int(ch) for ch in password))
            if original_name:
                await probe(client, f"Set Device Name (0x0142) -> {original_name!r}",
                            constants.CMD_SET_DEVICE_NAME, original_name.encode())
            else:
                print("  SKIP name revert: original name unknown (Get Device Name failed)")

        print("\n=== Summary ===")
        if FAILED_STEPS:
            print(f"{len(FAILED_STEPS)} failed step(s):")
            for step in FAILED_STEPS:
                print(f"  - {step}")
            return 1
        print("All steps passed.")
        return 0


if __name__ == "__main__":
    mac = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAC
    password = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PASSWORD
    try:
        sys.exit(asyncio.run(main(mac, password)))
    except KeyboardInterrupt:
        print("\nProbe aborted.")
        sys.exit(130)
