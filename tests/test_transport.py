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
    # These transport tests exercise auth/notify/watchdog behavior, not RTC
    # sync; keep the SDK's now-default-on RTC sync off unless a test asks.
    kwargs.setdefault("sync_rtc_on_connect", False)
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


def test_connect_failure_mentions_single_connection():
    # A failed connect (identical to "meter already connected elsewhere" on
    # the 1:1 BLE link) must hint that only one connection is allowed.
    async def _run():
        c = make_client(FakeBleak(hang_connect=True), connect_timeout=0.05)
        with pytest.raises(ConnectionError, match="only ONE connection"):
            await c.ensure_connected(retries=1)
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
    """RTC sync on connect is the SDK default (no flag needed)."""
    async def _run():
        fake = FakeBleak([auth_ok(), rtc_ok()])
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake)
        c._bleak = fake
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
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         sync_rtc_on_connect=False)
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
                         connect_timeout=0.5, sync_rtc_on_connect=False)
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
                         connect_timeout=0.5, sync_rtc_on_connect=False)
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


# --- read_stream --------------------------------------------------------------

def _push(c, frame=None):
    """Queue a frame for the client's stream (works across reconnects)."""
    q = c._queue
    if q is None:
        q = asyncio.Queue(maxsize=1)
        c._queue = q
    q.put_nowait(frame if frame is not None else StreamFrame(info=None, readings=[]))


class FailSecondConnect(FakeBleak):
    """A FakeBleak whose connect() fails from the second call on."""

    def __init__(self, responses=None):
        super().__init__(responses)
        self._connects = 0

    async def connect(self):
        self._connects += 1
        if self._connects >= 2:
            raise ConnectionError("meter powered off")
        self.connected = True


def test_read_stream_yields_frames():
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        await c._connect()
        got = []
        done = asyncio.Event()

        async def consumer():
            async for frame in c.read_stream(
                no_data_timeout=0.02, link_down_grace=0,
            ):
                got.append(frame)
                if len(got) == 3:
                    done.set()
                    return

        t = asyncio.ensure_future(consumer())
        for _ in range(3):
            _push(c)
            await asyncio.sleep(0.01)
        await asyncio.wait_for(done.wait(), timeout=2)
        await t
        assert len(got) == 3
    run(_run())


def test_read_stream_waits_out_pause_no_reconnect():
    """A data gap with the link up is a pause: waited out, never reconnected."""
    async def _run():
        c = make_client(FakeBleak([auth_ok()]))
        await c._connect()
        pauses = []
        got = []
        done = asyncio.Event()

        async def consumer():
            async for frame in c.read_stream(
                no_data_timeout=0.02, link_down_grace=0, retries=2,
                on_pause=lambda: pauses.append(1),
            ):
                got.append(frame)
                if len(got) == 2:
                    done.set()
                    return

        t = asyncio.ensure_future(consumer())
        _push(c)
        await asyncio.sleep(0.05)            # gap -> pause detected
        assert pauses == [1]                 # on_pause fired exactly once
        assert c.is_connected                # link up -> no reconnect
        _push(c)
        await asyncio.wait_for(done.wait(), timeout=2)
        await t
        assert len(got) == 2
        assert pauses == [1]                 # still one notice for the whole gap
    run(_run())


def test_read_stream_reconnects_on_link_down():
    async def _run():
        fake = FakeBleak([auth_ok(), auth_ok()])   # initial + reconnect
        c = make_client(fake)
        await c._connect()
        events = []
        got = []
        done = asyncio.Event()

        async def consumer():
            async for frame in c.read_stream(
                no_data_timeout=0.02, link_down_grace=0,
                on_lost=lambda reason: events.append(("lost", reason)),
                on_reconnected=lambda: events.append(("reconnected",)),
            ):
                got.append(frame)
                if len(got) == 2:
                    done.set()
                    return

        t = asyncio.ensure_future(consumer())
        _push(c)
        await asyncio.sleep(0.03)
        await fake.disconnect()              # link drops (power-off)
        # Reconnect takes ~0.5s (the SDK settles briefly after auth); poll.
        for _ in range(300):
            if ("reconnected",) in events:
                break
            await asyncio.sleep(0.01)
        assert ("lost", "link_down") in events
        assert ("reconnected",) in events
        _push(c)                             # new queue after reconnect
        await asyncio.wait_for(done.wait(), timeout=2)
        await t
        assert len(got) == 2
    run(_run())


def test_read_stream_grace_absorbs_link_blip():
    """A link drop that recovers within the grace window must NOT reconnect."""
    async def _run():
        fake = FakeBleak([auth_ok()])
        c = make_client(fake)
        await c._connect()
        events = []

        async def consumer():
            async for _frame in c.read_stream(
                no_data_timeout=0.02, link_down_grace=0.1, retries=1,
                on_lost=lambda reason: events.append(reason),
            ):
                pass

        t = asyncio.ensure_future(consumer())
        _push(c)
        await asyncio.sleep(0.03)
        await fake.disconnect()              # blip
        await asyncio.sleep(0.05)
        fake.connected = True                # link recovers within grace
        await asyncio.sleep(0.15)
        assert events == []                  # never decided it was lost
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    run(_run())


def test_read_stream_pause_cap_forces_reconnect():
    """Link-up silence longer than pause_cap is treated as lost."""
    async def _run():
        fake = FakeBleak([auth_ok()] * 8)
        c = make_client(fake)
        await c._connect()
        events = []

        async def consumer():
            async for _frame in c.read_stream(
                no_data_timeout=0.02, link_down_grace=0, pause_cap=0.05,
                on_lost=lambda reason: events.append(("lost", reason)),
                on_reconnected=lambda: events.append(("reconnected",)),
            ):
                pass

        t = asyncio.ensure_future(consumer())
        _push(c)
        await asyncio.sleep(0.03)
        # Link stays up; past pause_cap the SDK forces a reconnect (takes
        # ~0.5s to complete) — poll for the callbacks.
        for _ in range(300):
            if ("reconnected",) in events:
                break
            await asyncio.sleep(0.01)
        assert ("lost", "pause_cap") in events
        assert ("reconnected",) in events
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
    run(_run())


def test_read_stream_raises_when_bounded_retries_exhausted():
    async def _run():
        c = make_client(FailSecondConnect([auth_ok()]))
        await c._connect()
        _push(c)
        it = c.read_stream(
            no_data_timeout=0.02, link_down_grace=0,
            retries=1, retry_interval=0,
        ).__aiter__()
        first = await it.__anext__()         # yields the queued frame
        assert first is not None
        await c._bleak.disconnect()          # link drops; reconnect fails twice
        with pytest.raises(ConnectionError):
            await it.__anext__()
    run(_run())


def test_read_stream_connects_fresh_client():
    async def _run():
        fake = FakeBleak([auth_ok()])
        c = BrymenClient(MAC, "0000", bleak_factory=lambda mac: fake,
                         sync_rtc_on_connect=False)
        got = []
        done = asyncio.Event()

        async def consumer():
            async for frame in c.read_stream(no_data_timeout=0.02, link_down_grace=0):
                got.append(frame)
                done.set()
                return

        t = asyncio.ensure_future(consumer())
        for _ in range(50):
            if fake.connected:
                break
            await asyncio.sleep(0.01)
        assert fake.connected                # read_stream auto-connected
        _push(c)
        await asyncio.wait_for(done.wait(), timeout=2)
        await t
        assert len(got) == 1
    run(_run())
