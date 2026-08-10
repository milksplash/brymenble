"""Tests for the BLE transport layer (BrymenClient) using a fake BleakClient.

Covers connect + password auth, send_command (success/failure/timeout),
sync_rtc, reconnect, the no-data watchdog, frames() re-resolution across
reconnects, GATT timeouts, and worker-thread notification delivery — all
offline, no real hardware.
"""
import asyncio
import threading
from datetime import datetime

import pytest

from brymen import BrymenClient, CommandError, StreamFrame, commands, constants, crc
from tests.frame_builder import build_frame

MAC = "00:11:22:33:44:55"


def run(coro):
    return asyncio.run(coro)


def as_response(pkt: bytes) -> bytes:
    """Turn a command packet into a valid response packet (type 0x02)."""
    p = bytearray(pkt)
    p[3] = 0x02
    p[28:30] = crc.calculate_crc(bytes(p[2:28])).to_bytes(2, "little")
    return bytes(p)


def failure_response(failing_cmd: int, error_code: int) -> bytes:
    """Build a 0x8001 failure frame for `failing_cmd` with `error_code`."""
    args = (
        failing_cmd.to_bytes(2, "little")
        + error_code.to_bytes(2, "little")
        + b"\x00" * 10
    )
    return as_response(commands.build_command_packet(MAC, constants.CMD_FAILURE, args))


def auth_ok() -> bytes:
    return as_response(commands.build_command_packet(
        MAC, constants.CMD_VERIFY_CONNECTION_PASSWORD, bytes([0, 0, 0, 0])
    ))


def rtc_ok() -> bytes:
    return as_response(commands.build_command_packet(
        MAC, constants.CMD_RTC_TIME_CALIBRATION,
        commands.encode_rtc_time_args(datetime(2026, 1, 2, 3, 4, 5)),
    ))


class FakeBleak:
    """In-memory stand-in for bleak.BleakClient."""

    def __init__(self, responses=None, *, hang_connect=False, hang_start=False,
                 hang_stop=False, hang_disconnect=False, hang_read=False):
        self.responses = list(responses or [])
        self.hang_connect = hang_connect
        self.hang_start = hang_start
        self.hang_stop = hang_stop
        self.hang_disconnect = hang_disconnect
        self.hang_read = hang_read
        self.writes = []
        self.connected = False
        self.notify_started = False
        self.notify_stopped = False

    async def connect(self):
        if self.hang_connect:
            # Emulate bleak's winrt backend: a connect cancelled on timeout
            # raises CancelledError rather than returning quietly.
            await asyncio.sleep(10)
        self.connected = True

    async def write_gatt_char(self, uuid, data, response=True):
        self.writes.append(bytes(data))

    async def read_gatt_char(self, uuid):
        if self.hang_read:
            await asyncio.sleep(10)
        return bytearray(self.responses.pop(0))

    async def start_notify(self, *a, **k):
        if self.hang_start:
            await asyncio.sleep(10)
        self.notify_started = True

    async def stop_notify(self, *a, **k):
        if self.hang_stop:
            await asyncio.sleep(10)
        self.notify_stopped = True

    async def disconnect(self):
        if self.hang_disconnect:
            await asyncio.sleep(10)
        self.connected = False


def make_client(bleak=None, **kwargs) -> BrymenClient:
    fake = bleak if bleak is not None else FakeBleak()
    client = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake, **kwargs)
    client._bleak = fake          # so direct _connect() calls also work
    return client


# --- Connect / auth -----------------------------------------------------------

def test_connect_auth_ok():
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        await c._connect()
        assert c._bleak.connected
        assert c._bleak.notify_started
        assert len(c._bleak.writes) == 1          # verify-password packet
    run(_run())


def test_is_connected():
    """is_connected tracks the BLE link, independent of data flow."""
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        assert c.is_connected is False           # not connected yet
        await c._connect()
        assert c.is_connected is True            # link up
        await c._bleak.disconnect()
        assert c.is_connected is False           # link dropped (power-off)
    run(_run())


def test_connect_timeout_raises_connection_error():
    # Regression test: a connect cancelled by the timeout must surface as
    # ConnectionError, not a bare asyncio.CancelledError.
    async def _run():
        c = make_client(FakeBleak(hang_connect=True), connect_timeout=0.05)
        with pytest.raises(ConnectionError) as ei:
            await c._connect()
        assert "timed out" in str(ei.value)
    run(_run())


