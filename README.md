# brymenble

> **⚠️ Unofficial.** This is an independent, community-developed SDK. It is
> **not affiliated with, endorsed by, or sponsored by** Brymen Technology
> Co., Ltd. "Brymen" and the device model names are trademarks of their
> respective owners.

Open-source Python SDK for the **Brymen BM78xBT** Bluetooth Low Energy
multimeter. This is the monorepo for both the SDK itself (`src/brymen/`) and a
sample console app (`examples/`) that displays the meter output.

## SDK

The SDK is a pip-installable package that handles the whole protocol:

- `brymen.constants` — protocol constants and lookup tables
- `brymen.crc` — CRC-16 (poly 0xA001) used by the protocol
- `brymen.commands` — building command packets (auth, etc.)
- `brymen.parsers` — turning raw packets/frames into `InfoPacket`, `ReadingPacket`, `RtcTime`
- `brymen.formatter` — converting a parsed reading into a display string (`"123.45 V"`)
- `brymen.transport` — `BrymenClient`: connect, authenticate, subscribe, and stream parsed frames

### Install

```bash
pip install -e .          # from the repo root (installs `brymenble` + `bleak`)
```

### Minimal use

```python
import asyncio
from brymen import BrymenClient, DEFAULT_PASSWORD

async def main():
    async with BrymenClient("00:11:22:33:44:55", DEFAULT_PASSWORD) as client:
        async for info, readings in client:
            print(info.mac_str, readings[0])

asyncio.run(main())
```

## Sample console app

`examples/console.py` is a thin program built on the SDK: it connects to a
meter and prints the output, either continuously (auto mode) or on demand
(manual mode).

```bash
python examples/console.py [MAC] [PASSWORD] [--manual]
```

## Tests

Offline tests (no meter required):

```bash
.venv\Scripts\python.exe -m pytest
```

`tools/capture.py` captures real frames from a meter into
`tests/fixtures/captures.json`. That file is gitignored and kept local only —
real frames embed the meter's MAC address, so it must not be committed.

## License

MIT — see [LICENSE](LICENSE).

"Brymen" and the device model names are trademarks of their respective owners;
this project is not affiliated with or endorsed by Brymen Technology Co., Ltd.
