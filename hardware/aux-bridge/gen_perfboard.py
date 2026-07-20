#!/usr/bin/env python3
"""Génère les schémas *perfboard physique* de la carte pont AUX (layout-as-code).

Convention perfboard.app : plaque à pastilles vue de dessus, grille de trous, les
composants sont posés sur des trous nommés (colonne, rangée), les straps sont des
segments trou→trou. La grille est parfaite par construction ; on itère au rendu.

Émet un fragment SVG par étage (RX / TX), destiné à être inliné dans
../../docs/technical/cablage-interface-aux.html.

Usage :
    python3 gen_perfboard.py            # écrit *_preview.html à côté (rendu standalone)
"""

from __future__ import annotations

from pathlib import Path

# --- grille --------------------------------------------------------------
S = 34            # pas entre trous (px)
X0, Y0 = 60, 70   # origine (centre du trou col0,row0)

# --- palette (claire, façon perfboard.app) -------------------------------
BOARD   = "#e9dfc9"     # phénolique
HOLE    = "#c2a05a"     # pastille cuivre
HOLE_IN = "#4a3f2a"     # trou
INK     = "#3a3324"
DIM     = "#8a7d5f"
NET = {
    "pwr":  "#e0912f",  # +5 V
    "gnd":  "#7f8aa0",  # GND
    "sig":  "#2f92d0",  # DATA / entrées
    "ref":  "#9b5fc7",  # Vréf
    "out":  "#26a074",  # sortie → GPIO
    "warn": "#d6503f",  # +12 V — NE PAS CONNECTER
    "aux":  "#8b93a4",  # jumpers de tie-off (pins inutilisés)
}
RES_BODY, RES_EDGE = "#cb9e63", "#7a5a2c"
CAP_BODY, CAP_EDGE = "#5aa0d0", "#2f6f9c"
DIP_BODY, DIP_EDGE = "#20242e", "#454b5a"
LEG = "#b9c0cc"


def hx(c: float) -> float: return X0 + c * S
def hy(r: float) -> float: return Y0 + r * S