def test_connect_external_cancel_propagates():
    # A genuine external cancellation (e.g. Ctrl+C) must still propagate as
    # CancelledError — the timeout handling must not swallow it.
    async def _run():
        c = make_client(FakeBleak(hang_connect=True), connect_timeout=10)
        task = asyncio.ensure_future(c._connect())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(_run())


def test_connect_wrong_password_raises():
    async def _run():
        c = make_client(FakeBleak([failure_response(
            constants.CMD_VERIFY_CONNECTION_PASSWORD, 3)]))
        with pytest.raises(CommandError) as ei:
            await c._connect()
        assert "Invalid password" in str(ei.value)
    run(_run())


def test_connect_sync_rtc_on_connect():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), rtc_ok()]), sync_rtc_on_connect=True)
        await c._connect()
        assert len(c._bleak.writes) == 2          # verify-password + rtc
    run(_run())


def test_connect_start_notify_timeout():
    async def _run():
        c = make_client(FakeBleak([auth_ok()], hang_start=True), gatt_timeout=0.05)
        with pytest.raises(ConnectionError) as ei:
            await c._connect()
        assert "start_notify" in str(ei.value)
    run(_run())


# --- send_command / sync_rtc --------------------------------------------------

def test_send_command_success():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), as_response(
            commands.build_command_packet(MAC, constants.CMD_GET_FIRMWARE_VERSION))]))
        await c._connect()
        resp = await c.send_command(constants.CMD_GET_FIRMWARE_VERSION)
        assert resp.command_id == constants.CMD_GET_FIRMWARE_VERSION
        assert not resp.is_failure
    run(_run())


def test_send_command_failure_raises():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), failure_response(
            constants.CMD_GET_FIRMWARE_VERSION, 6)]))
        await c._connect()
        with pytest.raises(CommandError) as ei:
            await c.send_command(constants.CMD_GET_FIRMWARE_VERSION)
        assert "Insufficient permissions" in str(ei.value)
    run(_run())


def test_send_command_timeout():
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        await c._connect()
        c._bleak.hang_read = True
        with pytest.raises(ConnectionError):
            await c.send_command(constants.CMD_GET_FIRMWARE_VERSION, timeout=0.05)
    run(_run())


def test_sync_rtc_sends_rtc_command():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), rtc_ok()]))
        await c._connect()
        resp = await c.sync_rtc(datetime(2026, 1, 2, 3, 4, 5))
        assert resp.command_id == constants.CMD_RTC_TIME_CALIBRATION
        assert len(c._bleak.writes) == 2
    run(_run())


# --- Reconnect / watchdog / frames --------------------------------------------

def test_reconnect_reruns_connect():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), auth_ok()]))
        await c._connect()
        await c.reconnect()
        assert c._bleak.notify_started
        assert len(c._bleak.writes) == 2
    run(_run())


def test_wait_frame_timeout_returns_none():
    async def _run():
        c = make_client()
        c._queue = asyncio.Queue(maxsize=1)
        assert await c.wait_frame(timeout=0.02) is None
    run(_run())


def test_seconds_since_last_frame():
    c = make_client()
    assert c.seconds_since_last_frame() is None
    c._last_notify = 0.0
    assert c.seconds_since_last_frame() > 5


def test_frames_follow_queue_across_reconnect():
    async def _run():
        c = make_client()
        c._queue = asyncio.Queue(maxsize=1)
        c._queue.put_nowait(StreamFrame(info=None, readings=[]))
        it = c.frames().__aiter__()
        assert (await it.__anext__()).info is None
        c._queue = asyncio.Queue(maxsize=1)
        c._queue.put_nowait(StreamFrame(info=None, readings=[]))
        assert (await it.__anext__()).info is None
    run(_run())


def test_notify_from_worker_thread_lands_in_queue():
    async def _run():
        c = make_client()
        c._loop = asyncio.get_running_loop()
        c._queue = asyncio.Queue(maxsize=1)
        t = threading.Thread(target=lambda: c._on_notify(0, bytearray(build_frame())))
        t.start()
        t.join()
        frame = await asyncio.wait_for(c.wait_frame(timeout=2), timeout=2)
        assert isinstance(frame, StreamFrame)
        assert frame.info.mac_str == MAC
    run(_run())


# --- ensure_connected / close ------------------------------------------------

