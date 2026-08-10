"""BLE transport: connect to a BM78xBT meter, authenticate, and stream frames."""

import asyncio
import contextlib
import logging
import time
from datetime import datetime
from typing import AsyncIterator, Callable, Optional, Union

from bleak import BleakClient

from . import commands, constants, parsers

log = logging.getLogger(__name__)

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"
NOTIFY_CHAR_UUID = "0003cdd5-0000-1000-8000-00805f9b0131"
DEFAULT_PASSWORD = "0000"

# A parsed stream frame: the device-info packet plus up to 4 reading packets
# (empty/invalid trailing readings are None). ``StreamFrame`` lives in
# parsers.py alongside the other parsed dataclasses.
Frame = parsers.StreamFrame


class CommandError(Exception):
    """Raised when the meter replies to a command with a 0x8001 failure frame."""

    def __init__(self, response: "parsers.CommandResponse"):
        self.response = response
        super().__init__(
            f"Command 0x{response.failed_command_id:04X} failed: "
            f"{response.error_message or 'unknown error'}"
        )


class BrymenClient:
    """Async context manager streaming parsed frames from a BM78xBT meter.

    Connects, authenticates (Verify Password), and subscribes to notifications
    on entry; disconnects on exit. Iterate it to receive parsed frames::

        async with BrymenClient(mac, password) as client:
            async for frame in client:
                print(frame.info.mac_str, frame.readings)

    Each yielded value is a ``parsers.StreamFrame`` (``info`` + up to 4
    ``readings``). ``latest_frame()`` returns the most recent frame without
    blocking (for on-demand/manual display).

    ``ensure_connected()`` connects (or reconnects) with a bounded retry
    policy, and ``close()`` is a public, idempotent disconnect — both are safe
    to use outside ``async with``.
    """

    def __init__(
        self,
        mac_address: str,
        password: str = DEFAULT_PASSWORD,
        command_char_uuid: str = COMMAND_CHAR_UUID,
        notify_char_uuid: str = NOTIFY_CHAR_UUID,
        connect_timeout: float = 10.0,
        sync_rtc_on_connect: bool = False,
        gatt_timeout: float = 5.0,
        bleak_factory: Optional[Callable[[str], BleakClient]] = None,
        notify_gap_log_threshold: float = 2.0,
    ):
        self.mac_address = mac_address
        self.password = password
        self.command_char_uuid = command_char_uuid
        self.notify_char_uuid = notify_char_uuid
        self.connect_timeout = connect_timeout
        self.sync_rtc_on_connect = sync_rtc_on_connect
        self.gatt_timeout = gatt_timeout
        # Log notification gaps >= this many seconds at DEBUG (with the
        # reading's function) so the meter's pause cadence — e.g. during a
        # function switch — can be characterised on real hardware. 0 disables.
        self.notify_gap_log_threshold = notify_gap_log_threshold
        # Injectable BleakClient factory (test seam; defaults to real bleak).
        self._bleak_factory: Callable[[str], BleakClient] = bleak_factory or BleakClient
        self._bleak: Optional[BleakClient] = None
        self._queue: Optional[asyncio.Queue] = None
        self._last_notify: Optional[float] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def __aenter__(self) -> "BrymenClient":
        self._queue = asyncio.Queue(maxsize=1)
        self._bleak = self._bleak_factory(self.mac_address)
        await self._connect_with_cleanup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self) -> None:
        """Disconnect and release resources (idempotent, safe after a failed
        connect). Stops notifications, then tears down the BLE link."""
        if self._bleak is not None:
            try:
                await self._gatt_with_timeout(
                    "stop_notify",
                    self._bleak.stop_notify(self.notify_char_uuid),
                    self.gatt_timeout,
                )
            except Exception:
                pass
        await self._close()

    async def _connect_with_cleanup(self) -> None:
        """Run _connect, converting timeouts to ConnectionError and cleaning
        up on any failure so no half-open connection leaks."""
        try:
            await self._connect()
        except asyncio.TimeoutError:
            await self._close()
            raise ConnectionError(
                f"Connection to {self.mac_address} timed out after "
                f"{self.connect_timeout:.0f}s"
            ) from None
        except Exception:
            # Don't leak a half-open connection if entry fails partway.
            await self._close()
            raise

    async def _gatt_with_timeout(
        self, what: str, coro, timeout: Optional[float]
    ) -> None:
        """Await a GATT coroutine with a timeout, raising ConnectionError.

        Uses asyncio.wait (not wait_for) so the timeout doesn't inject a
        cancellation into the coroutine — some bleak backends surface that as a
        bare CancelledError instead of a clean timeout (see _connect).
        """
        task = asyncio.ensure_future(coro)
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if task not in done:
                raise ConnectionError(
                    f"{what} to {self.mac_address} timed out after "
                    f"{timeout:.0f}s"
                )
            task.result()   # re-raise real failures
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(BaseException):
                    await task

    async def _connect(self) -> None:
        """Establish the BLE link, verify the password, and subscribe."""
        self._last_notify = None
        self._loop = asyncio.get_running_loop()

        # Timeout the connect WITHOUT injecting a cancellation into bleak: its
        # winrt backend raises a bare CancelledError when connect() is cancelled
        # mid-flight (which asyncio.wait_for does on timeout), and that would
        # escape as CancelledError instead of our ConnectionError. asyncio.wait
        # leaves the task pending, so we cancel it ourselves and swallow the
        # result; a genuine external cancellation still propagates.
        connect_task = asyncio.ensure_future(self._bleak.connect())
        try:
            done, _ = await asyncio.wait(
                {connect_task}, timeout=self.connect_timeout
            )
            if connect_task not in done:
                raise ConnectionError(
                    f"Connection to {self.mac_address} timed out after "
                    f"{self.connect_timeout:.0f}s"
                )
            connect_task.result()   # re-raise real connect failures
        finally:
            if not connect_task.done():
                connect_task.cancel()
                with contextlib.suppress(BaseException):
                    await connect_task
        # Verify the connection password AND read the meter's response. A
        # 0x8001 failure frame (e.g. wrong password) raises CommandError here,
        # so a bad password fails the connect with a clear reason instead of
        # proceeding silently.
        if len(self.password) != 4 or not self.password.isdigit():
            raise ValueError("Password must be a 4-digit string")
        await self.send_command(
            constants.CMD_VERIFY_CONNECTION_PASSWORD,
            bytes(int(ch) for ch in self.password),
        )
        # TODO(low): Verify device identity after auth. The only trust anchors
        # are the 4-digit password (default "0000") and the MAC — and BLE MACs
        # are spoofable, so a malicious device that knows the password could
        # pretend to be the meter and feed fake readings. Probe
        # CMD_GET_MODEL_SERIES_ID (0x0116) / CMD_GET_FIRMWARE_VERSION (0x0004)
        # / CMD_GET_DEVICE_NAME (0x0143) after connecting and fail the connect
        # if the replies don't match the expected meter.
        # The meter has no RTC battery, so its clock resets on power-off.
        # Optionally re-sync it here (also runs on every reconnect).
        if self.sync_rtc_on_connect:
            await self.sync_rtc()
        await asyncio.sleep(0.5)
        await self._gatt_with_timeout(
            "start_notify",
            self._bleak.start_notify(self.notify_char_uuid, self._on_notify),
            self.gatt_timeout,
        )

    async def reconnect(self) -> None:
        """Tear down the current connection and re-establish it, including the
        password-verification procedure. Raises ConnectionError on failure."""
        await self._close()
        self._queue = asyncio.Queue(maxsize=1)
        self._bleak = self._bleak_factory(self.mac_address)
        await self._connect_with_cleanup()

    async def ensure_connected(
        self,
        retries: Optional[int] = 3,
        retry_interval: float = 5.0,
        on_retry: Optional[Callable[[int, Optional[int], Exception], None]] = None,
    ) -> None:
        """Connect if not connected, otherwise reconnect, with a retry policy.

        Attempts up to ``retries`` times (the first attempt isn't counted as a
        retry), sleeping ``retry_interval`` seconds between attempts. Only
        ``ConnectionError``-type failures are retried — a ``CommandError``
        (e.g. wrong password) is terminal and propagates immediately.
        ``on_retry``, if given, is called as
        ``on_retry(attempt, max_retries, error)`` before each retry so callers
        can log progress without the SDK printing. Raises ConnectionError if
        all attempts fail.

        Set ``retries=None`` to retry forever. This is meant for long-running
        consumers (overlays, loggers) that must survive the meter powering
        off and come back up when it returns. In that mode ``max_retries``
        passed to ``on_retry`` is ``None``, and cancelling the task (asyncio
        ``CancelledError``) stops the loop cleanly.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                if self._bleak is None:
                    self._queue = asyncio.Queue(maxsize=1)
                    self._bleak = self._bleak_factory(self.mac_address)
                    await self._connect_with_cleanup()
                else:
                    await self.reconnect()
                return
            except (ConnectionError, asyncio.TimeoutError) as exc:
                if retries is not None and attempt >= retries:
                    raise ConnectionError(
                        f"Could not connect to {self.mac_address} after "
                        f"{retries} attempt(s): {exc}"
                    ) from exc
                if on_retry is not None:
                    on_retry(attempt, retries, exc)
                await asyncio.sleep(retry_interval)

    async def send_command(
        self,
        command_id: Union[int, bytes],
        args: bytes = b"",
        timeout: Optional[float] = 5.0,
    ) -> "parsers.CommandResponse":
        """Send a command on COMMAND_CHAR_UUID and return the parsed response.

        The meter acknowledges each command with a 32-byte response frame read
        back from the command characteristic (success echoes the command ID;
        failure is 0x8001 + an error code). Raises CommandError on a failure
        frame and ConnectionError on a transport timeout or invalid response.
        """
        if self._bleak is None:
            raise RuntimeError("BrymenClient not connected (use 'async with')")
        cmd = (
            command_id
            if isinstance(command_id, int)
            else int.from_bytes(command_id, 'little')
        )
        packet = commands.build_command_packet(self.mac_address, command_id, args)

        async def _round_trip() -> bytes:
            await self._bleak.write_gatt_char(
                self.command_char_uuid, packet, response=True
            )
            return bytes(await self._bleak.read_gatt_char(self.command_char_uuid))

        try:
            data = await asyncio.wait_for(_round_trip(), timeout=timeout)
        except asyncio.TimeoutError:
            raise ConnectionError(
                f"Command 0x{cmd:04X} to {self.mac_address} timed out "
                f"after {timeout:.0f}s"
            ) from None

        response = parsers.parse_command_response(data)
        if response is None:
            raise ConnectionError(
                f"Command 0x{cmd:04X}: invalid response from {self.mac_address}"
            )
        if response.is_failure:
            raise CommandError(response)
        return response

    async def sync_rtc(
        self, when: Optional[datetime] = None
    ) -> "parsers.CommandResponse":
        """Set the meter's RTC via the RTC Time Calibration (0x0010) command.

        The meter has no RTC battery, so its clock resets on power-off; call
        this after connecting (or set ``sync_rtc_on_connect``) to keep reading
        timestamps accurate. Defaults to the host's local time.
        """
        if self._bleak is None:
            raise RuntimeError("BrymenClient not connected (use 'async with')")
        if when is None:
            when = datetime.now()
        return await self.send_command(
            constants.CMD_RTC_TIME_CALIBRATION, commands.encode_rtc_time_args(when)
        )

    @property
    def is_connected(self) -> bool:
        """True while the BLE GATT link is up, regardless of data flow.

        This is the signal consumers should use to tell a meter that is merely
        paused — e.g. mid function-switch, link still up — from one that
        powered off (link dropped). ``wait_frame()`` timing out on its own is
        ambiguous; combine it with ``is_connected``:

        * link up + no data  -> pause, keep waiting (do NOT reconnect)
        * link down          -> powered off, reconnect

        Reads the backend's connection state live; on bleak/WinRT it updates
        asynchronously, so callers may want a small grace window after a
        services-change blip.
        """
        if self._bleak is None:
            return False
        # bleak >= 0.21 exposes ``is_connected``; the SDK's test seam
        # (FakeBleak) uses ``connected``. Accept either.
        for attr in ("is_connected", "connected"):
            try:
                return bool(getattr(self._bleak, attr))
            except AttributeError:
                continue
        return False

    async def wait_frame(self, timeout: Optional[float] = None) -> Optional[Frame]:
        """Wait for the next parsed frame, or return None if `timeout` elapses.

        A timeout alone means "no notification for a while" — it does NOT
        distinguish a function-switch pause from a power-off. Pair it with
        ``is_connected`` to decide whether to reconnect (see there).
        """
        queue = self._queue
        if queue is None:
            raise RuntimeError("BrymenClient not connected (use 'async with')")
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def seconds_since_last_frame(self) -> Optional[float]:
        """Seconds since the last BLE notification, or None if none received."""
        if self._last_notify is None:
            return None
        return time.monotonic() - self._last_notify

    async def _close(self) -> None:
        """Best-effort cleanup of any connection state."""
        if self._bleak is not None:
            try:
                await self._gatt_with_timeout(
                    "disconnect", self._bleak.disconnect(), self.gatt_timeout
                )
            except Exception:
                pass
        self._bleak = None
        self._queue = None
        self._loop = None

    def _on_notify(self, sender: int, data: bytearray) -> None:
        """bleak notification callback (NOTIFY characteristic, cdd5).

        bleak may deliver notifications on a worker thread (backend-dependent), so
        the handling is marshalled onto the event loop via ``call_soon_threadsafe``
        to keep the queue / last-notification-timestamp updates race-free with the
        async consumer (``wait_frame``, ``seconds_since_last_frame``). This is also
        safe when bleak already calls us on the loop thread.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(self._handle_notify, bytes(data))

    def _handle_notify(self, data: bytes) -> None:
        """Event-loop-side handling of one notification (see ``_on_notify``)."""
        now = time.monotonic()
        frame = parsers.parse_stream_frame(data)
        if self._last_notify is not None and self.notify_gap_log_threshold:
            gap = now - self._last_notify
            if gap >= self.notify_gap_log_threshold:
                function = "?"
                if frame is not None and frame.readings and frame.readings[0]:
                    function = frame.readings[0].function_name
                log.debug("notify gap %.1fs (function=%s)", gap, function)
        self._last_notify = now
        if frame is None or frame.info is None:
            return
        queue = self._queue
        if queue is None:
            return
        # Keep only the latest frame: overwrite any pending one.
        try:
            queue.put_nowait(frame)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(frame)

    def latest_frame(self) -> Optional[Frame]:
        """Return the most recent frame without blocking, or None if none yet."""
        queue = self._queue
        if queue is None:
            return None
        frame = None
        while True:
            try:
                frame = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        return frame

    async def frames(self) -> AsyncIterator[Frame]:
        """Async iterator yielding each parsed frame as it arrives."""
        while True:
            # Re-resolve self._queue each iteration: reconnect() replaces the
            # queue, so an iterator started before a reconnect must pick up
            # the new one (see wait_frame()).
            queue = self._queue
            if queue is None:
                raise RuntimeError("BrymenClient not connected (use 'async with')")
            yield await queue.get()

    def __aiter__(self) -> AsyncIterator[Frame]:
        return self.frames().__aiter__()