class Board:
    def __init__(self, cols: int, rows: int, title: str) -> None:
        self.cols, self.rows, self.title = cols, rows, title
        self.holes: list[str] = []
        self.wires: list[str] = []   # straps (sous les composants)
        self.parts: list[str] = []   # composants (au-dessus)
        self.marks: list[str] = []   # labels, nœuds, hops (tout au-dessus)

    # -- fond + grille de trous ------------------------------------------
    def board(self) -> None:
        w = hx(self.cols - 1) + 40
        h = hy(self.rows - 1) + 30
        self.holes.append(
            f'<rect x="20" y="30" width="{w - 20}" height="{h - 20}" rx="10" '
            f'fill="{BOARD}" stroke="#cbbf9f" stroke-width="1.5"/>')
        for r in range(self.rows):
            for c in range(self.cols):
                x, y = hx(c), hy(r)
                self.holes.append(
                    f'<circle cx="{x}" cy="{y}" r="4.2" fill="{HOLE}"/>'
                    f'<circle cx="{x}" cy="{y}" r="1.8" fill="{HOLE_IN}"/>')

    # -- rail d'alimentation (bus le long d'une rangée) ------------------
    def rail(self, row: int, c0: int, c1: int, net: str, label: str) -> None:
        col = NET[net]
        self.wires.append(
            f'<line x1="{hx(c0)}" y1="{hy(row)}" x2="{hx(c1)}" y2="{hy(row)}" '
            f'stroke="{col}" stroke-width="6" stroke-linecap="round" opacity=".9"/>')
        self.marks.append(
            f'<text x="{hx(c0)}" y="{hy(row) - 12}" font-size="12" font-weight="700" '
            f'fill="{col}">{label}</text>')

    # -- résistance (corps + 3 bandes + pattes vers 2 trous) -------------
    def res(self, c0: int, r0: int, c1: int, r1: int, label: str) -> None:
        x0, y0, x1, y1 = hx(c0), hy(r0), hx(c1), hy(r1)
        horiz = r0 == r1
        col = NET["gnd"]  # les pattes prennent la couleur du fil courant ? non → neutre
        if horiz:
            bx0, bx1 = min(x0, x1), max(x0, x1)
            bl = bx1 - bx0
            bodyx, bodyw = bx0 + bl * .22, bl * .56
            self.parts.append(
                f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#9a9a9a" stroke-width="2.5"/>'
                f'<rect x="{bodyx}" y="{y0 - 11}" width="{bodyw}" height="22" rx="5" '
                f'fill="{RES_BODY}" stroke="{RES_EDGE}" stroke-width="1.5"/>')
            for i, cc in enumerate(("#caa000", "#7a3fb0", "#6b4a2a")):
                self.parts.append(
                    f'<rect x="{bodyx + 8 + i * 9}" y="{y0 - 11}" width="4" height="22" fill="{cc}"/>')
            self.marks.append(
                f'<text x="{(bx0 + bx1) / 2}" y="{y0 - 16}" text-anchor="middle" '
                f'font-size="11" fill="{DIM}">{label}</text>')
        else:
            by0, by1 = min(y0, y1), max(y0, y1)
            bl = by1 - by0
            bodyy, bodyh = by0 + bl * .22, bl * .56
            self.parts.append(
                f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#9a9a9a" stroke-width="2.5"/>'
                f'<rect x="{x0 - 11}" y="{bodyy}" width="22" height="{bodyh}" rx="5" '
                f'fill="{RES_BODY}" stroke="{RES_EDGE}" stroke-width="1.5"/>')
            for i, cc in enumerate(("#caa000", "#7a3fb0", "#6b4a2a")):
                self.parts.append(
                    f'<rect x="{x0 - 11}" y="{bodyy + 8 + i * 9}" width="22" height="4" fill="{cc}"/>')
            self.marks.append(
                f'<text x="{x0 + 15}" y="{(by0 + by1) / 2 + 4}" '
                f'font-size="11" fill="{DIM}">{label}</text>')

    # -- condensateur céramique -----------------------------------------
    def cap(self, c0: int, r0: int, c1: int, r1: int, label: str) -> None:
        x0, y0, x1, y1 = hx(c0), hy(r0), hx(c1), hy(r1)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        self.parts.append(
            f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#9a9a9a" stroke-width="2.5"/>'
            f'<rect x="{mx - 13}" y="{my - 11}" width="26" height="22" rx="8" '
            f'fill="{CAP_BODY}" stroke="{CAP_EDGE}" stroke-width="1.5"/>')
        self.marks.append(
            f'<text x="{mx + 16}" y="{my + 4}" font-size="11" fill="{DIM}">{label}</text>')

    # -- boîtier DIP (vu de dessus, pin1 en bas-gauche) ------------------
    def dip(self, c0: int, r_top: int, r_bot: int, npins_side: int,
            name: str, funcs: dict[int, str]) -> None:
        """funcs : pin -> net (colore le numéro de la patte utilisée)."""
        x0 = hx(c0) - 15
        x1 = hx(c0 + npins_side - 1) + 15
        yt, yb = hy(r_top), hy(r_bot)
        self.parts.append(
            f'<rect x="{x0}" y="{yt - 4}" width="{x1 - x0}" height="{yb - yt + 8}" rx="7" '
            f'fill="{DIP_BODY}" stroke="{DIP_EDGE}" stroke-width="2"/>')
        # encoche gauche + point patte 1
        self.parts.append(
            f'<path d="M{(x0 + x1) / 2 - 10},{yt - 4} a10,10 0 0,0 20,0" fill="none" '
            f'stroke="{DIP_EDGE}" stroke-width="2"/>')
        self.parts.append(f'<circle cx="{hx(c0)}" cy="{yb - 11}" r="3" fill="#8fa0c0"/>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(yt + yb) / 2 + 4}" text-anchor="middle" '
            f'font-size="13" font-weight="700" fill="#e8ecf4">{name}</text>')
        # pattes : bas = 1..n (g→d), haut = 2n..n+1 (g→d)
        for i in range(npins_side):
            pin_b = i + 1
            pin_t = 2 * npins_side - i
            xb = hx(c0 + i)
            for (pin, y, up) in ((pin_b, yb, False), (pin_t, yt, True)):
                leg_y = y + 8 if not up else y - 8
                self.parts.append(
                    f'<rect x="{xb - 4}" y="{min(y, leg_y)}" width="8" height="8" fill="{LEG}"/>')
                dy = 15 if not up else -9
                net = funcs.get(pin)
                col = NET[net] if net else DIM
                weight = "700" if net else "400"
                self.marks.append(
                    f'<text x="{xb}" y="{y + dy}" text-anchor="middle" font-size="10" '
                    f'font-weight="{weight}" fill="{col}">{pin}</text>')

    # -- strap (polyline trou→trou, coins nets) --------------------------
    def strap(self, pts: list[tuple[int, int]], net: str, hops: list[tuple[int, int]] | None = None) -> None:
        col = NET[net]
        d = f'M{hx(pts[0][0])},{hy(pts[0][1])}'
        for c, r in pts[1:]:
            d += f' L{hx(c)},{hy(r)}'
        self.wires.append(
            f'<path d="{d}" fill="none" stroke="{col}" stroke-width="3.4" '
            f'stroke-linejoin="round" stroke-linecap="round"/>')
        for c, r in (pts[0], pts[-1]):
            self.wires.append(f'<circle cx="{hx(c)}" cy="{hy(r)}" r="4" fill="{col}"/>')
        for c, r in (hops or []):
            self.marks.append(
                f'<path d="M{hx(c) - 8},{hy(r)} q8,-10 16,0" fill="none" '
                f'stroke="{col}" stroke-width="3.4"/>')

    # -- nœud (jonction) + tension --------------------------------------
    def node(self, c: int, r: int, net: str, label: str = "", volt: str = "") -> None:
        col = NET[net]
        self.marks.append(f'<circle cx="{hx(c)}" cy="{hy(r)}" r="4.5" fill="{col}"/>')
        if volt:
            self.marks.append(
                f'<text x="{hx(c)}" y="{hy(r) - 10}" text-anchor="middle" font-size="10.5" '
                f'font-weight="700" fill="{col}">{volt}</text>')
        if label:
            self.marks.append(
                f'<text x="{hx(c) + 8}" y="{hy(r) + 4}" font-size="10.5" fill="{col}">{label}</text>')

    # -- pad connecteur au bord -----------------------------------------
    def pad(self, c: int, r: int, net: str, label: str, side: str = "left") -> None:
        col = NET[net]
        x, y = hx(c), hy(r)
        self.parts.append(
            f'<rect x="{x - 9}" y="{y - 9}" width="18" height="18" rx="3" '
            f'fill="none" stroke="{col}" stroke-width="2.2"/>')
        tx = x - 15 if side == "left" else x + 15
        anc = "end" if side == "left" else "start"
        self.marks.append(
            f'<text x="{tx}" y="{y + 4}" text-anchor="{anc}" font-size="11" '
            f'font-weight="700" fill="{col}">{label}</text>')

    # -- bloc posé (module ESP32 / connecteur) : rect + titre ------------
    def block(self, c0: int, r0: int, c1: int, r1: int, title: str,
              fill: str, edge: str, sub: str = "", tcol: str = "#e8ecf4") -> None:
        x0, y0 = hx(c0) - 16, hy(r0) - 16
        x1, y1 = hx(c1) + 16, hy(r1) + 16
        self.parts.append(
            f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="8" '
            f'fill="{fill}" stroke="{edge}" stroke-width="2"/>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(y0 + y1) / 2 + 4}" text-anchor="middle" '
            f'font-size="13" font-weight="700" fill="{tcol}">{title}</text>')
        if sub:
            self.parts.append(
                f'<text x="{(x0 + x1) / 2}" y="{(y0 + y1) / 2 + 20}" text-anchor="middle" '
                f'font-size="9.5" fill="{tcol}" opacity=".8">{sub}</text>')

    # -- broche d'un bloc posé (pastille colorée + libellé) --------------
    def bpin(self, c: int, r: int, net: str, label: str, dy: int = 16) -> None:
        col = NET[net]
        x, y = hx(c), hy(r)
        self.parts.append(
            f'<circle cx="{x}" cy="{y}" r="5.5" fill="{col}" stroke="#2a2418" stroke-width="1"/>')
        self.marks.append(
            f'<text x="{x}" y="{y + dy}" text-anchor="middle" font-size="9" '
            f'font-weight="700" fill="{col}">{label}</text>')

    # -- module ESP32 : empreinte à 2 rangées de pattes nommées ----------
    def esp32(self, c0: int, r_top: int, r_bot: int,
              top: list[str], bot: list[str],
              used: dict[tuple[str, int], str]) -> None:
        n = len(top)
        x0, x1 = hx(c0) - 15, hx(c0 + n - 1) + 15
        yt, yb = hy(r_top), hy(r_bot)
        self.parts.append(
            f'<rect x="{x0}" y="{yt - 9}" width="{x1 - x0}" height="{yb - yt + 18}" rx="8" '
            f'fill="#173026" stroke="#2e6a4f" stroke-width="2"/>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(yt + yb) / 2 - 3}" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="#cfe0d5">ESP32 DevKitC</text>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(yt + yb) / 2 + 15}" text-anchor="middle" '
            f'font-size="9" fill="#cfe0d5" opacity=".75">déjà enfiché sur 2 barrettes femelles</text>')
        for side, r, labels, ldy in (("t", r_top, top, 20), ("b", r_bot, bot, -20)):
            y = hy(r)
            for i, lab in enumerate(labels):
                x = hx(c0 + i)
                net = used.get((side, i))
                col = NET[net] if net else "#5f7469"
                legy = y - 9 if side == "t" else y + 1
                self.parts.append(
                    f'<rect x="{x - 4}" y="{legy}" width="8" height="8" '
                    f'fill="{col if net else LEG}"/>')
                if net:
                    self.marks.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{col}"/>')
                ly = y + ldy
                self.marks.append(
                    f'<text transform="rotate(-90 {x} {ly})" x="{x}" y="{ly + 3}" '
                    f'text-anchor="middle" font-size="7.5" '
                    f'font-weight="{"700" if net else "400"}" fill="{col}">{lab}</text>')

    # -- connecteur posé (RJ-12 6 pins, bornier 2 pins) -----------------
    def connector(self, c0: int, r_pins: int, npins: int, name: str, sub: str,
                  pins: dict[int, tuple[str, str]], body_above: bool) -> None:
        x0, x1 = hx(c0) - 13, hx(c0 + npins - 1) + 13
        yp = hy(r_pins)
        if body_above:
            by0, by1 = yp - 14 - 42, yp - 14
        else:
            by0, by1 = yp + 14, yp + 14 + 42
        self.parts.append(
            f'<rect x="{x0}" y="{by0}" width="{x1 - x0}" height="{by1 - by0}" rx="6" '
            f'fill="#242832" stroke="#556" stroke-width="2"/>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(by0 + by1) / 2 - 2}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#dfe4ee">{name}</text>')
        self.parts.append(
            f'<text x="{(x0 + x1) / 2}" y="{(by0 + by1) / 2 + 13}" text-anchor="middle" '
            f'font-size="8.5" fill="#dfe4ee" opacity=".75">{sub}</text>')
        for i in range(npins):
            x = hx(c0 + i)
            info = pins.get(i)
            col = NET[info[1]] if info else "#6a7285"
            self.parts.append(
                f'<circle cx="{x}" cy="{yp}" r="5.5" fill="{col}" stroke="#1a1e26" stroke-width="1"/>')
            ny = yp + (16 if not body_above else -10)
            self.marks.append(
                f'<text x="{x}" y="{ny}" text-anchor="middle" font-size="8" '
                f'font-weight="700" fill="{col}">{i + 1}</text>')
            if info:
                fy = yp + (27 if not body_above else -21)
                self.marks.append(
                    f'<text x="{x}" y="{fy}" text-anchor="middle" font-size="7.5" '
                    f'fill="{col}">{info[0]}</text>')

    # -- connecteur vertical (pins en colonne, corps à droite) ----------
    def vconnector(self, c_pin: int, r0: int, npins: int, name: str, sub: str,
                   pins: dict[int, tuple[str, str]]) -> None:
        xp = hx(c_pin)
        bx0, bx1 = hx(c_pin + 1) - 6, hx(c_pin + 4) + 10
        by0, by1 = hy(r0) - 15, hy(r0 + npins - 1) + 15
        self.parts.append(
            f'<rect x="{bx0}" y="{by0}" width="{bx1 - bx0}" height="{by1 - by0}" rx="6" '
            f'fill="#242832" stroke="#556" stroke-width="2"/>')
        cx = (bx0 + bx1) / 2
        self.parts.append(
            f'<text x="{cx}" y="{by0 + 18}" text-anchor="middle" font-size="12" '
            f'font-weight="700" fill="#dfe4ee">{name}</text>')
        self.parts.append(
            f'<text x="{cx}" y="{by0 + 31}" text-anchor="middle" font-size="8.5" '
            f'fill="#dfe4ee" opacity=".75">{sub}</text>')
        for i in range(npins):
            y = hy(r0 + i)
            info = pins.get(i)
            col = NET[info[1]] if info else "#6a7285"
            self.parts.append(
                f'<circle cx="{xp}" cy="{y}" r="5.5" fill="{col}" stroke="#1a1e26" stroke-width="1"/>')
            lab = f'{i + 1} {info[0]}' if info else f'{i + 1}'
            self.marks.append(
                f'<text x="{xp - 11}" y="{y + 3}" text-anchor="end" font-size="8" '
                f'font-weight="{"700" if info else "400"}" fill="{col}">{lab}</text>')

    # -- stub : nub court depuis une patte + étiquette (tie-off compact) -
    def stub(self, c: int, r: int, net: str, label: str, dr: tuple[int, int]) -> None:
        col = NET[net]
        x, y = hx(c), hy(r)
        ex, ey = x + dr[0] * S * 0.75, y + dr[1] * S * 0.75
        self.wires.append(
            f'<line x1="{x}" y1="{y}" x2="{ex}" y2="{ey}" stroke="{col}" '
            f'stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="{ex}" cy="{ey}" r="3" fill="{col}"/>')
        lx, ly = ex + dr[0] * 12, ey + dr[1] * 6 + (10 if dr[1] >= 0 else -6)
        anc = "middle" if dr[0] == 0 else ("start" if dr[0] > 0 else "end")
        self.marks.append(
            f'<text x="{lx}" y="{ly}" text-anchor="{anc}" font-size="9" '
            f'font-weight="700" fill="{col}">{label}</text>')

    def svg(self) -> str:
        w = hx(self.cols - 1) + 40
        h = hy(self.rows - 1) + 30
        body = "\n".join(self.holes + self.wires + self.parts + self.marks)
        return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" '
                f'role="img" aria-label="{self.title}">\n{body}\n</svg>')


