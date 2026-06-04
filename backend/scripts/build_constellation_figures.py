"""Build one-shot de l'asset des figures de constellations.

Lit les tracés Stellarium (.fab, paires de HIP) + la base HYG (HIP→coord),
filtre aux constellations des 32 étoiles d'alignement, et émet
`astro_brain/data/constellation_figures.json`. NE TOURNE PAS au runtime.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from astro_brain.services._alignment_catalog import constellation_of, load_catalog

# Abréviation IAU → nom français (constellations utiles côté alignement).
_FR_NAMES = {
    "UMa": "Grande Ourse", "UMi": "Petite Ourse", "CMa": "Grand Chien",
    "CMi": "Petit Chien", "Ori": "Orion", "Tau": "Taureau", "Leo": "Lion",
    "Boo": "Bouvier", "Lyr": "Lyre", "Aql": "Aigle", "Cyg": "Cygne",
    "Sco": "Scorpion", "Vir": "Vierge", "Gem": "Gémeaux", "Aur": "Cocher",
    "Per": "Persée", "And": "Andromède", "Peg": "Pégase", "Cas": "Cassiopée",
    "Cep": "Céphée", "Car": "Carène", "Cen": "Centaure", "Cru": "Croix du Sud",
    "PsA": "Poisson Austral", "Sgr": "Sagittaire", "Eri": "Éridan",
    "Gru": "Grue", "Oph": "Ophiuchus", "Aqr": "Verseau",
    "Ari": "Bélier", "CrB": "Couronne boréale", "Cet": "Baleine", "Hya": "Hydre",
}


def parse_fab_lines(text: str) -> dict[str, list[tuple[int, int]]]:
    """Parse le format .fab → {abbr: [(hip_a, hip_b), ...]}.

    Chaque ligne : <Abbr> <n_segments> <hip> <hip> <hip> <hip> ...
    (2*n_segments HIP, lus par paires).
    """
    figures: dict[str, list[tuple[int, int]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tok = line.split()
        abbr, n = tok[0], int(tok[1])
        hips = [int(h) for h in tok[2 : 2 + 2 * n]]
        figures[abbr] = [(hips[i], hips[i + 1]) for i in range(0, len(hips), 2)]
    return figures


def _load_hyg(path: Path) -> dict[int, dict]:
    """HIP → {ra_deg, dec_deg, mag, label}.

    Colonnes HYG v3 utilisées : ``hip``, ``proper``, ``bayer``, ``ra``
    (heures → converti en degrés ×15), ``dec``, ``mag``.
    """
    by_hip: dict[int, dict] = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            hip = row.get("hip")
            if not hip:
                continue
            label = row.get("proper") or row.get("bayer") or f"HIP {hip}"
            by_hip[int(hip)] = {
                "ra_deg": float(row["ra"]) * 15.0,
                "dec_deg": float(row["dec"]),
                "mag": float(row["mag"]),
                "label": label.strip(),
            }
    return by_hip


def build(data_dir: Path, out_path: Path) -> dict:
    """Construit l'asset JSON et l'écrit dans ``out_path``.

    Return le dictionnaire généré (pratique pour les tests d'intégration).
    """
    needed = {
        abbr
        for abbr in (constellation_of(s) for s in load_catalog())
        if abbr is not None
    }
    fab = parse_fab_lines((data_dir / "western_lines.fab").read_text())
    hyg = _load_hyg(data_dir / "hyg_v3.csv")

    out: dict[str, dict] = {}
    for abbr, seg_hips in fab.items():
        if abbr not in needed:
            continue
        hip_order: list[int] = []
        for a, b in seg_hips:
            for h in (a, b):
                if h not in hip_order:
                    hip_order.append(h)
        filtered_hips = [h for h in hip_order if h in hyg]
        index = {h: i for i, h in enumerate(filtered_hips)}
        nodes = [
            {
                "label": hyg[h]["label"],
                "ra_deg": round(hyg[h]["ra_deg"], 5),
                "dec_deg": round(hyg[h]["dec_deg"], 5),
                "mag": hyg[h]["mag"],
            }
            for h in filtered_hips
        ]
        if len(nodes) < 2:
            continue
        segments = [
            [index[a], index[b]]
            for a, b in seg_hips
            if a in hyg and b in hyg
        ]
        out[abbr] = {
            "name": _FR_NAMES.get(abbr, abbr),
            "nodes": nodes,
            "segments": segments,
        }

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    here = Path(__file__).parent
    result = build(
        here / "data",
        here.parent / "astro_brain" / "data" / "constellation_figures.json",
    )
    print(f"Generated {len(result)} constellation figures: {sorted(result)}")
