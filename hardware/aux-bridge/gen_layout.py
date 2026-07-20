#!/usr/bin/env python3
"""Génère le PLAN D'IMPLANTATION perfboard de la carte pont AUX (layout-as-code).

Contrairement à gen_netlist.py (qui décrit la connectique logique pour KiCad),
ce script décrit le PLACEMENT PHYSIQUE sur une plaque à pastilles isolées :
chaque composant est posé sur des trous précis (col, row), et chaque liaison est
un strap/fil de trou à trou. Il émet un HTML autonome (grille SVG + tables de
trous + notes de montage) — le document qu'on suit LE FER À LA MAIN.

Repère : col croît vers la droite, row vers le bas. Pas standard 2,54 mm.
L'ESP32 est déjà soudé sur barrettes femelles à gauche : il est hors grille,
représenté comme un bloc dont 5 broches partent vers la zone interface.

Usage :
    python3 gen_layout.py     # écrit ../../docs/technical/cablage-carte-aux-perfboard.html
"""

from __future__ import annotations

from pathlib import Path

# --- Géométrie grille -------------------------------------------------------
COLS, ROWS = 24, 13
P = 34                 # pas (px)
OX, OY = 150, 24       # origine grille (px) — OX laisse la place au bloc ESP32
SVG_W = OX + (COLS + 1) * P + 20
SVG_H = OY + (ROWS + 1) * P + 40


def X(col: float) -> float:
    return OX + col * P


def Y(row: float) -> float:
    return OY + row * P


# --- Rails ------------------------------------------------------------------
RAIL5_ROW = 2
RAILG_ROW = 12
RAIL_C0, RAIL_C1 = 1, 21

# --- Circuits intégrés (DIP-14 sur support) ---------------------------------
# pins : nom -> (col, row). notch = côté encoche ('L' ou 'R').
U1 = {
    "ref": "U1 · LM2902 (RX)", "notch": "R",
    "c0": 3, "c1": 9, "rtop": 5, "rbot": 8,
    "pins": {  # seuls les pins utilisés sont tracés/étiquetés
        "4 V+":  (6, 5), "3 IN+": (7, 5), "2 IN−": (8, 5), "1 OUT": (9, 5),
        "11 GND": (6, 8),
    },
}
U2 = {
    "ref": "U2 · 74AHCT125 (TX)", "notch": "L",
    "c0": 12, "c1": 18, "rtop": 5, "rbot": 8,
    "pins": {
        "14 VCC": (12, 5), "1 /OE": (12, 8), "2 1A": (13, 8), "3 1Y": (14, 8),
        "7 GND": (18, 8),
    },
}

# --- Résistances : ref, valeur, (col,row) leg A, (col,row) leg B ------------
RES = [
    ("R3", "10k",  (10, 2), (10, 5)),   # Vréf haut : +5V -> tapVref
    ("R4", "2k2",  (10, 5), (10, 12)),  # Vréf bas  : tapVref -> GND
    ("R5", "1k",   (9, 3),  (11, 3)),   # RX out    : OUT -> tapRX
    ("R6", "4k7",  (11, 3), (11, 12)),  # RX out bas: tapRX -> GND
    ("R1", "1M",   (18, 3), (20, 3)),   # ÷2 haut   : DATA -> tapIN+
    ("R2", "1M",   (20, 3), (20, 12)),  # ÷2 bas    : tapIN+ -> GND
    ("R7", "470",  (14, 10), (16, 10)), # série TX  : 1Y -> DATA
]

# --- Condensateurs : ref, valeur, (col,row) +, (col,row) - ------------------
CAP = [
    ("C3", "10µ",  (1, 2), (1, 12)),    # réservoir près VIN ESP32
    ("C1", "100n", (2, 2), (2, 12)),    # découplage U1
    ("C2", "100n", (19, 2), (19, 12)),  # découplage U2
]

# --- Nœuds étoile (repères) -------------------------------------------------
DATA_NODE = (21, 6)
NODES = {
    "DATA": DATA_NODE, "Vréf": (10, 5), "IN+": (20, 3), "RX": (11, 3),
}