# =========================================================================
#  ÉTAGE RX — comparateur LM2902 (V+ pin4 / GND pin11 en milieu de rangée)
# =========================================================================
def build_rx() -> str:
    b = Board(cols=18, rows=13, title="Perfboard RX LM2902")
    b.board()
    b.rail(0, 0, 17, "pwr", "+5 V")
    b.rail(12, 0, 17, "gnd", "GND")

    # chip : cols 6..12, pattes bas row7 / haut row4  (pin1 = col6,row7)
    b.dip(6, 4, 7, 7, "LM2902",
          funcs={1: "out", 2: "ref", 3: "sig", 4: "pwr", 11: "gnd"})
    # pins utiles : OUT(6,7) IN−(7,7) IN+(8,7) V+(9,7) GND(9,4)

    # --- SORTIE (gauche, propre) : OUT → R5 → nœud → R6 → GND ; nœud → GPIO16
    b.strap([(6, 7), (6, 8), (5, 8)], "out")                     # OUT → R5
    b.res(5, 8, 3, 8, "R5 1k")                                   # R5 en série sur OUT
    b.node(3, 8, "out", volt="≈2,9 V")
    b.res(3, 8, 3, 11, "R6 4k7")                                 # nœud → GND
    b.strap([(3, 11), (3, 12)], "gnd")
    b.pad(0, 8, "out", "GPIO16")
    b.strap([(3, 8), (0, 8)], "out")                             # nœud → GPIO16

    # --- ALIM du boîtier, contournant le CI (par la droite) -------------
    b.strap([(9, 7), (9, 8), (15, 8), (15, 0)], "pwr",
            hops=[(13, 8), (14, 8)])                             # V+ → +5 V (saute Vréf)
    b.strap([(9, 4), (9, 3), (16, 3), (16, 12)], "gnd",
            hops=[(15, 3), (13, 3)])                             # GND → rail (saute V+ & R3)

    # --- Vréf (droite, près de IN−) : +5 V → R3 → nœud → R4 → GND -------
    b.res(13, 0, 13, 4, "R3 10k")
    b.node(13, 4, "ref", volt="Vréf 0,9 V")
    b.res(13, 4, 13, 7, "R4 2k2")
    b.strap([(13, 7), (13, 12)], "gnd")                          # R4 bas → GND rail
    b.strap([(13, 4), (14, 4), (14, 9), (7, 9), (7, 8), (7, 7)], "ref",
            hops=[(8, 9)])                                       # Vréf → IN− (saute la dérivation ÷2)

    # --- diviseur ÷2 (droite) : DATA → R1 → nœud → R2 → GND ; nœud → IN+
    b.node(8, 10, "sig", volt="≈2,05 V")
    b.res(8, 10, 8, 12, "R2 1M")                                 # nœud → GND rail
    b.strap([(8, 10), (8, 7)], "sig")                            # nœud → IN+ (montée col8)
    b.res(8, 10, 12, 10, "R1 1M")                                # nœud → DATA
    b.pad(12, 10, "sig", "DATA")                                 # RJ-12 p4

    # --- découplage 100 nF entre les deux straps d'alim, au ras du CI ---
    b.cap(15, 6, 16, 6, "100 nF")

    return b.svg()


