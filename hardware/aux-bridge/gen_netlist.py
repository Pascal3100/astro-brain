#!/usr/bin/env python3
"""Génère le netlist KiCad de la carte pont AUX (schéma-as-code).

La carte est décrite ici sous forme de données (composants + nets), et le script
émet un netlist KiCad importable dans Pcbnew (« File → Import Netlist » ou
« Update PCB from Netlist »). Aucune dépendance KiCad : on écrit du S-expr texte.

Source de vérité lisible : ../../docs/technical/cablage-carte-aux-pcb.html
Empreintes vérifiées présentes dans les libs KiCad 9 (snap) au moment de l'écriture.

Usage :
    python3 gen_netlist.py            # écrit aux-bridge.net à côté du script

⚠️ ESP32 (A1) : empreinte laissée VIDE (placeholder). Aucune empreinte DevKitC
   n'existe dans les libs stock — elle sera générée à tes cotes mesurées, avec des
   pads nommés VIN/GND/IO16/IO17/IO32. Le chevelu se résoudra alors par nom de pad.
"""

from __future__ import annotations

import uuid
from pathlib import Path

# --- Empreintes (lib:footprint) vérifiées présentes -------------------------
FP_DIP14   = "Package_DIP:DIP-14_W7.62mm_Socket"
FP_R       = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_C_DISC  = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_C_ELEC  = "Capacitor_THT:CP_Radial_D5.0mm_P2.50mm"
FP_RJ12    = "Connector_RJ:RJ12_Amphenol_54601-x06_Horizontal"
FP_TERM    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal"
FP_ESP32   = ""  # placeholder — à créer/assigner (voir README)

# --- Composants : ref -> (value, footprint, lib, part) ----------------------
COMPONENTS: dict[str, tuple[str, str, str, str]] = {
    "U1": ("LM2902",       FP_DIP14,  "Amplifier_Operational", "LM2902"),
    "U2": ("74AHCT125",    FP_DIP14,  "74xx",                  "74AHCT125"),
    "R1": ("1M",           FP_R,      "Device",                "R"),
    "R2": ("1M",           FP_R,      "Device",                "R"),
    "R3": ("10k",          FP_R,      "Device",                "R"),
    "R4": ("2.2k",         FP_R,      "Device",                "R"),
    "R5": ("1k",           FP_R,      "Device",                "R"),
    "R6": ("4.7k",         FP_R,      "Device",                "R"),
    "R7": ("470",          FP_R,      "Device",                "R"),
    "C1": ("100n",         FP_C_DISC, "Device",                "C"),
    "C2": ("100n",         FP_C_DISC, "Device",                "C"),
    "C3": ("10u",          FP_C_ELEC, "Device",                "CP"),
    "J1": ("AUX_RJ12",     FP_RJ12,   "Connector",             "Conn_6P6C"),
    "J2": ("5V_IN",        FP_TERM,   "Connector",             "Screw_Terminal_01x02"),
    "A1": ("ESP32-DevKitC", FP_ESP32, "MCU_Module",            "ESP32-DEVKITC-V4"),
}

