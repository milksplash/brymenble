"""BLE transport: connect to a BM78xBT meter, authenticate, and stream frames."""

import asyncio
import time
from typing import AsyncIterator, List, Optional, Tuple

from bleak import BleakClient

from . import commands, parsers

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"
NOTIFY_CHAR_UUID = "0003cdd5-0000-1000-8000-00805f9b0131"
DEFAULT_PASSWORD = "0000"

# A parsed stream frame: the device-info packet plus up to 4 reading packets.
# Empty/invalid trailing reading packets parse to None.
Frame = Tuple[parsers.InfoPacket, List[Optional[parsers.ReadingPacket]]]


class BrymenClient:
    """Async context manager streaming parsed frames from a BM78xBT meter.

    Connects, authenticates (Verify Password), and subscribes to notifications
    on entry; disconnects on exit. Iterate it to receive parsed frames::

        async with BrymenClient(mac, password) as client:
            async for info, readings in client:
                ...

    ``latest()`` returns the most recent frame without blocking (for
    on-demand/manual display).
    """

    def __init__(
        self,
        mac_address: str,
        password: str = DEFAULT_PASSWORD,
        command_char_uuid: str = COMMAND_CHAR_UUID,
        notify_char_uuid: str = NOTIFY_CHAR_UUID,
        connect_timeout: float = 10.0,
    ):
        self.mac_address = mac_address
        self.password = password
        self.command_char_uuid = command_char_uuid
        self.notify_char_uuid = notify_char_uuid
        self.connect_timeout = connect_timeout
        self._bleak: Optional[BleakClient] = None
        self._queue: Optional[asyncio.Queue] = None
        self._last_notify: Optional[float] = None

    async def __aenter__(self) -> "BrymenClient":
        self._queue = asyncio.Queue(maxsize=1)
        self._bleak = BleakClient(self.mac_address)
        await self._connect_with_cleanup()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._bleak is not None:
            try:
                await self._bleak.stop_notify(self.notify_char_uuid)
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

    async def _connect(self) -> None:
        """Establish the BLE link, verify the password, and subscribe."""
        self._last_notify = None
        await asyncio.wait_for(
            self._bleak.connect(), timeout=self.connect_timeout
        )
        auth_packet = commands.build_verify_password_packet(
            self.mac_address, self.password
        )
        await self._bleak.write_gatt_char(
            self.command_char_uuid, auth_packet, response=True
        )
        await asyncio.sleep(0.5)
        await self._bleak.start_notify(self.notify_char_uuid, self._on_notify)

    async def reconnect(self) -> None:
        """Tear down the current connection and re-establish it, including the
        password-verification procedure. Raises ConnectionError on failure."""
        await self._close()
        self._queue = asyncio.Queue(maxsize=1)
        self._bleak = BleakClient(self.mac_address)
        await self._connect_with_cleanup()

    async def wait_frame(self, timeout: Optional[float] = None) -> Optional[Frame]:
        """Wait for the next parsed frame, or return None if `timeout` elapses.

        A timeout (e.g. no BLE notification for a while) typically means the
        meter powered off.
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
                await self._bleak.disconnect()
            except Exception:
                pass
        self._bleak = None
        self._queue = None

    def _on_notify(self, sender: int, data: bytearray) -> None:
        self._last_notify = time.monotonic()
        info, readings = parsers.parse_stream_frame(bytes(data))
        if info is None:
            return
        queue = self._queue
        if queue is None:
            return
        # Keep only the latest frame: overwrite any pending one.
        try:
            queue.put_nowait((info, readings))
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait((info, readings))

    def latest(self) -> Optional[Frame]:
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
        queue = self._queue
        if queue is None:
            raise RuntimeError("BrymenClient not connected (use 'async with')")
        while True:
            yield await queue.get()

    def __aiter__(self) -> AsyncIterator[Frame]:
        return self.frames().__aiter__()