# =========================================================================
#  ÉTAGE TX — buffer tri-state 74AHCT125 (gate 1 ; VCC/GND en coins → simple)
# =========================================================================
def build_tx() -> str:
    b = Board(cols=18, rows=13, title="Perfboard TX 74AHCT125")
    b.board()
    b.rail(0, 0, 17, "pwr", "+5 V")
    b.rail(12, 0, 17, "gnd", "GND")

    # chip : cols 6..12, pattes bas row7 / haut row4  (pin1 = col6,row7)
    b.dip(6, 4, 7, 7, "74AHCT125",
          funcs={1: "sig", 2: "sig", 3: "out", 14: "pwr", 7: "gnd"})
    # utiles : 1/OE(6,7)←GPIO32 · 1A(7,7)←GPIO17 · 1Y(8,7)→R7→DATA · VCC(6,4) · GND(12,7)

    # --- alim : pattes de coin → droit au rail --------------------------
    b.strap([(6, 4), (6, 0)], "pwr")                             # VCC pin14 → +5 V
    b.strap([(12, 7), (12, 12)], "gnd")                          # GND pin7  → GND

    # --- gate 1 : entrées GPIO (gauche) ---------------------------------
    b.pad(0, 9, "sig", "GPIO32")
    b.strap([(0, 9), (6, 9), (6, 7)], "sig")                     # → 1/OE (pin1)
    b.pad(0, 11, "sig", "GPIO17")
    b.strap([(0, 11), (7, 11), (7, 7)], "sig")                   # → 1A (pin2)

    # --- gate 1 : sortie 1Y → 470 Ω → DATA → monture --------------------
    b.strap([(8, 7), (8, 8)], "out")
    b.res(8, 8, 11, 8, "R7 470")
    b.node(11, 8, "out", label="DATA")
    b.strap([(11, 8), (15, 8)], "out", hops=[(12, 8)])           # saute la descente GND
    b.pad(15, 8, "out", "MONTURE", side="right")

    # --- découplage 100 nF (à monter au ras des pattes 14 & 7) ----------
    b.strap([(16, 0), (16, 5)], "pwr")
    b.cap(16, 5, 16, 8, "100 nF")
    b.strap([(16, 8), (16, 12)], "gnd")

    # gates 2·3·4 inutilisés (/OE→+5 V, A→GND, Y en l'air) : voir note + netlist.

    return b.svg()


