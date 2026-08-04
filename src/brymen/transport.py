"""BLE transport: connect to a BM78xBT meter, authenticate, and stream frames."""

import asyncio
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
    ):
        self.mac_address = mac_address
        self.password = password
        self.command_char_uuid = command_char_uuid
        self.notify_char_uuid = notify_char_uuid
        self._bleak: Optional[BleakClient] = None
        self._queue: Optional[asyncio.Queue] = None

    async def __aenter__(self) -> "BrymenClient":
        self._queue = asyncio.Queue(maxsize=1)
        self._bleak = BleakClient(self.mac_address)
        await self._bleak.connect()

        auth_packet = commands.build_verify_password_packet(
            self.mac_address, self.password
        )
        await self._bleak.write_gatt_char(
            self.command_char_uuid, auth_packet, response=True
        )
        await asyncio.sleep(0.5)

        await self._bleak.start_notify(self.notify_char_uuid, self._on_notify)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._bleak is not None:
            try:
                await self._bleak.stop_notify(self.notify_char_uuid)
            finally:
                await self._bleak.disconnect()
        self._bleak = None
        self._queue = None

    def _on_notify(self, sender: int, data: bytearray) -> None:
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