# --- Nets : nom -> [(ref, pad), ...] ----------------------------------------
# Convention pads : R/C = 1,2 · DIP-14 = 1..14 · RJ12 = 1..6 · bornier = 1,2
# ESP32 pads nommés par fonction (VIN/GND/IO16/IO17/IO32).
NETS: dict[str, list[tuple[str, str]]] = {
    "+5V": [
        ("J2", "1"), ("U1", "4"), ("U2", "14"),
        ("U2", "4"), ("U2", "10"), ("U2", "13"),   # /OE des gates inutilisés → VCC
        ("A1", "VIN"), ("R3", "1"),
        ("C1", "1"), ("C2", "1"), ("C3", "1"),
    ],
    "GND": [
        ("J2", "2"), ("J1", "5"), ("U1", "11"),
        ("U1", "5"), ("U1", "10"), ("U1", "12"),   # IN+ des amplis inutilisés → GND
        ("U2", "7"), ("U2", "5"), ("U2", "9"), ("U2", "12"),  # A des gates inutilisés → GND
        ("A1", "GND"), ("R2", "2"), ("R4", "2"), ("R6", "2"),
        ("C1", "2"), ("C2", "2"), ("C3", "2"),
    ],
    "DATA": [("J1", "4"), ("R1", "1"), ("R7", "2")],
    "IN+":  [("R1", "2"), ("R2", "1"), ("U1", "3")],
    "VREF": [("R3", "2"), ("R4", "1"), ("U1", "2")],
    "RX_RAW": [("U1", "1"), ("R5", "1")],          # sortie op-amp 0/5 V
    "RX":   [("R5", "2"), ("R6", "1"), ("A1", "IO16")],   # ~2,9 V → GPIO16
    "TX_1Y": [("U2", "3"), ("R7", "1")],           # 1Y avant le 470 Ω
    "TX_DATA": [("A1", "IO17"), ("U2", "2")],      # GPIO17 → 1A
    "TX_OE":   [("A1", "IO32"), ("U2", "1")],      # GPIO32 → 1/OE
    # amplis LM2902 inutilisés câblés en suiveurs (OUT ↔ IN−), IN+ déjà à GND
    "U1_FLW_B": [("U1", "6"), ("U1", "7")],
    "U1_FLW_C": [("U1", "8"), ("U1", "9")],
    "U1_FLW_D": [("U1", "13"), ("U1", "14")],
    # NB : U2 pins 6/8/11 (sorties Y inutilisées) volontairement non connectées.
    # NB : J1 pin 3 (+12 V) volontairement NON connectée (pad isolé au routage).
}

_NS = uuid.UUID("a5730b12-0000-4000-8000-000000000000")  # namespace stable


def _tstamp(ref: str) -> str:
    """UUID déterministe par ref → diffs git propres, matching stable au ré-import."""
    return str(uuid.uuid5(_NS, ref))


def build() -> str:
    lines: list[str] = []
    lines.append('(export (version "E")')
    lines.append("  (design")
    lines.append('    (source "gen_netlist.py")')
    lines.append('    (date "")')
    lines.append('    (tool "astro-brain gen_netlist.py"))')

    # composants
    lines.append("  (components")
    for ref, (value, fp, lib, part) in COMPONENTS.items():
        lines.append(f'    (comp (ref "{ref}")')
        lines.append(f'      (value "{value}")')
        if fp:
            lines.append(f'      (footprint "{fp}")')
        lines.append(f'      (libsource (lib "{lib}") (part "{part}") (description ""))')
        lines.append('      (sheetpath (names "/") (tstamps "/"))')
        lines.append(f'      (tstamps "{_tstamp(ref)}"))')
    lines.append("  )")

    # nets
    lines.append("  (nets")
    for code, (name, nodes) in enumerate(NETS.items(), start=1):
        lines.append(f'    (net (code "{code}") (name "{name}")')
        for ref, pad in nodes:
            lines.append(f'      (node (ref "{ref}") (pin "{pad}"))')
        lines.append("    )")
    lines.append("  )")

    lines.append(")")
    return "\n".join(lines) + "\n"


def main() -> None:
    out = Path(__file__).with_name("aux-bridge.net")
    out.write_text(build(), encoding="utf-8")
    n_pins = sum(len(v) for v in NETS.values())
    print(f"écrit : {out}")
    print(f"  composants : {len(COMPONENTS)}")
    print(f"  nets       : {len(NETS)}")
    print(f"  nœuds      : {n_pins}")
    missing = [r for r, (_, fp, *_ ) in COMPONENTS.items() if not fp]
    if missing:
        print(f"  ⚠️ empreinte à assigner : {', '.join(missing)}")


if __name__ == "__main__":
    main()