# --- Straps nus (dessus) : (c1,r1),(c2,r2), kind -----------------------------
# kind : pwr / gnd / out / sig
STRAPS_TOP = [
    ((6, 5), (6, 2), "pwr"),    # U1 V+ -> rail +5V
    ((6, 8), (6, 12), "gnd"),   # U1 GND -> rail GND
    ((12, 5), (12, 2), "pwr"),  # U2 VCC -> rail +5V
    ((18, 8), (18, 12), "gnd"), # U2 GND -> rail GND
    ((9, 3), (9, 5), "out"),    # R5 -> U1 OUT p1
    ((14, 8), (14, 10), "out"), # U2 1Y p3 -> R7
    ((22, 8), (22, 12), "gnd"), # RJ12 GND -> rail GND
]

# --- Fils isolés au dos : (c1,r1),(c2,r2), kind, label -----------------------
WIRES_BACK = [
    ((10, 5), (8, 5), "sig", "Vréf→IN−"),      # tapVref -> U1 p2
    ((20, 3), (7, 5), "sig", "IN+→p3"),        # tapIN+ -> U1 p3
    ((18, 3), (21, 6), "sig", "→DATA"),        # R1 -> DATA node
    ((16, 10), (21, 6), "out", "→DATA"),       # R7 -> DATA node
    ((22, 6), (21, 6), "sig", ""),             # RJ12 DATA -> DATA node
]

# --- Connexions ESP32 (bloc hors grille) : pin, (col,row) cible, kind --------
ESP_BLK = {"x": 10, "y": 96, "w": 128, "h": 320}
ESP_WIRES = [
    ("VIN",    (1, 2),  "pwr"),
    ("GND",    (1, 12), "gnd"),
    ("GPIO16", (11, 3), "out"),   # <- RX tap
    ("GPIO17", (13, 8), "sig"),   # -> U2 1A
    ("GPIO32", (12, 8), "sig"),   # -> U2 /OE
]

# --- RJ-12 (bloc à droite) --------------------------------------------------
RJ12 = {"c0": 22, "c1": 23, "r0": 4, "r1": 9,
        "pins": {"3 +12V": (22, 5), "4 DATA": (22, 6), "5 GND": (22, 8)}}

# --- Bornier 5V (bas gauche) ------------------------------------------------
J2 = {"plus": (1, 13), "minus": (2, 13)}

COLORS = {
    "bg": "#0a0e1a", "grid": "#1b2740", "hole": "#0d1424", "holek": "#2a3c60",
    "txt": "#c8d6f0", "dim": "#6f82a8", "line": "#1e2c47", "panel": "#111a2e",
    "pwr": "#ffb454", "gnd": "#7184a8", "sig": "#4fd1ff", "out": "#4fe0a0",
    "cap": "#c58bff", "res": "#d9b56b", "warn": "#ff5d6c", "ic": "#16223c",
}


