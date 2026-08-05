
---

# BM78xBT Wireless Data Communication Protocol Specification

## 1. Advertising Packet

* **Default Size:** 20 bytes (variable based on "Device Name" length).



### Frame Structure

* **Byte [0]**: `Length` = `0x02` (Don't care)


* **Byte [1]**: `<<Flags>>` = `0x01` (Don't care)


* **Byte [2]**: `General discoverable mode` = `0x06` (Don't care)


* **Byte [3]**: `Length of <<Device Name>>` = `0x08` (Remote Changeable; Valid range: `0x02` to `0x0D`, corresponding to 1 to 12 ASCII characters)


* **Byte [4]**: `<<Device Name>> Type` = `0x09` (Don't care)


* **Bytes [5–11]**: `Device Name` ASCII characters: `'B'`, `'M'`, `'7'`, `'8'`, `'x'`, `'B'`, `'T'` (`0x42`, `0x4D`, `0x37`, `0x38`, `0x78`, `0x42`, `0x54`) (Remote Changeable)


* **Byte [12]**: `Length of Manufacturer Specific Data` = `0x07` (Fixed)


* **Byte [13]**: `<<Manufacturer Data Specific>> Type` = `0xFF` (Don't care)


* **Byte [14]**: `Manufacturer Specific Data-1` = `0x31` (Fixed)


* **Byte [15]**: `Manufacturer Specific Data-2` = `0x01` (Fixed)


* **Byte [16]**: `'B'` = `0x42` (Fixed)


* **Byte [17]**: `'M'` = `0x4D` (Fixed)


* **Byte [18]**: `Model Series ID` = `0x0B` (Fixed)


* **Byte [19]**: `Status` = `0x00` (Fixed)



---

## 2. Command / Response Packet Format

* **Fixed Packet Length:** 32 Bytes



### Frame Structure

* **Byte [0]**: `HeadByte0` = `0xFF` (HEAD)


* **Byte [1]**: `HeadByte1` = `0x01` (SOH)


* **Byte [2]**: `Packet Length` = `0x20` (32 bytes)


* **Byte [3]**: `Packet Type` = `0x01` (Command) or `0x02` (Response)


* **Byte [4]**: `Protocol Version` = `0x01`

* **Bytes [5–10]**: `MAC Address [0..5]` (BLE Device Address, extractable from any Response packet)


* **Bytes [11–12]**: `Command ID [0..1]` (See Command Table)


* **Byte [13]**: `Password Identification` = `0x01`

* **Bytes [14–27]**: `Arguments [0..13]` (Command/Response Specific Data)


* **Bytes [28–29]**: `Checksum [0..1]` (CRC-16 calculated over Bytes [2] through [27])


* **Byte [30]**: `EndByte0` = `0xFF` (HEAD)


* **Byte [31]**: `EndByte1` = `0x03` (ETX)



### CRC-16 Calculation

* **Algorithm:** Reverse CRC-16 (Polynomial: $x^{16} + x^{15} + x^2 + 1$ / `0x8005`, Initial Value: `0xFFFF`, XOR Polynomial: `0xA001`).


* **Reference C Implementation:**

```c
unsigned int crc_chk(unsigned char* data, unsigned char length) 
{
    int j;
    unsigned int reg_crc = 0xFFFF;
    while (length--) 
    { 
        reg_crc ^= *data++;
        for (j = 0; j < 8; j++) 
        { 
            if (reg_crc & 0x01) 
                reg_crc = (reg_crc >> 1) ^ 0xA001;
            else 
                reg_crc = reg_crc >> 1;
        } 
    } 
    return reg_crc;
}

```

---

## 3. BLE GATT Services & Characteristics

* **Attribute MTU Requirement:** Must be set to **185 Bytes**.


* **Primary Service UUID:** `0003CDD0-0000-1000-8000-00805F9B0131`

* **Data Notification Characteristic UUID:** `0003CDD5-0000-1000-8000-00805F9B0131`

* **Properties:** NOTIFY


* **Payload Length:** 185 Bytes


* **Descriptor:** Client Characteristic Configuration Descriptor (CCCD, UUID: `0x2902`)




* **Command Characteristic UUID:** `0003CDD4-0000-1000-8000-00805F9B0131`

* **Properties:** READ / WRITE


* **Payload Length:** 32 Bytes





---

## 4. Command Set Specification

### Error Codes (`Arg[3:2]` in Failure Responses)

* `0`: Checksum error


* `1`: Invalid channel ID


* `2`: Out of setting range


* `3`: Invalid password


* `4`: Invalid password


* `5`: Invalid arguments


* `6`: Insufficient permissions



### Commands

#### Command `0x0004`: Get BLE Firmware Version

* **Command Packet Args (`Arg[0..13]`):** `0x00` for all


* **Success Response:** `Command` = `0x0004`, `Arg[2:0]` = BLE Firmware Version ID, `Arg[3..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0004`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0010`: RTC Time Calibration

* **Command Packet Args (`Arg[0..13]`):**
* `Arg[0]`: Second (`0–59`)


* `Arg[1]`: Minute (`0–59`)


* `Arg[2]`: Hour (`0–23`)


* `Arg[3]`: Date (`1–31`)


* `Arg[4]`: Day (`1–7`)


* `Arg[5]`: Month (`1–12`)


* `Arg[6]`: Year (`0–99` for 2000–2099)


* `Arg[7..13]`: `0x00`



* **Success Response:** Echoes setting in `Arg[0..6]`, `Arg[7..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0010`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0116`: Get Model Series ID

* **Command Packet Args (`Arg[0..13]`):** `0x00` for all


* **Success Response:** `Arg[0]` = `0x0B` (BM78x Series ID), `Arg[1..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0116`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0140`: Set Connection Password

* **Command Packet Args (`Arg[0..13]`):** `Arg[0..3]` = New Connection Password, `Arg[4..13]` = `0x00`

* **Success Response:** Echoes new password in `Arg[0..3]`, `Arg[4..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0140`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0141`: Get Connection Password

* **Command Packet Args (`Arg[0..13]`):** `0x00` for all


* **Success Response:** `Arg[0..3]` = Connection Password, `Arg[4..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0141`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0142`: Set Device Name

* **Command Packet Args (`Arg[0..13]`):** `Arg[0..11]` = New Device Name (ASCII), `Arg[12..13]` = `0x00`

* **Success Response:** Echoes new name in `Arg[0..11]`, `Arg[12..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0142`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0143`: Get Device Name

* **Command Packet Args (`Arg[0..13]`):** `0x00` for all


* **Success Response:** `Arg[0..11]` = Device Name (ASCII), `Arg[12..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0143`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`


#### Command `0x0151`: Verify Connection Password

* **Default Password:** `"0000"`

* **Command Packet Args (`Arg[0..13]`):** `Arg[0..3]` = Connection Password to verify, `Arg[4..13]` = `0x00`

* **Success Response:** Echoes password in `Arg[0..3]`, `Arg[4..13]` = `0x00`

* **Failure Response:** `Command` = `0x8001`, `Arg[1:0]` = `0x0151`, `Arg[3:2]` = Error Code, `Arg[4..13]` = `0x00`

* **Hardware Factory Reset:** Press and hold the "Hz" button while turning the Rotary Switch from OFF to Capacitance position within 0.6 seconds to restore default password (`0000`) and default device name. The meter display will briefly show `"Org"`.



---

## 5. Streaming Reading Output Format

The total stream frame length is **152 Bytes**, emitted periodically over the Notification characteristic:


$$\text{Stream Format} = \text{Device Info Packet (24 B)} + \text{Device Reading Packet 1 (32 B)} + 3 \times \text{Empty Reading Packets (32 B each, filled with 0x00)}$$

### A. Device Information Packet (24 Bytes)

* **Byte [0]**: `HeadByte0` = `0xFF`

* **Byte [1]**: `HeadByte1` = `0x01`

* **Byte [2]**: `Packet Length` = `0x18` (24 bytes)


* **Byte [3]**: `Packet Type` = `0x04` (Device Information)


* **Byte [4]**: `Protocol Version` = `0x01`

* **Byte [5]**: `Device Category ID` = `0x02` (Multimeter) or `0x03` (Clamp-on meter)


* **Bytes [6–11]**: `Bluetooth Device MAC Address`

* **Byte [12]**: `Battery Status` (`0x02` = Low Battery; `0x00` = Normal)


* **Byte [13]**: `Power Source Flag` = `0x00`

* **Bytes [14–15]**: `Reserved` = `0x00`

* **Byte [16]**: `Reading Packet Count No. 1` = `0x04` (Number of reading packets following)


* **Bytes [17–18]**: `Reading Packet Count No. 2–3` = `0x00`

* **Byte [19]**: `Device Reading PK No.` = `0x01` (Single display device)


* **Bytes [20–21]**: `Checksum [0..1]` (CRC-16 calculated over Bytes [2] through [19])


* **Byte [22]**: `EndByte0` = `0xFF`

* **Byte [23]**: `EndByte1` = `0x03`


### B. Device Reading Packet (32 Bytes)

* **Byte [0]**: `HeadByte0` = `0xFF`

* **Byte [1]**: `HeadByte1` = `0x02`

* **Byte [2]**: `Packet Length` = `0x20` (32 bytes)


* **Byte [3]**: `Packet Type` = `0x05` (Device Reading)


* **Bytes [4–6]**: `Logging Data Set ID [1..3]` = `01 00 00` (little-endian encoding of `0x000001` for BM78XBT)

* **Byte [7]**: `Device Reading PK ID` = `0x01` (Single Display Device)

* **Bytes [8–13]**: `Device RTC Time` (See Bit Field Structure below)


* **Bytes [14–16]**: `Device Status Flags [0..2]` (See Bit Field Structure below)


* **Byte [17]**: `Device Type` = `0x01` (`0` = Sensor, `1` = Meter)


* **Byte [18]**: `Main-Function ID` (See Function ID Table)


* **Byte [19]**: `Reserved` = `0x00`

* **Byte [20]**: `Sub-Function ID` (See Function ID Table)


* **Bytes [21–23]**: `Device Reading Data [0..2]` (24-bit Signed integer, little-endian)


* *Example 1:* `0x008000` = `32768`

* *Example 2:* `0xFF8000` = `-32768`



* **Byte [24]**: `Decimal Point Position` (See Decimal Point Table)


* **Byte [25]**: `Metrics Prefix` (Signed Byte):
* `-9` = `'n'` ($10^{-9}$)


* `-6` = `'µ'` ($10^{-6}$)


* `-3` = `'m'` ($10^{-3}$)


* `0` = `' '` ($10^0$)


* `3` = `'k'` ($10^3$)


* `6` = `'M'` ($10^6$)


* `9` = `'G'` ($10^9$)




* **Byte [26]**: `Function Unit` (See Unit Table)


* **Byte [27]**: `Display Digit Number` (`3` = 3 digits, `4` = 4 digits, `5` = 5 digits, `6` = 6 digits)


* **Bytes [28–29]**: `Checksum [0..1]` (CRC-16 calculated over Bytes [2] through [27])


* **Byte [30]**: `EndByte0` = `0xFF`

* **Byte [31]**: `EndByte1` = `0x03`


---

## 6. Data Encoding Reference Tables

### RTC Time Field Decoding (`Bytes [8..13]` in Reading Packet)

* **Bytes [8..13]**:
* `Hour`: `Byte[11] Bit[2..0]` combined with `Byte[10] Bit[7..6]` ($0 \text{ to } 23$, 5 bits)


* `Minute`: `Byte[10] Bit[5..0]` ($0 \text{ to } 59$, 6 bits)


* `Second`: `Byte[9] Bit[7..2]` ($0 \text{ to } 59$, 6 bits)


* `Millisecond`: `Byte[9] Bit[1..0]` combined with `Byte[8] Bit[7..0]` ($0 \text{ to } 999$, 10 bits)




* **Bytes [12..13]**:
* `Year`: `Byte[13] Bit[7..1]` ($2000 + 1 \text{ to } 127$, 7 bits)


* `Month`: `Byte[13] Bit[0]` combined with `Byte[12] Bit[7..5]` ($1 \text{ to } 12$, 4 bits)


* `Date`: `Byte[12] Bit[4..0]` ($1 \text{ to } 31$, 5 bits)





### Status Flags Decoding

#### Status Flag 2 (`Byte [16]`)

* `Bit[7..0]`: Don't care (`1` or `0`)



#### Status Flag 1 (`Byte [15]`)

* `Bit [6]` (**Sign**): `0` = Positive, `1` = Negative


* `Bit [5]` (**OL**): `0` = Normal Reading, `1` = Overload (OL). *When Bit 5 = 1, ignore Reading Bytes [21..23]*.


* `Bit [4]` (**RECORD**): `0` = Mode Off, `1` = Mode On


* `Bit [3]` (**MAX**): `0` = LCD "MAX" Off, `1` = LCD "MAX" On


* `Bit [2]` (**MIN**): `0` = LCD "MIN" Off, `1` = LCD "MIN" On


* `Bit [1]` (**AVG**): `0` = LCD "AVG" Off, `1` = LCD "AVG" On


* `Bits [7, 0]`: Don't care



#### Status Flag 0 (`Byte [14]`)

* `Bit [7]` (**CREST**): `0` = Inactive, `1` = Active


* `Bit [6]` (**REL**): `0` = Relative Mode Off, `1` = Relative Mode On


* `Bit [5]` (**HOLD**): `0` = Not Held, `1` = Display Held


* `Bit [4]` (**AUTO-Ranging**): `0` = Manual Ranging, `1` = Auto Ranging


* `Bit [3]` (**AUTO-HOLD**): `0` = Inactive, `1` = Active


* `Bit [2]` (**ASCII Reading Flag**):
* `0` = Numerical reading


* `1` = Non-numerical display state. Map `Device Reading [21..23]` as follows:
* `0x000001` -> `"Auto"`

* `0x000002` -> `"InEr"`

* `0x000003` -> `"-"`

* `0x000004` -> `"--"`

* `0x000005` -> `"---"`

* `0x000006` -> `"----"`

* `0x000007` -> `"-----"`

* `0x00000A` -> `"EF-H"`

* `0x00000B` -> `"EF-L"`





* `Bits [1, 0]`: Don't care



### Decimal Point Map (`Byte [24]`)

* **When Display Digit Count (`Byte [27]`) = 5:**
* `0`: `XXXXX`
* `1`: `X.XXXX`
* `2`: `XX.XXX`
* `3`: `XXX.XX`
* `4`: `XXXX.X`



* **When Display Digit Count (`Byte [27]`) = 4:**
* `0`: `XXXX`
* `1`: `X.XXX`
* `2`: `XX.XX`
* `3`: `XXX.X`




### Function Unit Codes (`Byte [26]`)

* `0x02`: `V` (Volt)


* `0x03`: `A` (Ampere)


* `0x04`: `Ω` (Ohm)


* `0x05`: `S` (Siemens / $\mho$)


* `0x06`: `F` (Farad)


* `0x08`: `Hz` (Hertz)


* `0x0A`: `%` (Duty Cycle)


* `0x14`: `°C` (Celsius)


* `0x15`: `°F` (Fahrenheit)


* `0x4F`: `%4~20mA` (Current Loop Percentage)



### Function ID Mapping

| Main Function ID | Function Description | Sub-Function ID | Display Function / Mode |
| --- | --- | --- | --- |
| `0x02` | AutoCheck | `0x00` | LoZ-ACV |
|  |  | `0x01` | LoZ-DCV |
|  |  | `0x03` | AUTO |
| `0x03` | Volt | `0x00` | ACV |
|  |  | `0x01` | DCV |
|  |  | `0x02` | DC+ACV |
|  |  | `0x03` | ~~Hz of Line Volt~~ |
| `0x17` | VFD | `0x00` | Hz of VFD-ACV |
|  |  | `0x01` | VFD-ACV |
| `0x04` | mV | `0x00` | ACmV |
|  |  | `0x01` | DCmV |
|  |  | `0x02` | DC+ACmV |
| `0x05` | µA | `0x00` | ACµA |
|  |  | `0x01` | DCµA |
|  |  | `0x02` | DC+ACµA |
|  |  | `0x03` | ~~Hz of µA~~ |
| `0x06` | mA | `0x00` | ACmA |
|  |  | `0x01` | DCmA |
|  |  | `0x02` | DC+ACmA |
|  |  | `0x03` | ~~Hz of mA~~ |
|  |  | `0x08` | %4~20mA |
| `0x07` | A | `0x00` | ACA |
|  |  | `0x01` | DCA |
|  |  | `0x02` | DC+ACA |
|  |  | `0x03` | ~~Hz of A~~ |
| `0x0C` | Temperature | `0x00` | T1 |
|  |  | `0x01` | T2 |
|  |  | `0x02` | T1 - T2 |
| `0x0D` | Resistance | `0x00` | Resistance |
| `0x0E` | Capacitance | `0x00` | Capacitance |
| `0x0F` | Continuity | `0x00` | Continuity |
| `0x10` | Diode | `0x00` | Diode |
| `0x11` | nS Conductance | `0x00` | nS Conductance |
| `0x12` | Duty Cycle (%) | `0x00` | Duty Cycle (%) |
| `0x13` | Logic-Hz | `0x00` | Logic-Hz |
| `0x22` | EF (Electric Field) | `0x00` | EF-Lo |
|  |  | `0x01` | EF-Hi |
| `0x23` | Hz of Line Signal | `0x00` | Hz of Line Volt/Current |

---

## 7. Connection & Communication Flowchart Sequence

1. **BLE Advertising & Scanning:**
* Central scans for BM78xBT advertising packets.




2. **Connection Parameters Negotiation:**
* Recommended Connection Interval: `100 ms`

* Recommended Slave Latency: `25`

* Recommended Connection Supervision Timeout: `6000 ms`

* Central requests ATT MTU size exchange to **185 bytes**.




3. **Password Verification Flow:**
* Central sends Command `0x0151` with 4-byte ASCII Password (Default: `"0000"`) on Command Characteristic (`0003CDD4-...`).


* If authentication fails, meter responds with `0x8001 + ArgN0151F` error frame.


* If authentication succeeds, meter responds with `0x0151 + ArgN0151` confirmation frame.




4. **Data Streaming Activation:**
* Central enables Notifications on Data Characteristic (`0003CDD5-...`) by writing to its CCCD (`0x2902`).


* Upon opening notification channels, BM78xBT streams display reading frames periodically (152 bytes total: 1 Info Packet + 4 Reading Packets).