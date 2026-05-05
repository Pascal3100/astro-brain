# NexStar Serial Protocol — Reference

> Consolidated reference for the Celestron NexStar serial protocol as used by `backend/astro_brain/adapters/nexstar_adapter.py` to drive the Bresser/Celestron mount over USB-série (9600 8N1).
>
> Two layers are documented here:
>
> 1. **HC serial protocol** — single-byte command IDs sent to the hand control via the HC's RS-232/USB port. This is what `nexstarpy` wraps and what is documented in the official Celestron PDF.
> 2. **AUX command set** — packetised motor-controller / GPS / accessory protocol, accessible *through* the HC via the pass-through prefix `'P'` (0x50) or directly via the PC port. This is where backlash, cordwrap, sync-of-position, autoguide rate etc. live. Documented by Andre Paquette, not by Celestron.

## Sources

| Source | Type | Used for |
| --- | --- | --- |
| [`1154108406_nexstarcommprot.pdf`](https://s3.amazonaws.com/celestron-site-support-files/support_files/1154108406_nexstarcommprot.pdf) (Celestron official, ~v1.2, dated 2006-07-28, author: Andre Paquette while at Celestron) | Canonical | Every HC-level command in this document. |
| [Celestron support page — NexStar Communication Protocol v1.2](https://www.celestron.com/pages/support-files/nexstar-communication-protocol-v-1-2) | Canonical landing page | Pointer to the PDF above. |
| [`NexStar_AUX_Commands_10.pdf`](http://www.paquettefamily.ca/nexstar/NexStar_AUX_Commands_10.pdf) — Andre Paquette, "NexStar AUX Command Set", Issue 1.0, February 2003 | Reverse-engineered, community canonical | All `MC_*`, `GPS_*`, `MAIN_*` IDs, packet format, backlash/cordwrap/PEC/autoguide/approach. |
| [`indigo-astronomy/libnexstar`](https://github.com/indigo-astronomy/libnexstar) | Reverse-engineered | Cross-check of pass-through hex codes; protocol-version constants. |
| [`jochym/nexstar-evo` notes.md](https://github.com/jochym/nexstar-evo/blob/master/doc/notes.md) | Reverse-engineered (Evolution-specific) | Evolution-only AUX device IDs (Wi-Fi, battery, lights), pulse-guide IDs `0x26`/`0x27`. Not relevant to SLT/AdvGT. |
| INDI forum — [Hibernation thread](https://indilib.org/forum/mounts/6289-celestron-hybernation-mode.html), [Ryoko ASCOM driver](https://github.com/Ryoko/ASCOM-Celestron-Telescope-Driver-RS232-BT) | Reverse-engineered | Hibernate `'x'` (0x78) / Wake `'y'` (0x79). NexStar+ HC ≥ 5.22 (GEM) / 5.24 (fork). |

**Document version this file targets:** Celestron HC protocol "v1.2" (PDF revision dated 2006-07-28). Sync (`'S'`/`'s'`) was added in HC firmware 4.10+ — present in the PDF text we have. Hibernate/Wake (`'x'`/`'y'`) are **not** in the PDF and remain community-documented only.

**Mount-coverage caveat.** The user's mount is most likely an **SLT** (model code 7) — possibly an **Advanced GT** (model code 6). The vast majority of HC-level commands work uniformly across SLT/AdvancedGT/CPC/SE/CGE. Differences flagged in the table:

- `Sync` (`'S'`/`'s'`): HC firmware ≥ 4.10 only.
- `Get precise AZM-ALT` (`'z'`): HC ≥ 2.2.
- `Get/Set Location/Time` (`'w'`/`'W'`/`'h'`/`'H'`): HC ≥ 2.3.
- RTC pass-through (device 0xB2): **CGE only**.
- PEC: only meaningful for EQ-mode mounts (CGE/AdvancedGT/CGEM, **not** SLT).
- Cordwrap: only meaningful for fork mounts (CPC/SE/SLT, **not** GEMs).
- Hibernate/Wake: NexStar+ HC **5.22+ (GEM)** / **5.24+ (fork)**. SLT with the original 4.x HC almost certainly does **not** support it; an SLT bundled with a NexStar+ HC does.

---

## Frame format (HC level)

- **Wire**: 9600 baud, 8 data bits, no parity, 1 stop bit, no flow control. RJ-22 socket on the underside of the HC.
- **Request**: a single ASCII command byte, sometimes followed by binary or ASCII payload.
- **Response**: zero or more payload bytes, terminated by the literal byte `'#'` (0x23).
- **Worst-case timeout**: 3.5 seconds (the HC retries internally when talking to the MC). For pass-through commands, the HC may also return one extra error byte before `'#'` if the target device did not answer — read until `'#'` and discard.
- **Numbers**: position values are sent as ASCII hex digits (uppercase or lowercase accepted); time/location/pass-through payloads are sent as raw bytes.

## Position encoding

The Get/GoTo position commands encode each axis as a fraction of one full rotation:

- Standard precision (4 hex chars): `value / 0x10000` → fraction of 360°. ~19.8 arcsec/lsb.
- Precise (8 hex chars, only 24 MSBs significant): `(value & 0xFFFFFF00) / 0x100000000` → fraction of 360°. ~0.08 arcsec/lsb.

For RA/DEC, after alignment, values reflect the actual sky. AZM is indexed to North = 0 once aligned; ALT = 0 means OTA perpendicular to the AZM axis. Before alignment, both axes are relative to the boot-time orientation.

---

## Command table (HC-level, sorted by hex code)

> "ASCII" is what you'd put in `bytes(...)`. Payload columns use Python `bytes` notation: ASCII literals in `b'...'`, binary bytes as `\xXX`. Response always ends with `b'#'`.

| Hex | ASCII | Name | Payload (request) | Response (before `#`) | Models / HC firmware | Source | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0x42 | `B` | GoTo AZM-ALT | `b'B' + b'%04X,%04X' % (azm, alt)` | empty | All, 1.2+ | Celestron PDF | Acked once GoTo *initiated*; poll `L`. |
| 0x48 | `H` | Set Time | `b'H' + 8 raw bytes (h,m,s,month,day,year-2000,tz,dst)` | empty | All, 2.3+ | Celestron PDF | tz negative = `256-zone`. dst: 0/1. |
| 0x4A | `J` | Is Alignment Complete? | none | 1 byte: `0` not aligned, `1` aligned | All, 1.2+ | Celestron PDF | **Already in `nexstarpy`? No.** |
| 0x4B | `K` | Echo | `b'K' + 1 byte` | the same byte | All, 1.2+ | Celestron PDF | Liveness probe. |
| 0x4C | `L` | Is GoTo in Progress? | none | 1 ASCII byte: `'0'` (0x30) idle, `'1'` (0x31) running | All, 1.2+ | Celestron PDF | **ASCII char, not raw 0/1.** |
| 0x4D | `M` | Cancel GoTo | none | empty | All, 1.2+ | Celestron PDF | |
| 0x50 | `P` | Pass-through | `b'P' + msgLen + destId + msgId + d1 + d2 + d3 + responseBytes` (8 bytes total) | `responseBytes` bytes of data | All, 1.6+ | Celestron PDF + Paquette | See § Pass-through. |
| 0x52 | `R` | GoTo RA/DEC | `b'R' + b'%04X,%04X' % (ra, dec)` | empty | All, 1.2+ | Celestron PDF | Requires alignment. |
| 0x53 | `S` | Sync RA/DEC | `b'S' + b'%04X,%04X' % (ra, dec)` | empty | All, **4.10+** | Celestron PDF | The "align on object" command. **NOT in `nexstarpy`.** |
| 0x54 | `T` | Set Tracking Mode | `b'T' + chr(mode)` (mode: 0 Off, 1 Alt-Az, 2 EQ-N, 3 EQ-S) | empty | All, 1.6+ | Celestron PDF | CGE/AdvGT 3.01–3.04 inverted EQ-N/EQ-S. |
| 0x56 | `V` | Get Version | none | 2 bytes `(major, minor)` | All, 1.2+ | Celestron PDF | HC firmware. |
| 0x57 | `W` | Set Location | `b'W' + 8 raw bytes (latD, latM, latS, NS, lonD, lonM, lonS, EW)` | empty | All, 2.3+ | Celestron PDF | NS=0 N/1 S, EW=0 E/1 W. |
| 0x58 | `X` | (reserved/unused) | — | — | — | — | — |
| 0x62 | `b` | GoTo precise AZM-ALT | `b'b' + b'%08X,%08X'` (only top 24 bits used) | empty | All, 2.2+ | Celestron PDF | |
| 0x65 | `e` | Get precise RA/DEC | none | 17 bytes `'XXXXXXXX,XXXXXXXX'` | All, 1.6+ | Celestron PDF | |
| 0x68 | `h` | Get Time | none | 8 raw bytes `(h,m,s,month,day,year-2000,tz,dst)` | All, 2.3+ | Celestron PDF | **NOT in `nexstarpy`** (only `set_time` is). |
| 0x6D | `m` | Get Model | none | 1 byte | All, 2.2+ | Celestron PDF | See model table below. |
| 0x72 | `r` | GoTo precise RA/DEC | `b'r' + b'%08X,%08X'` | empty | All, 1.6+ | Celestron PDF | |
| 0x73 | `s` | Sync precise RA/DEC | `b's' + b'%08X,%08X'` | empty | All, **4.10+** | Celestron PDF | **NOT in `nexstarpy`.** |
| 0x74 | `t` | Get Tracking Mode | none | 1 byte (mode value) | All, 2.3+ | Celestron PDF | |
| 0x77 | `w` | Get Location | none | 8 raw bytes (same layout as Set) | All, 2.3+ | Celestron PDF | **NOT in `nexstarpy`.** |
| 0x78 | `x` | **Hibernate** | none | empty | NexStar+ HC ≥ 5.22 GEM / 5.24 fork; StarSense | Community / INDI / Ryoko ASCOM | Mount stops tracking, retains alignment. |
| 0x79 | `y` | **Wake from hibernate** | `b'y' + 1 byte (0 or 1)` | empty | NexStar+ HC ≥ 4.21+ in INDI driver; check actual HC | Community | Param semantics not fully documented; INDI sends 0. |
| 0x7A | `z` | Get precise AZM-ALT | none | 17 bytes | All, 2.2+ | Celestron PDF | |

### Variable-rate slew (HC command 'P' with msgLen=3)

`b'P' + b'\x03' + axis + dir + rateHi + rateLo + b'\x00' + b'\x00'`

- axis = 0x10 (AZM/RA) or 0x11 (ALT/DEC)
- dir = 0x06 (positive) or 0x07 (negative)
- rate is in arcsec/sec × 4, split as `(rate*4) // 256, (rate*4) % 256`. So 150 arcsec/sec → `chr(2)+chr(88)`.

Response: empty (just `#`).

### Fixed-rate slew (HC command 'P' with msgLen=2)

`b'P' + b'\x02' + axis + dir + rate + b'\x00' + b'\x00' + b'\x00'`

- axis = 0x10 / 0x11
- dir = 0x24 (positive) or 0x25 (negative)
- rate = 0..9 (0 stops). On GT mounts, rate 9 = 3°/s, not maximum.

### Model codes (`'m'` response byte)

| Code | Mount |
| --- | --- |
| 1 | NexStar GPS Series |
| 3 | i-Series |
| 4 | i-Series SE |
| 5 | CGE |
| 6 | Advanced GT |
| 7 | **SLT** |
| 9 | CPC |
| 10 | GT (legacy) |
| 11 | 4/5 SE |
| 12 | 6/8 SE |

(Newer Evolution / CGX / CGEM-II / StarSense codes are not in the 2006 PDF; community sources list 14=Evolution, 20=CGEM, etc., but treat as speculative for this project.)

### Tracking modes

| Value | Meaning |
| --- | --- |
| 0 | Off |
| 1 | Alt/Az |
| 2 | EQ North |
| 3 | EQ South |

---

## Pass-through (`'P'`) frame layout

The HC has a fixed 8-byte transport for any AUX command:

```
0x50  msgLen  destId  msgId  data1  data2  data3  responseBytes
```

- `msgLen` ∈ {1,2,3}: number of meaningful bytes from `msgId` onward (i.e. 1 = just `msgId`, 2 = `msgId+data1`, 3 = `msgId+data1+data2`, 4 = `msgId+data1+data2+data3`). The Celestron PDF shows `msgLen=3` for variable-rate slew and `msgLen=2` for fixed-rate slew (which include msgId + 2 or 1 data bytes respectively). Stick to that convention.
- `destId`: AUX device ID (table below).
- `msgId`: AUX message ID for the chosen device.
- `data1..data3`: payload bytes; **always present in the frame** (zero-padded if unused).
- `responseBytes`: how many bytes you expect back (excluding `#`). If the device returns more, you get truncation; if less, garbage in the trailing bytes.

The reply is `responseBytes` bytes of data + `'#'`. If the destination did not answer at all, the HC inserts one extra error byte before `'#'` — robust code reads until `'#'`.

### AUX device IDs

| Hex | Decimal | Device | Notes |
| --- | --- | --- | --- |
| 0x01 | 1 | Main / Interconnect board | |
| 0x04 | 4 | Hand control | Use as source on direct PC port; on HC pass-through, the HC handles source. |
| 0x10 | 16 | AZM/RA motor controller | |
| 0x11 | 17 | ALT/DEC motor controller | |
| 0xB0 | 176 | GPS / Compass | NexStar GPS only (ours uses our own DroTek GPS, so this is moot). |
| 0xB2 | 178 | RTC | **CGE only.** |
| 0xB4 | 180 | Focuser (community) | Celestron motorised focuser. Not relevant pre-Macro 6. |
| 0xB5 | 181 | Wi-Fi controller | Evolution-only. |
| 0xB6 | 182 | Battery / charge | Evolution-only. |
| 0xB7 | 183 | Charge port | Evolution-only. |
| 0xBF | 191 | Mount lights | Evolution-only. |

---

## Motor-controller AUX commands (destId 0x10 / 0x11)

All from Andre Paquette's "NexStar AUX Command Set" v1.0 (Feb 2003) unless noted. **None are formally endorsed by Celestron**, but they have been used in production by INDI, ASCOM, libnexstar, KStars/Ekos for ~20 years and are known stable.

### Position & motion

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0x01 | `MC_GET_POSITION` | none | 24-bit signed pos | Fraction of full rotation. |
| 0x02 | `MC_GOTO_FAST` | 16 or 24-bit pos | ack | Slew at rate 9. |
| 0x04 | `MC_SET_POSITION` | 24-bit pos | ack | Used by HC after leveling/north-finding. |
| 0x06 | `MC_SET_POS_GUIDERATE` | 16 or 24-bit | ack | 0xFFFF=sidereal, 0xFFFE=solar, 0xFFFD=lunar (16-bit form). |
| 0x07 | `MC_SET_NEG_GUIDERATE` | 16 or 24-bit | ack | Same magic values. |
| 0x17 | `MC_GOTO_SLOW` | 16 or 24-bit | ack | Slow approach goto. |
| 0x24 | `MC_MOVE_POS` | 1 byte rate (0..9) | ack | Fixed rate move "right/up". 0 stops. |
| 0x25 | `MC_MOVE_NEG` | 1 byte rate | ack | Fixed rate move "left/down". |
| 0x13 | `MC_SLEW_DONE` | none | 1 byte: 0x00 not done, 0xFF done | Per axis. **HC `'L'` aggregates this.** |

### Backlash

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0x10 | `MC_SET_POS_BACKLASH` | 1 byte (0..99) | ack | "Push" direction backlash. |
| 0x11 | `MC_SET_NEG_BACKLASH` | 1 byte (0..99) | ack | "Pull" direction backlash. |
| 0x40 | `MC_GET_POS_BACKLASH` | none | 1 byte | |
| 0x41 | `MC_GET_NEG_BACKLASH` | none | 1 byte | |

Range **0–99** integer, dimensionless (HC presents it as such — the same scale as the "Anti-Backlash" menu in the HC).

### GoTo approach

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0xFC | `MC_GET_APPROACH` | none | 1 byte: 0 positive, 1 negative | Per axis. |
| 0xFD | `MC_SET_APPROACH` | 1 byte | ack | |

### Autoguide rate

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0x46 | `MC_SET_AUTOGUIDE_RATE` | 1 byte | ack | percentage = `100 * value / 256`. |
| 0x47 | `MC_GET_AUTOGUIDE_RATE` | none | 1 byte | Same formula. |

### Cordwrap (AZM only — destId 0x10)

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0x38 | `MC_ENABLE_CORDWRAP` | none | ack | |
| 0x39 | `MC_DISABLE_CORDWRAP` | none | ack | |
| 0x3A | `MC_SET_CORDWRAP_POS` | 24-bit pos | ack | Convention: current AZM + 180° mod 360°. |
| 0x3B | `MC_POLL_CORDWRAP` | none | 1 byte: 0x00 disabled, 0xFF enabled | |
| 0x3C | `MC_GET_CORDWRAP_POS` | none | 24-bit pos | |

### PEC (AZM only)

| MsgID | Name | Tx data | Response | Notes |
| --- | --- | --- | --- | --- |
| 0x0C | `MC_PEC_RECORD_START` | none | ack | Requires `MC_AT_INDEX` first. |
| 0x0D | `MC_PEC_PLAYBACK` | 1 byte (1 start / 0 stop) | ack | |
| 0x15 | `MC_PEC_RECORD_DONE` | none | 1 byte (0xFF when done) | |
| 0x16 | `MC_PEC_RECORD_STOP` | none | ack | |
| 0x18 | `MC_AT_INDEX` | none | 1 byte | AZM only. |
| 0x19 | `MC_SEEK_INDEX` | none | ack | AZM only. |

### Leveling (ALT only)

| MsgID | Name | Notes |
| --- | --- | --- |
| 0x0B | `MC_LEVEL_START` | |
| 0x12 | `MC_LEVEL_DONE` | 0xFF when done. |

### Slew limits (Evolution-flavoured; SLT untested)

From `nexstar-evo` notes — present on Evolution, **probably not on SLT 4.x**. Document as speculative for our hardware.

| MsgID | Name | Notes |
| --- | --- | --- |
| 0x20 | `MC_SET_MAX_SLEW_RATE` | 16-bit, 1e-3 deg/s. |
| 0x21 | `MC_GET_MAX_SLEW_RATE` | Returns two 16-bit. |
| 0x22 | `MC_ENABLE_MAX_SLEW_RATE` | 0x01 active / 0x00 inactive. |
| 0x23 | `MC_GET_MAX_SLEW_RATE_STATUS` | |

### Pulse-guide (Evolution / newer MC; SLT untested)

| MsgID | Name | Notes |
| --- | --- | --- |
| 0x26 | `MTR_AUX_GUIDE` | signed velocity %, unsigned duration. |
| 0x27 | `MTR_IS_AUX_GUIDE_ACTIVE` | TRUE/FALSE. |

### Misc

| MsgID | Name | Notes |
| --- | --- | --- |
| 0xFE | `MC_GET_VER` | Returns 2 bytes (major, minor). Available on every device. |

### Firmware upgrade — DO NOT USE

`MC_PROGRAM_ENTER` (0x81), `MC_PROGRAM_INIT` (0x82), `MC_PROGRAM_DATA` (0x83), `MC_PROGRAM_END` (0x84). Listed for completeness; sending these can brick the MC.

---

## GPS unit AUX commands (destId 0xB0)

> Our DroTek GPS is **not** wired through the mount, so these are largely irrelevant. Documented for completeness; they only return useful data on a NexStar GPS / CPC with a built-in GPS.

| MsgID | Name | Response | Notes |
| --- | --- | --- | --- |
| 0x01 | `GPS_GET_LAT` | 24-bit signed | Fraction of full rotation × 360°. |
| 0x02 | `GPS_GET_LONG` | 24-bit signed | |
| 0x03 | `GPS_GET_DATE` | 2 bytes (month, day) | GMT. |
| 0x04 | `GPS_GET_YEAR` | 16-bit | GMT. |
| 0x07 | `GPS_GET_SAT_INFO` | 2 bytes (visible, tracked) | |
| 0x08 | `GPS_GET_RCVR_STATUS` | 16-bit bitfield | See AUX doc §"Receiver status". |
| 0x33 | `GPS_GET_TIME` | 3 bytes (h,m,s) | GMT. |
| 0x36 | `GPS_TIME_VALID` | 1 byte (0/1) | |
| 0x37 | `GPS_LINKED` | 1 byte (0/1) | This is what `nexstarpy.is_gps_linked()` calls. |
| 0x55 | `GPS_GET_HW_VER` | 1 byte (0xAB constant) | Motorola module ID. |
| 0xA0 | `GPS_GET_COMPASS` | 1 byte | 0x0B=N, 0x09=NE, 0x0D=E, 0x0C=SE, 0x0E=S, 0x06=SW, 0x07=W, 0x03=NW. |
| 0xFE | `GPS_GET_VER` | 2 bytes | |

Celestron PDF also documents these GPS items wrapped at HC level via `'P' + chr(1) + chr(176) + msgId + ... + chr(responseLen)`.

---

## RTC AUX commands (destId 0xB2 — CGE only)

| MsgID | Name | Notes |
| --- | --- | --- |
| 0x03 | `RTC_GET_DATE` | (month, day). |
| 0x04 | `RTC_GET_YEAR` | 16-bit. |
| 0x33 | `RTC_GET_TIME` | (h, m, s). |
| 0x83 | `RTC_SET_DATE` | data: month, day. HC ≥ 3.01. |
| 0x84 | `RTC_SET_YEAR` | data: yearHi, yearLo. |
| 0xB3 | `RTC_SET_TIME` | data: h, m, s. |

---

## Family deep-dives — gotchas & sample byte sequences

### 1. Sync (HC `S` / `s`)

The Celestron PDF (revision present in `1154108406_nexstarcommprot.pdf`) explicitly documents Sync as a top-level HC command since firmware 4.10. It is **not** an AUX/MC `MC_SET_POSITION` — that one sets the raw axis encoder, which is wrong for an "align on object" use-case because the HC's alignment model is not a single axis offset.

**Pyserial snippet:**

```python
def sync_radec(ser, ra_deg, dec_deg):
    ra_int  = int(ra_deg  / 360.0 * 0x10000) & 0xFFFF
    dec_int = int(dec_deg / 360.0 * 0x10000) & 0xFFFF
    cmd = b'S' + b'%04X,%04X' % (ra_int, dec_int)
    ser.write(cmd)
    return ser.read_until(b'#')   # response is just b'#'
```

For precise sync, use lowercase `s` and 8-hex-digit fields (top 24 bits). Sync requires the mount to already be aligned — it's an *adjustment*, not an *initial alignment*. For our 3-star wizard, we do the wizard's geometry on the Pi, then push the resulting coordinate fix back via `S`/`s` for at least the brightest reference star.

**Gotcha:** Sync was *not* in the original 2007 community-distributed PDF — it appeared in the version of the same PDF on the Celestron site after they added it to HC firmware 4.10. Some old wrappers (including `nexstarpy` 0.1.0) don't expose it.

### 2. Backlash (AUX `MC_*_BACKLASH`)

Range 0–99, applied per axis per direction. The HC menu "Anti-Backlash" maps directly to these four bytes: AZM-positive, AZM-negative, ALT-positive, ALT-negative.

**Pyserial snippet — set ALT positive backlash to 30:**

```python
# 'P' (0x50)  msgLen=2  dest=0x11 (ALT)  msgId=0x10 (SET_POS_BACKLASH)  d1=30  d2=0  d3=0  resp=0
ser.write(bytes([0x50, 0x02, 0x11, 0x10, 30, 0x00, 0x00, 0x00]))
ser.read_until(b'#')   # b'#' on success; b'\x00#' if device didn't respond
```

**Get AZM negative backlash:**

```python
ser.write(bytes([0x50, 0x01, 0x10, 0x41, 0x00, 0x00, 0x00, 0x01]))
resp = ser.read_until(b'#')
backlash = resp[0]            # 0..99
```

### 3. Cordwrap (AUX `MC_*_CORDWRAP`, AZM only)

Cordwrap prevents the AZM axis from rotating past a "no-cross" angle, avoiding cable wrap on fork mounts. SLT is a fork mount → cordwrap is meaningful.

**Enable cordwrap:**

```python
# msgLen=1 (only msgId), dest=0x10 (AZM), msgId=0x38, no data, no response
ser.write(bytes([0x50, 0x01, 0x10, 0x38, 0x00, 0x00, 0x00, 0x00]))
ser.read_until(b'#')
```

**Disable, poll, get/set position** follow the same pattern; see the table above for msgIds. The position is a 24-bit signed fraction-of-rotation, identical to `MC_GET_POSITION`. By convention it is set to "current AZM + 180° mod 360°" so the no-cross line is behind the OTA at startup.

### 4. GoTo-in-progress (HC `L`)

Returns ASCII `'0'` or `'1'`, **not** raw 0/1. Polling pattern:

```python
def goto_in_progress(ser):
    ser.write(b'L')
    resp = ser.read_until(b'#')   # b'0#' or b'1#'
    return resp[0:1] == b'1'
```

### 5. Get Location / Get Time (HC `w` / `h`)

Both return **8 raw bytes** then `'#'`. Layout matches the Set commands:

- `w` → `lat_deg, lat_min, lat_sec, NS(0=N/1=S), lon_deg, lon_min, lon_sec, EW(0=E/1=W)`
- `h` → `hour, minute, second, month, day, year-2000, tz_offset, dst(0/1)`. tz: if negative, value = `256 + zone` (e.g. UTC-5 → 251).

```python
ser.write(b'w')
b = ser.read_until(b'#')
lat_d, lat_m, lat_s, ns, lon_d, lon_m, lon_s, ew = b[:8]
```

### 6. Echo (HC `K`) — liveness

```python
ser.write(b'K' + b'\xA5')
assert ser.read_until(b'#') == b'\xA5#'
```

Useful as a heartbeat from the FastAPI side to confirm the HC is alive without nudging the motors.

### 7. Hibernate / Wake (HC `x` / `y`)

**Caveat: not in the Celestron PDF.** Confirmed working on NexStar+ HC firmware ≥ 5.22 (GEM) / ≥ 5.24 (fork) and on StarSense HC. Implemented in INDI's celestron driver and Ryoko's ASCOM driver; both projects worked directly with Celestron developers. Behaviour: mount stops tracking and powers down motors but retains alignment and time. On wake, the HC re-syncs to the saved alignment.

```python
ser.write(b'x')         ; ser.read_until(b'#')   # hibernate
ser.write(b'y' + b'\x00'); ser.read_until(b'#')  # wake
```

If the SLT we have is paired with the original 4.x HC, **expect this to fail or be ignored**. Test with `K` first then try `x`/`y`; if `x` returns `b'#'` quickly and tracking stops, it's supported.

### 8. Pass-through "device not present" detection

When the HC tries to forward a `P` packet to a device that isn't there (e.g. `dest=0xB0` on an SLT with no built-in GPS), the response is one extra error byte before `'#'`. Robust code:

```python
def aux_send(ser, dest, msg_id, data=(0,0,0), resp_len=0):
    payload = [0x50, 1 + len(data), dest, msg_id, *data, resp_len]
    ser.write(bytes(payload))
    raw = ser.read_until(b'#')
    if len(raw) > resp_len + 1:        # extra byte → device absent
        raise NexStarDeviceMissing(dest)
    return raw[:resp_len]
```

### 9. Slew-rate semantics

- **Variable rate** is in arcsec/sec × 4. Range up to ~16383 ≈ 1°/s on most mounts.
- **Fixed rate** 1..9 mimics the HC's keypad rates. Rate 9 on GT-class is **3°/s, not the maximum** — for max slew, use a high variable rate.
- Slew commands generally **override tracking**. Best practice from the PDF: stop tracking → slew → restore tracking. Exception: in EQ tracking, fixed rates 1 and 2 don't override (useful for autoguide simulation).

---

## What `nexstarpy` 0.1.0 currently wraps vs. what's available

Inventory taken directly from `nexstarpy/constants.py` and `nexstarpy/nexstar.py` of the installed wheel.

### Wrapped (good)

| HC cmd | Method | Notes |
| --- | --- | --- |
| `E`, `e` | `get_radec(precise=)` | OK |
| `Z`, `z` | `get_azm_alt(precise=)` | OK |
| `R`, `r` | `goto_radec(... precise=)` | OK |
| `B` | `goto_azm_alt` | OK — only standard precision (`b` not exposed). |
| `T` | `set_tracking_mode` | OK |
| `t` | `get_tracking_mode` | OK |
| `W` | `set_location` | OK |
| `H` | `set_time` | OK |
| `V` | `get_version` | OK |
| `m` | `get_model` | OK |
| `M` | `cancel_goto` | OK |
| `K` | (not exposed as method but constant defined) | Constant only, no `echo()` method. |
| `L` | (not exposed as method but constant defined) | Constant only, no `goto_in_progress()` method. |
| Variable slew | `slew_variable(axis, dir, rate)` | OK |
| Fixed slew | `slew_fixed(axis, dir, rate)` | OK |
| Pass-through (GPS link only) | `is_gps_linked` | Hard-codes `dest=0xB0, msgId=0x37`. |

### Constant defined but no method

- `ECHO` (`b'K'`) — no `echo()`.
- `GOTO_IN_PROGRESS` (`b'L'`) — no `goto_in_progress()`. **Critical missing.**
- `RTC` (`0xB2`) — defined but no methods touching the CGE RTC.

### Absent — must send raw bytes via `pyserial`

- **`J` — Is alignment complete?** Trivial; needed before allowing GoTo from the app.
- **`S` / `s` — Sync** (HC 4.10+). Needed for the Macro 3 3-star wizard fix-up.
- **`b` — GoTo precise AZM-ALT.**
- **`w` — Get Location.** We mostly drive location *to* the mount (we have a real GPS), but useful for diagnostics ("did the mount remember location after hibernate?").
- **`h` — Get Time.** Same.
- **`x` / `y` — Hibernate / Wake.** Needs HC firmware check first.
- **All AUX motor pass-through** — backlash, cordwrap, autoguide rate, approach, GoTo-slow, MC version probe per axis, slew-done per axis, max-slew-rate, pulse-guide. None of these have any wrapper.
- **All GPS pass-through except `is_linked`** — irrelevant for us (we use the DroTek GPS), but worth noting for completeness.

---

## Recommended additions to `nexstarpy` (or our own `nexstar_adapter.py`)

Given the scope of the gap, we have three options:

1. **Extend `nexstarpy`** (PR upstream + vendor in `pyproject`).
2. **Fork `nexstarpy`** as `astro-brain-nexstar` and own the surface.
3. **Wrap `pyserial` directly** in `backend/astro_brain/adapters/nexstar_adapter.py` and treat `nexstarpy` as a starting reference — drop the dependency once we cover its surface.

Recommendation: **option 3** for now (the dependency is single-author, 0.1.0, and we already need to send raw AUX bytes). Vendor the `Tracking Mode` / `Slew Direction` enums.

Priority list for implementation, by milestone:

### Macro 2 — Setup (calibration + courses + backlash)

- `J` — `is_aligned()`. *One-byte HC command, trivial.*
- `L` — `is_goto_in_progress()`. *Polling primitive; drives the "is the slew finished" UX.*
- `K` — `echo()`. *Connection heartbeat for the SSE state stream.*
- AUX `MC_GET_POS_BACKLASH` / `MC_GET_NEG_BACKLASH` / `MC_SET_POS_BACKLASH` / `MC_SET_NEG_BACKLASH` for both axes (8 calls). *Drives the "Backlash" panel of the Setup screen.*
- AUX `MC_POLL_CORDWRAP` / `MC_ENABLE_CORDWRAP` / `MC_DISABLE_CORDWRAP` / `MC_GET_CORDWRAP_POS` / `MC_SET_CORDWRAP_POS` (AZM only). *Drives the "Cordwrap" panel.*
- AUX `MC_GET_VER` per axis. *Surfaces motor controller firmware version in the "À propos" screen.*
- `w` / `h` — `get_location()` / `get_time()`. *Diagnostic round-trip after we push GPS data with `W`/`H`.*

### Macro 3 — Mise en station + GoTo basique

- `S` / `s` — `sync_radec(ra, dec, precise=)`. *Push 3-star wizard fix back to mount.*
- AUX `MC_SLEW_DONE` per axis. *Granular slew completion, fallback to `L`.*
- AUX `MC_GET_AUTOGUIDE_RATE` / `MC_SET_AUTOGUIDE_RATE`. *Settings panel.*
- AUX `MC_GET_APPROACH` / `MC_SET_APPROACH`. *Optional fine-tuning.*

### Macro 5+

- AUX `MC_GOTO_SLOW`. *Useful for fine framing once cameras land.*
- Hibernate / Wake (`x` / `y`). *Quality-of-life for multi-night sessions; conditional on HC firmware ≥ 5.22/5.24.*
- Pulse-guide (`MTR_AUX_GUIDE` 0x26 / 0x27). *PHD2 path in Macro 7.*
- PEC commands. *Not on SLT (Alt-Az), only relevant if we add an EQ mount someday.*

---

## Implementation hints

- **Always read until `b'#'`**. Never read fixed lengths — pass-through "device missing" injects an extra byte.
- **3.5 s timeout** for any HC command, per the PDF. AUX commands routed through HC pass-through inherit this.
- **Don't poll faster than ~10 Hz**. Paquette explicitly warns: "Polling the MC board very frequently can cause some operations to fail" — back-to-back `MC_SLEW_DONE` can make the MC overshoot.
- **Echo (`K`) is your friend** — use it as a health probe in the connection-state machine (we already have an `overall` pastille with a connection state; this is where `K` fits).
- **Detect HC capability** at connection time: `V` (HC firmware) + `m` (model). Gate Sync/Hibernate/Wake on those values.
- **Tracking conflict**: stop tracking (`T 0`) before any manual slew, restore the original mode after. The slew-tracking conflict only doesn't apply at fixed rates 1–2 in EQ mode (irrelevant for SLT alt-az).