def svg() -> str:
    s: list[str] = []
    s.append(f'<svg viewBox="0 0 {SVG_W} {SVG_H}" width="100%" '
             f'style="max-width:{SVG_W}px" role="img" '
             f'aria-label="Plan d\'implantation perfboard du pont AUX">')

    # rails (fil nu épais)
    s.append(f'<line x1="{X(RAIL_C0)}" y1="{Y(RAIL5_ROW)}" x2="{X(RAIL_C1)}" '
             f'y2="{Y(RAIL5_ROW)}" stroke="{COLORS["pwr"]}" stroke-width="7" '
             f'stroke-linecap="round" opacity="0.85"/>')
    s.append(f'<line x1="{X(RAIL_C0)}" y1="{Y(RAILG_ROW)}" x2="{X(RAIL_C1)}" '
             f'y2="{Y(RAILG_ROW)}" stroke="{COLORS["gnd"]}" stroke-width="7" '
             f'stroke-linecap="round" opacity="0.85"/>')
    s.append(f'<text x="{X(RAIL_C0)}" y="{Y(RAIL5_ROW)-12}" fill="{COLORS["pwr"]}" '
             f'font-size="12" font-weight="700">RAIL +5 V — fil étamé nu</text>')
    s.append(f'<text x="{X(RAIL_C0)}" y="{Y(RAILG_ROW)+22}" fill="{COLORS["gnd"]}" '
             f'font-size="12" font-weight="700">RAIL GND — fil étamé nu</text>')

    # trous
    for c in range(1, COLS + 1):
        for r in range(1, ROWS + 1):
            s.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="3.2" '
                     f'fill="{COLORS["hole"]}" stroke="{COLORS["holek"]}" stroke-width="1"/>')
    # repères de colonnes (haut)
    for c in range(1, COLS + 1):
        if c % 2 == 1:
            s.append(f'<text x="{X(c)}" y="{OY-2}" fill="{COLORS["dim"]}" '
                     f'font-size="9" text-anchor="middle">{c}</text>')

    # condensateurs (violet) : ligne + petit corps + label
    for ref, val, a, b in CAP:
        x1, y1, x2, y2 = X(a[0]), Y(a[1]), X(b[0]), Y(b[1])
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{COLORS["cap"]}" stroke-width="2.5"/>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        s.append(f'<rect x="{mx-6}" y="{my-9}" width="12" height="18" rx="3" '
                 f'fill="{COLORS["bg"]}" stroke="{COLORS["cap"]}" stroke-width="1.6"/>')
        s.append(f'<text x="{mx+10}" y="{my+3}" fill="{COLORS["cap"]}" '
                 f'font-size="10">{ref} {val}</text>')

    # résistances (corps beige) : legs + corps + label
    for ref, val, a, b in RES:
        x1, y1, x2, y2 = X(a[0]), Y(a[1]), X(b[0]), Y(b[1])
        horiz = a[1] == b[1]
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{COLORS["res"]}" stroke-width="2"/>')
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if horiz:
            s.append(f'<rect x="{mx-14}" y="{my-6}" width="28" height="12" rx="3" '
                     f'fill="{COLORS["bg"]}" stroke="{COLORS["res"]}" stroke-width="1.6"/>')
            s.append(f'<text x="{mx}" y="{my-10}" fill="{COLORS["res"]}" '
                     f'font-size="10" text-anchor="middle">{ref} {val}</text>')
        else:
            s.append(f'<rect x="{mx-6}" y="{my-14}" width="12" height="28" rx="3" '
                     f'fill="{COLORS["bg"]}" stroke="{COLORS["res"]}" stroke-width="1.6"/>')
            s.append(f'<text x="{mx+10}" y="{my+3}" fill="{COLORS["res"]}" '
                     f'font-size="10">{ref} {val}</text>')

    # fils dos (pointillés) — tracés d'abord pour passer sous les CI/pastilles
    for a, b, kind, label in WIRES_BACK:
        x1, y1, x2, y2 = X(a[0]), Y(a[1]), X(b[0]), Y(b[1])
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                 f'stroke="{COLORS[kind]}" stroke-width="2" stroke-dasharray="5 4" '
                 f'opacity="0.9"/>')
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            s.append(f'<text x="{mx}" y="{my-4}" fill="{COLORS[kind]}" '
                     f'font-size="9" text-anchor="middle">{label}</text>')

    # straps nus (pleins)
    for a, b, kind in STRAPS_TOP:
        s.append(f'<line x1="{X(a[0])}" y1="{Y(a[1])}" x2="{X(b[0])}" y2="{Y(b[1])}" '
                 f'stroke="{COLORS[kind]}" stroke-width="3"/>')

    # circuits intégrés
    for ic in (U1, U2):
        bx, by = X(ic["c0"]) - 15, Y(ic["rtop"]) - 15
        bw = X(ic["c1"]) - X(ic["c0"]) + 30
        bh = Y(ic["rbot"]) - Y(ic["rtop"]) + 30
        s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="7" '
                 f'fill="{COLORS["ic"]}" stroke="{COLORS["dim"]}" stroke-width="1.6" opacity="0.92"/>')
        # encoche
        ny = by + bh / 2
        if ic["notch"] == "L":
            s.append(f'<path d="M{bx},{ny-11} a11,11 0 0,1 0,22" fill="none" '
                     f'stroke="{COLORS["txt"]}" stroke-width="2"/>')
        else:
            s.append(f'<path d="M{bx+bw},{ny-11} a11,11 0 0,0 0,22" fill="none" '
                     f'stroke="{COLORS["txt"]}" stroke-width="2"/>')
        s.append(f'<text x="{bx+bw/2}" y="{by-6}" fill="{COLORS["txt"]}" '
                 f'font-size="12" font-weight="700" text-anchor="middle">{ic["ref"]}'
                 f'  <tspan fill="{COLORS["dim"]}">encoche {"◀" if ic["notch"]=="L" else "▶"}</tspan></text>')
        # pins utilisés
        for name, (c, r) in ic["pins"].items():
            s.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="4.5" fill="{COLORS["sig"]}"/>')
            below = r == ic["rbot"]
            ty = Y(r) + 16 if below else Y(r) - 9
            s.append(f'<text x="{X(c)}" y="{ty}" fill="{COLORS["dim"]}" '
                     f'font-size="8.5" text-anchor="middle">{name}</text>')

    # nœuds étoile
    for label, (c, r) in NODES.items():
        s.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="5.5" fill="none" '
                 f'stroke="{COLORS["sig"]}" stroke-width="2"/>')
        s.append(f'<text x="{X(c)+8}" y="{Y(r)-6}" fill="{COLORS["sig"]}" '
                 f'font-size="9" font-weight="700">{label}</text>')

    # RJ-12
    bx, by = X(RJ12["c0"]) - 14, Y(RJ12["r0"]) - 6
    bw = X(RJ12["c1"]) - X(RJ12["c0"]) + 28
    bh = Y(RJ12["r1"]) - Y(RJ12["r0"]) + 12
    s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="7" '
             f'fill="{COLORS["panel"]}" stroke="{COLORS["dim"]}" stroke-width="1.6"/>')
    s.append(f'<text x="{bx+bw/2}" y="{by-6}" fill="{COLORS["txt"]}" font-size="11" '
             f'font-weight="700" text-anchor="middle">J1 · RJ-12</text>')
    for name, (c, r) in RJ12["pins"].items():
        warn = "+12V" in name
        col = COLORS["warn"] if warn else COLORS["sig"] if "DATA" in name else COLORS["gnd"]
        s.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="4.5" fill="{col}"/>')
        s.append(f'<text x="{X(c)+9}" y="{Y(r)+3}" fill="{col}" font-size="9">'
                 f'{name}{" ✗NC" if warn else ""}</text>')

    # bornier J2
    s.append(f'<circle cx="{X(J2["plus"][0])}" cy="{Y(J2["plus"][1])}" r="4.5" fill="{COLORS["pwr"]}"/>')
    s.append(f'<circle cx="{X(J2["minus"][0])}" cy="{Y(J2["minus"][1])}" r="4.5" fill="{COLORS["gnd"]}"/>')
    s.append(f'<text x="{X(J2["plus"][0])-6}" y="{Y(J2["plus"][1])+16}" fill="{COLORS["dim"]}" '
             f'font-size="9">J2 5V+</text>')
    s.append(f'<text x="{X(J2["minus"][0])+8}" y="{Y(J2["minus"][1])+16}" fill="{COLORS["dim"]}" '
             f'font-size="9">GND</text>')
    # J2 -> rails (fils dos)
    s.append(f'<line x1="{X(J2["plus"][0])}" y1="{Y(J2["plus"][1])}" x2="{X(1)}" y2="{Y(RAIL5_ROW)}" '
             f'stroke="{COLORS["pwr"]}" stroke-width="2" stroke-dasharray="5 4"/>')
    s.append(f'<line x1="{X(J2["minus"][0])}" y1="{Y(J2["minus"][1])}" x2="{X(2)}" y2="{Y(RAILG_ROW)}" '
             f'stroke="{COLORS["gnd"]}" stroke-width="2" stroke-dasharray="5 4"/>')

    # bloc ESP32 (hors grille)
    e = ESP_BLK
    s.append(f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["w"]}" height="{e["h"]}" rx="9" '
             f'fill="{COLORS["panel"]}" stroke="{COLORS["dim"]}" stroke-width="1.6"/>')
    s.append(f'<text x="{e["x"]+e["w"]/2}" y="{e["y"]+20}" fill="{COLORS["txt"]}" '
             f'font-size="12" font-weight="700" text-anchor="middle">ESP32</text>')
    s.append(f'<text x="{e["x"]+e["w"]/2}" y="{e["y"]+36}" fill="{COLORS["dim"]}" '
             f'font-size="9" text-anchor="middle">déjà soudé · barrettes ♀</text>')
    n = len(ESP_WIRES)
    for i, (pin, (c, r), kind) in enumerate(ESP_WIRES):
        py = e["y"] + 60 + i * ((e["h"] - 80) / (n - 1))
        px = e["x"] + e["w"]
        s.append(f'<circle cx="{px}" cy="{py}" r="4" fill="{COLORS[kind]}"/>')
        s.append(f'<text x="{px-8}" y="{py+3}" fill="{COLORS[kind]}" font-size="9" '
                 f'text-anchor="end">{pin}</text>')
        s.append(f'<line x1="{px}" y1="{py}" x2="{X(c)}" y2="{Y(r)}" '
                 f'stroke="{COLORS[kind]}" stroke-width="2" stroke-dasharray="5 4"/>')

    s.append('</svg>')
    return "\n".join(s)