# =========================================================================
#  CARTE COMPLÈTE — tentative / plan d'implantation (ESP32 + RJ-12 + bornier)
# =========================================================================
def build_combined() -> str:
    # Vraie plaque ROTH 16×64. Rails aux bords (r0 = +5 V, r15 = GND).
    # CI montés haut (r4/r7) pour aérer dessous ; résistances toutes à 3 pas
    # (4 trous, comme R3) ; masses des pattes inutilisées regroupées.
    b = Board(cols=64, rows=16, title="Perfboard carte AUX 16×64 (tentative)")
    b.board()
    b.rail(0, 0, 52, "pwr", "+5 V")
    b.rail(15, 0, 52, "gnd", "GND")

    # --- ESP32 déjà enfiché (gauche) : empreinte à pattes nommées -------
    TOP = ["VIN", "GND", "D13", "D12", "D14", "D27", "D26", "D25",
           "D33", "D32", "D35", "D34", "VN", "VP", "EN"]
    BOT = ["3V3", "GND", "D15", "D2", "D4", "RX2", "TX2", "D5",
           "D18", "D19", "D21", "RX0", "TX0", "D22", "D23"]
    b.esp32(1, 3, 12, TOP, BOT, {
        ("t", 0): "pwr", ("t", 1): "gnd", ("t", 9): "sig",   # VIN · GND · D32
        ("b", 1): "gnd", ("b", 5): "out", ("b", 6): "sig"})  # GND · RX2 · TX2

    # --- les 2 CI ; pattes haut r4 / bas r7 ----------------------------
    b.dip(18, 4, 7, 7, "LM2902",
          funcs={1: "out", 2: "ref", 3: "sig", 4: "pwr", 11: "gnd"})
    # RX : OUT(18,7) IN−(19,7) IN+(20,7) V+(21,7) GND(21,4)
    b.dip(30, 4, 7, 7, "74AHCT125",
          funcs={1: "sig", 2: "sig", 3: "out", 14: "pwr", 7: "gnd"})
    # TX : 1/OE(30,7) 1A(31,7) 1Y(32,7) VCC(30,4) GND(36,7)

    # --- connecteurs verticaux alignés, même design --------------------
    b.vconnector(50, 3, 2, "5 V", "bornier",
                 {0: ("+5V", "pwr"), 1: ("GND", "gnd")})
    b.vconnector(50, 8, 6, "RJ-12", "6P6C",
                 {2: ("+12V", "warn"), 3: ("DATA", "sig"), 4: ("GND", "gnd")})

    # =========== ALIM +5 V (vers le rail rangée 0) =====================
    b.strap([(1, 3), (1, 0)], "pwr")                             # ESP32 VIN
    b.strap([(21, 7), (21, 8), (25, 8), (25, 0)], "pwr")         # U1 V+ (contourne à droite)
    b.strap([(30, 4), (30, 0)], "pwr")                           # U2 VCC (montée directe)
    b.strap([(50, 3), (50, 0)], "pwr")                           # bornier +5V

    # =========== GND (vers le rail rangée 15) ==========================
    b.strap([(2, 12), (2, 15)], "gnd")                           # ESP32 GND
    b.strap([(36, 7), (36, 15)], "gnd")                          # U2 GND (descente directe)
    b.strap([(50, 4), (48, 4), (48, 15)], "gnd")                 # bornier GND
    b.strap([(50, 12), (47, 12), (47, 15)], "gnd")               # RJ-12 p5 GND

    # =========== RX : chaque diviseur pend droit sous sa patte =========
    # ÷2 sous IN+ (col20) : DATA → R1 → nœud → R2 → GND ; nœud → IN+
    b.node(20, 11, "sig", volt="2,05")
    b.res(20, 11, 23, 11, "R1 1M")
    b.res(20, 11, 20, 14, "R2 1M")
    b.strap([(20, 14), (20, 15)], "gnd")
    b.strap([(20, 11), (20, 7)], "sig")
    # Vréf sous IN− (col19) : +5 V → R3 → nœud → R4 → GND ; nœud → IN−
    b.node(19, 8, "ref", volt="0,9")
    b.res(16, 8, 19, 8, "R3 10k")
    b.strap([(16, 8), (16, 0)], "pwr")
    b.res(19, 8, 19, 11, "R4 2k2")
    b.strap([(19, 11), (19, 15)], "gnd")
    b.strap([(19, 8), (19, 7)], "ref")
    # sortie sous OUT (col18) : OUT → R5 → nœud → R6 → GND ; nœud → IO16
    # (R3 croise le strap OUT à r8, pas une résistance)
    b.strap([(18, 7), (18, 9)], "out")
    b.res(18, 9, 18, 12, "R5 1k")
    b.node(18, 12, "out", volt="2,9")
    b.res(18, 12, 18, 15, "R6 4k7")
    b.strap([(6, 12), (6, 13), (17, 13), (17, 12), (18, 12)], "out")   # IO16 (couloir r13)

    # =========== DATA : bus r11 (RJ-12 p4 ↔ R1 ÷2 ↔ R7 sortie TX) ======
    b.strap([(23, 11), (49, 11)], "sig")
    b.node(44, 11, "sig", label="DATA")
    b.strap([(50, 11), (49, 11)], "sig")                         # RJ-12 p4 → bus

    # =========== TX : sortie 1Y → R7 → DATA ; entrées ← IO17/IO32 ======
    b.strap([(32, 7), (32, 9)], "out")
    b.res(32, 9, 35, 9, "R7 470")
    b.strap([(35, 9), (35, 11)], "out")                          # R7 → bus DATA
    b.strap([(10, 3), (10, 1), (29, 1), (29, 7), (30, 7)], "sig")   # D32/IO32 → 1/OE (couloir r1)
    b.strap([(7, 12), (7, 14), (31, 14), (31, 7)], "sig")        # TX2/IO17 → 1A (couloir r14)

    # =========== LM2902 : amplis B/C/D inutilisés ======================
    # entrées inutilisées tirées à la masse (sorties 7·8·14 en l'air) :
    # haut = pins 13·12·11·10·9 sur un bus GND ; bas = entrées ampli B (5·6)
    b.strap([(19, 4), (23, 4)], "gnd")                           # bus GND : pins 13-12-11-10-9
    b.strap([(21, 4), (21, 2), (26, 2), (26, 15)], "gnd",
            hops=[(25, 2)])                                      # pin11 → rail GND (saute V+)
    b.strap([(22, 7), (23, 7)], "gnd")                           # entrées ampli B : pins 5-6
    b.strap([(22, 7), (22, 15)], "gnd")                          # → rail GND

    # =========== 74AHCT125 : gates 2/3/4 inutilisés ====================
    # /OE → +5 V, entrées A → GND, sorties Y (6·8·11) laissées libres
    b.strap([(31, 4), (31, 0)], "pwr")                           # pin13 /OE → +5 V
    b.strap([(34, 4), (34, 0)], "pwr")                           # pin10 /OE → +5 V
    b.strap([(33, 7), (33, 8), (38, 8), (38, 0)], "pwr")         # pin4 /OE → +5 V
    b.strap([(34, 7), (34, 15)], "gnd")                          # pin5 A → GND
    b.strap([(35, 4), (35, 3), (39, 3), (39, 15)], "gnd")        # pin9 A → GND
    b.strap([(32, 4), (32, 3), (39, 3)], "gnd")                  # pin12 A → GND

    # =========== découplage : 100 nF AU RAS du CI ; 10 µF à l'entrée ===
    b.cap(27, 7, 27, 10, "C1 100n")                              # collé au LM2902
    b.strap([(27, 7), (27, 0)], "pwr")
    b.strap([(27, 10), (27, 15)], "gnd")
    b.cap(37, 7, 37, 10, "C2 100n")                              # collé au 74AHCT125
    b.strap([(37, 7), (37, 0)], "pwr")
    b.strap([(37, 10), (37, 15)], "gnd")
    b.cap(46, 7, 46, 10, "C3 10µ")                               # réservoir à l'entrée 5 V
    b.strap([(46, 7), (46, 0)], "pwr")
    b.strap([(46, 10), (46, 15)], "gnd")

    return b.svg()


def main() -> None:
    rx, tx = build_rx(), build_tx()
    block = 'margin:0 auto 34px;max-width:760px'
    html = (
        '<!DOCTYPE html><meta charset="utf-8">'
        '<body style="background:#f4efe4;margin:0;padding:24px;'
        'font-family:ui-monospace,Menlo,Consolas,monospace">'
        f'<div style="{block}"><h3>RX — LM2902</h3>{rx}</div>'
        f'<div style="{block}"><h3>TX — 74AHCT125</h3>{tx}</div>'
        f'<div style="margin:0 auto 34px;overflow-x:auto"><h3>Carte complète (tentative)</h3>'
        f'{build_combined()}</div></body>')
    out = Path(__file__).with_name("perfboard_preview.html")
    out.write_text(html, encoding="utf-8")
    print(f"écrit : {out}")


if __name__ == "__main__":
    main()
