"""Sniffer passif du bus AUX, via le pont ESP32 (aucune émission).

Le pont laisse /OE en Hi-Z au repos et relaie vers le Pi TOUTE trame vue sur
le bus : il suffit de lire /dev/ttyAMA0 pendant que la raquette parle.
Prérequis : indiserver ARRÊTÉ (sinon notre driver émet aussi et on capture
un dialogue pollué), raquette branchée sur le jack AUX libre de la base.

Trame AUX : 0x3b | len | src | dst | cmd | data[len-3] | checksum
"""
from __future__ import annotations

import sys
import time

import serial

TARGETS = {
    0x00: "ANY", 0x01: "MB", 0x04: "HC", 0x0D: "HCP", 0x10: "AZM",
    0x11: "ALT", 0x12: "FOCUS", 0x20: "APP", 0xB0: "GPS", 0xB5: "WiFi",
    0xB6: "BAT", 0xB7: "CHG", 0xBF: "LIGHT",
}
# Les commandes MC_* et GPS_* se recouvrent : on désambiguïse sur la cible.
MC_CMDS = {
    0x01: "MC_GET_POSITION", 0x02: "MC_GOTO_FAST", 0x04: "MC_SET_POSITION",
    0x05: "MC_GET_MODEL", 0x06: "MC_SET_POS_GUIDERATE",
    0x07: "MC_SET_NEG_GUIDERATE", 0x0B: "MC_LEVEL_START",
    0x12: "MC_LEVEL_DONE", 0x13: "MC_SLEW_DONE", 0x17: "MC_GOTO_SLOW",
    0x18: "MC_SEEK_DONE", 0x19: "MC_SEEK_INDEX", 0x24: "MC_MOVE_POS",
    0x25: "MC_MOVE_NEG", 0x26: "MC_AUX_GUIDE", 0x27: "MC_AUX_GUIDE_ACTIVE",
    0x38: "MC_ENABLE_CORDWRAP", 0x39: "MC_DISABLE_CORDWRAP",
    0x3A: "MC_SET_CORDWRAP_POS", 0x3B: "MC_POLL_CORDWRAP",
    0x3C: "MC_GET_CORDWRAP_POS", 0x46: "MC_SET_AUTOGUIDE_RATE",
    0x47: "MC_GET_AUTOGUIDE_RATE", 0xFE: "GET_VER",
}
GPS_CMDS = {
    0x01: "GPS_GET_LAT", 0x02: "GPS_GET_LONG", 0x03: "GPS_GET_DATE",
    0x04: "GPS_GET_YEAR", 0x33: "GPS_GET_TIME", 0x36: "GPS_TIME_VALID",
    0x37: "GPS_LINKED", 0xFE: "GET_VER",
}


def name(target: int) -> str:
    return TARGETS.get(target, f"0x{target:02x}")


def cmd_name(cmd: int, src: int, dst: int) -> str:
    axis = {0x10, 0x11}
    if src in axis or dst in axis:
        return MC_CMDS.get(cmd, f"0x{cmd:02x}")
    if 0xB0 in (src, dst):
        return GPS_CMDS.get(cmd, f"0x{cmd:02x}")
    return MC_CMDS.get(cmd, f"0x{cmd:02x}")


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
    ser = serial.Serial(port, 19200, bytesize=8, parity="N", stopbits=2,
                        timeout=0.1)
    t0 = time.monotonic()
    buf = bytearray()
    seen = 0
    print(f"# sniff {port} pendant {duration:.0f}s — Ctrl-C pour arrêter")
    try:
        while time.monotonic() - t0 < duration:
            chunk = ser.read(256)
            if not chunk:
                continue
            buf.extend(chunk)
            while True:
                start = buf.find(0x3B)
                if start < 0:
                    buf.clear()
                    break
                if start:
                    del buf[:start]
                if len(buf) < 2:
                    break
                need = buf[1] + 3  # 0x3b + len + len octets + checksum
                if len(buf) < need:
                    break
                frame = bytes(buf[:need])
                del buf[:need]
                seen += 1
                src, dst, cmd = frame[2], frame[3], frame[4]
                data = frame[5:-1]
                print(
                    f"{time.monotonic() - t0:8.3f}  "
                    f"{name(src):>5} -> {name(dst):<5}  "
                    f"{cmd_name(cmd, src, dst):<22} "
                    f"data={data.hex(' ') or '-':<20} "
                    f"raw={frame.hex(' ')}",
                    flush=True,
                )
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
    print(f"# {seen} trames")


if __name__ == "__main__":
    main()