def rows_components() -> str:
    out = []
    for ic in (U1, U2):
        pins = " · ".join(f"{n}=({c},{r})" for n, (c, r) in ic["pins"].items())
        out.append(f'<tr><td><code>{ic["ref"]}</code></td>'
                   f'<td>cols {ic["c0"]}–{ic["c1"]}, rangées {ic["rtop"]} &amp; {ic["rbot"]} · '
                   f'encoche {"gauche" if ic["notch"]=="L" else "DROITE"}</td>'
                   f'<td>{pins}</td></tr>')
    for ref, val, a, b in RES:
        out.append(f'<tr><td><code>{ref}</code> {val}</td><td>résistance</td>'
                   f'<td>({a[0]},{a[1]}) ↔ ({b[0]},{b[1]})</td></tr>')
    for ref, val, a, b in CAP:
        out.append(f'<tr><td><code>{ref}</code> {val}</td><td>condensateur</td>'
                   f'<td>+({a[0]},{a[1]}) · −({b[0]},{b[1]})</td></tr>')
    return "\n".join(out)


def rows_wires() -> str:
    out = []
    out.append('<tr><td><code>+5V</code> rail</td><td>fil nu</td>'
               f'<td>rangée {RAIL5_ROW}, cols {RAIL_C0}→{RAIL_C1}</td></tr>')
    out.append('<tr><td><code>GND</code> rail</td><td>fil nu</td>'
               f'<td>rangée {RAILG_ROW}, cols {RAIL_C0}→{RAIL_C1}</td></tr>')
    for a, b, kind in STRAPS_TOP:
        out.append(f'<tr><td>strap</td><td>nu (dessus)</td>'
                   f'<td>({a[0]},{a[1]}) → ({b[0]},{b[1]})</td></tr>')
    for a, b, kind, label in WIRES_BACK:
        out.append(f'<tr><td>{label or "fil"}</td><td>isolé (dos)</td>'
                   f'<td>({a[0]},{a[1]}) → ({b[0]},{b[1]})</td></tr>')
    for pin, (c, r), kind in ESP_WIRES:
        out.append(f'<tr><td>ESP32 {pin}</td><td>isolé (dos)</td>'
                   f'<td>bloc ESP32 → ({c},{r})</td></tr>')
    return "\n".join(out)


HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carte pont AUX — plan d'implantation perfboard</title>
<style>
  :root {{ --bg:#0a0e1a; --panel:#111a2e; --line:#1e2c47; --txt:#c8d6f0;
    --dim:#6f82a8; --accent:#4fd1ff; --pwr:#ffb454; --gnd:#7184a8; --out:#4fe0a0;
    --cap:#c58bff; --res:#d9b56b; --warn:#ff5d6c; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt); font-size:14px; line-height:1.55;
    font-family:"SF Mono","JetBrains Mono",ui-monospace,Menlo,Consolas,monospace; }}
  .wrap {{ max-width:1060px; margin:0 auto; padding:26px 20px 80px; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  .sub {{ color:var(--dim); font-size:12px; margin-bottom:20px; }}
  h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:1.4px; color:var(--accent);
    margin:34px 0 12px; padding-left:9px; border-left:3px solid var(--accent); }}
  .legend {{ display:flex; flex-wrap:wrap; gap:7px 16px; margin:0 0 12px; font-size:11.5px; color:var(--dim); }}
  .legend span {{ display:inline-flex; align-items:center; gap:6px; }}
  .sw {{ width:20px; height:4px; border-radius:2px; display:inline-block; }}
  .schwrap {{ overflow-x:auto; background:var(--panel); border:1px solid var(--line);
    border-radius:10px; padding:12px; }}
  table {{ border-collapse:collapse; width:100%; font-size:12px; margin-top:4px; }}
  th, td {{ border:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; }}
  th {{ color:var(--accent); background:#0d1424; }}
  code {{ color:var(--accent); white-space:nowrap; }}
  .warn {{ border-left:3px solid var(--warn); background:rgba(255,93,108,.07);
    padding:11px 15px; border-radius:6px; margin:12px 0; }}
  .warn b {{ color:var(--warn); }}
  .note {{ border-left:3px solid var(--pwr); background:rgba(255,180,84,.07);
    padding:11px 15px; border-radius:6px; margin:12px 0; }}
  .note b {{ color:var(--pwr); }}
  ol, ul {{ padding-left:20px; line-height:1.7; }}
  .check {{ list-style:none; padding-left:2px; }}
  .check li {{ position:relative; padding-left:24px; margin:7px 0; }}
  .check li::before {{ content:"☐"; position:absolute; left:0; color:var(--accent); }}
  a {{ color:var(--accent); }}
  .muted {{ color:var(--dim); }}
  footer {{ margin-top:44px; color:var(--dim); font-size:11px; text-align:center; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Carte pont AUX — plan d'implantation perfboard</h1>
  <div class="sub">Plaque à pastilles isolées · à souder à la main · généré par <code>gen_layout.py</code> · 2026-07-10</div>
  <p><a href="cablage-carte-aux-pcb.html">← vue logique / PCB</a></p>

  <div class="note"><b>Comment lire.</b> Vue de DESSUS de la plaque. Les <b>gros traits</b> = straps nus posés
  sur le dessus ; les <b>pointillés</b> = fils isolés au verso (leurs croisements sont sans effet, ils sont
  isolés). Chaque composant est posé sur des trous <code>(colonne, rangée)</code> — voir tables. L'ESP32 est
  <b>déjà soudé</b> à gauche (bloc), on tire 5 fils depuis ses broches.</p>

  <h2>Plan de perçage</h2>
  <div class="legend">
    <span><i class="sw" style="background:var(--pwr)"></i>+5 V</span>
    <span><i class="sw" style="background:var(--gnd)"></i>GND</span>
    <span><i class="sw" style="background:var(--accent)"></i>signal / DATA</span>
    <span><i class="sw" style="background:var(--out)"></i>sortie RX / 1Y</span>
    <span><i class="sw" style="background:var(--res)"></i>résistance</span>
    <span><i class="sw" style="background:var(--cap)"></i>condensateur</span>
    <span><i class="sw" style="border-top:2px dashed var(--dim);height:0"></i>fil isolé (dos)</span>
  </div>
  <div class="schwrap">
{svg}
  </div>

  <h2>Composants — trous</h2>
  <table>
    <tr><th>Composant</th><th>Type / pose</th><th>Trous (col,rangée)</th></tr>
{rows_comp}
  </table>
  <p class="muted" style="margin-top:8px">RJ-12 : cols {rj0}–{rj1} · DATA=({dc},{dr}) · GND=({gc},{gr}) ·
  <b style="color:var(--warn)">+12 V=({pc},{pr}) laissé NC</b>. Bornier J2 : +({j2p}) / −({j2m}).</p>

  <h2>Rails, straps &amp; fils</h2>
  <table>
    <tr><th>Liaison</th><th>Type</th><th>De → vers (col,rangée)</th></tr>
{rows_wire}
  </table>

  <h2>Brochage &amp; orientation DIP</h2>
  <p class="muted">Les deux CI ont l'encoche dans un sens <b>différent</b> — c'est normal, imposé par leurs brochages
  (place VCC côté rail +5 V et GND côté rail GND dans les deux cas).</p>
  <ul>
    <li><b>U1 LM2902</b> — <b>encoche à DROITE</b> ▶ : p4 V+ (haut) · p11 GND (bas) · p3 IN+ · p2 IN− · p1 OUT.</li>
    <li><b>U2 74AHCT125</b> — <b>encoche à GAUCHE</b> ◀ : p14 VCC (haut) · p7 GND (bas) · p1 /OE · p2 1A · p3 1Y.</li>
  </ul>

  <div class="note"><b>Durcissement optionnel (unités inutilisées).</b> Le circuit est prouvé sans, mais pour une
  carte durable tu peux ajouter les tie-offs : LM2902 amplis B/C/D en suiveurs (<code>IN+→GND</code>, <code>OUT↔IN−</code>)
  et 74AHCT125 gates 2/3/4 (<code>/OE→+5V</code>, <code>A→GND</code>, <code>Y</code> en l'air). Non tracés ici pour garder
  la grille lisible.</div>

  <h2>Ordre de montage</h2>
  <ol>
    <li>Supports DIP-14 ×2, barrettes ESP32, RJ-12, bornier — encoche des supports comme sur le plan.</li>
    <li>Rails +5 V (haut) et GND (bas) en fil étamé nu.</li>
    <li>Straps d'alim vers les CI + découplage C1/C2/C3 au plus court.</li>
    <li>Résistances sur leurs trous, puis straps signal nus, puis fils isolés au dos.</li>
    <li>Nœud DATA + RJ-12 en dernier. <b>Broche +12 V laissée totalement isolée.</b></li>
    <li>Contrôle continuité (ci-dessous) AVANT d'enficher l'ESP32.</li>
  </ol>

  <h2>Contrôle continuité — avant mise sous tension</h2>
  <ul class="check">
    <li><b>+5 V ↔ GND : pas de court-circuit</b> (piège n°1).</li>
    <li>VIN, U1 p4, U2 p14, R3 haut, C+ tous sur le rail +5 V.</li>
    <li>GND ESP32, U1 p11, U2 p7, R2/R4/R6 bas, C−, RJ-12 p5 tous sur le rail GND.</li>
    <li>DATA relie RJ-12 p4, R1, R7 — et n'a AUCUNE continuité avec +5 V ni GND.</li>
    <li><b>RJ-12 p3 (+12 V) isolée de tout.</b></li>
    <li>Sous 5 V (ESP32 retiré) : rail ≈ 5 V · Vréf ≈ 0,9 V (U1 p2) · IN+ ≈ 2,05 V (U1 p3).</li>
  </ul>

  <div class="warn"><b>⚠️ RJ-12 broche 3 (+12 V).</b> Repérer au multimètre monture allumée AVANT branchement
  (un câble <i>reversed</i> inverse l'ordre). Un contact +12 V grille U1 / U2 / ESP32.</div>

  <footer>Astro-Brain — plan d'implantation perfboard · <code>hardware/aux-bridge/gen_layout.py</code> ·
  netlist logique : <a href="cablage-carte-aux-pcb.html">carte PCB</a>.</footer>
</div>
</body>
</html>
"""


def main() -> None:
    out = Path(__file__).resolve().parents[2] / "docs" / "technical" / "cablage-carte-aux-perfboard.html"
    html = HTML.format(
        svg=svg(),
        rows_comp=rows_components(),
        rows_wire=rows_wires(),
        rj0=RJ12["c0"], rj1=RJ12["c1"],
        dc=RJ12["pins"]["4 DATA"][0], dr=RJ12["pins"]["4 DATA"][1],
        gc=RJ12["pins"]["5 GND"][0], gr=RJ12["pins"]["5 GND"][1],
        pc=RJ12["pins"]["3 +12V"][0], pr=RJ12["pins"]["3 +12V"][1],
        j2p=f'{J2["plus"][0]},{J2["plus"][1]}', j2m=f'{J2["minus"][0]},{J2["minus"][1]}',
    )
    out.write_text(html, encoding="utf-8")
    print(f"écrit : {out}")
    print(f"  grille {COLS}×{ROWS} · {len(RES)} R · {len(CAP)} C · 2 CI · "
          f"{len(STRAPS_TOP)} straps nus · {len(WIRES_BACK)+len(ESP_WIRES)} fils dos")


if __name__ == "__main__":
    main()