class FailingConnect(FakeBleak):
    """A FakeBleak whose connect() fails the first ``fail_count`` times."""

    def __init__(self, responses=None, fail_count=0):
        super().__init__(responses)
        self.fail_count = fail_count

    async def connect(self):
        if self.fail_count > 0:
            self.fail_count -= 1
            raise ConnectionError("transient connect failure")
        self.connected = True


def test_ensure_connected_connects_fresh_client():
    async def _run():
        fake = FakeBleak([auth_ok()])
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake)
        await c.ensure_connected()
        assert c._bleak.connected
        assert c._bleak.notify_started
        assert len(c._bleak.writes) == 1
    run(_run())


def test_ensure_connected_reconnects_existing_client():
    async def _run():
        c = make_client(FakeBleak([auth_ok(), auth_ok()]))
        await c._connect()
        await c.ensure_connected(retries=1)
        assert c._bleak.notify_started
        assert len(c._bleak.writes) == 2
    run(_run())


def test_ensure_connected_retries_then_succeeds():
    async def _run():
        fake = FailingConnect([auth_ok()], fail_count=2)
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        retried = []
        await c.ensure_connected(retries=3, retry_interval=0.01,
                                 on_retry=lambda a, m, e: retried.append((a, m)))
        assert c._bleak is not None and c._bleak.connected
        assert c._bleak.notify_started
        assert retried == [(1, 3), (2, 3)]
    run(_run())


def test_ensure_connected_gives_up_after_retries():
    async def _run():
        fake = FailingConnect([auth_ok()], fail_count=99)
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        retried = []
        with pytest.raises(ConnectionError) as ei:
            await c.ensure_connected(retries=3, retry_interval=0.01,
                                     on_retry=lambda a, m, e: retried.append((a, m)))
        assert "after 3 attempt(s)" in str(ei.value)
        assert retried == [(1, 3), (2, 3)]
        assert c._bleak is None   # no half-open connection leaked
    run(_run())


def test_ensure_connected_does_not_retry_bad_password():
    # A CommandError (bad password) is terminal — must not be retried.
    async def _run():
        fake = FakeBleak([failure_response(
            constants.CMD_VERIFY_CONNECTION_PASSWORD, 3)])
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        retried = []
        with pytest.raises(CommandError) as ei:
            await c.ensure_connected(retries=3, retry_interval=0.01,
                                     on_retry=lambda a, m, e: retried.append((a, m)))
        assert "Invalid password" in str(ei.value)
        assert retried == []
    run(_run())


def test_ensure_connected_infinite_retries_then_succeeds():
    # retries=None keeps going past the bounded default (3) until the meter
    # comes back.
    async def _run():
        fake = FailingConnect([auth_ok()], fail_count=5)
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        retried = []
        await c.ensure_connected(
            retries=None, retry_interval=0.01,
            on_retry=lambda a, m, e: retried.append((a, m)))
        assert c._bleak is not None and c._bleak.connected
        assert c._bleak.notify_started
        assert retried == [(1, None), (2, None), (3, None), (4, None), (5, None)]
    run(_run())


def test_ensure_connected_infinite_retries_bad_password_terminal():
    # Even with retries=None, a CommandError (bad password) is terminal.
    async def _run():
        fake = FakeBleak([failure_response(
            constants.CMD_VERIFY_CONNECTION_PASSWORD, 3)])
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        retried = []
        with pytest.raises(CommandError):
            await c.ensure_connected(
                retries=None, retry_interval=0.01,
                on_retry=lambda a, m, e: retried.append((a, m)))
        assert retried == []
    run(_run())


def test_ensure_connected_infinite_retries_is_cancellable():
    # A permanently-failing meter + retries=None stops cleanly on cancel.
    async def _run():
        fake = FailingConnect([auth_ok()], fail_count=999)
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         connect_timeout=0.5)
        task = asyncio.ensure_future(
            c.ensure_connected(retries=None, retry_interval=0.01))
        await asyncio.sleep(0.05)   # let it retry a few times
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(_run())


def test_close_is_idempotent():
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        await c._connect()
        await c.close()
        assert c._bleak is None
        await c.close()   # second call is a no-op
    run(_run())


# --- Cleanup ------------------------------------------------------------------

def test_cleanup_swallows_gatt_hangs():
    async def _run():
        c = make_client(FakeBleak(hang_stop=True, hang_disconnect=True), gatt_timeout=0.05)
        await c.__aexit__(None, None, None)
        assert c._bleak is None
    run(_run())
