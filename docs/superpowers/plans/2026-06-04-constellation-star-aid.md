# Aide « voir l'étoile dans sa constellation » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher, pendant le wizard de calibration GoTo, un schéma au trait de la constellation de l'étoile cible (orienté comme le ciel), pour aider l'utilisateur à reconnaître quelle étoile choisir/centrer.

**Architecture:** Un asset autonome `constellation_figures.json` embarqué côté backend décrit chaque figure (segments + nœuds RA/Dec/mag). Deux endpoints servent la figure (avec alt/az calculés à l'instant T) et la liste des étoiles d'alignement visibles groupées par constellation. Côté Flutter, un widget `ConstellationChart` (CustomPaint) dessine le schéma, intégré dans un bottom sheet sur l'écran par-étoile et dans un écran-navigateur ouvert au swap. La position de l'observateur suit la chaîne fix Pi → téléphone → sinon pas de wizard (suppression du fallback Paris).

**Tech Stack:** Python 3.13 / FastAPI / pytest (backend, `uv`), Flutter / flutter_bloc / flutter_test (app), CustomPaint pour le dessin, package `geolocator` pour la position téléphone.

**Spec de référence :** [`docs/superpowers/specs/2026-06-04-constellation-star-aid-design.md`](../specs/2026-06-04-constellation-star-aid-design.md)

---

## File Structure

**Backend (créés)**
- `backend/astro_brain/data/constellation_figures.json` — asset des figures (généré, commité).
- `backend/scripts/build_constellation_figures.py` — build one-shot hors runtime.
- `backend/scripts/data/western_lines.fab` — tracés HIP vendorisés (Stellarium western skyculture).
- `backend/astro_brain/services/constellation_figures.py` — chargement de l'asset + `figure_for` + matching cible + projection.

**Backend (modifiés)**
- `backend/astro_brain/services/_alignment_catalog.py` — ajout `constellation_of()` + `visible_stars()`.
- `backend/astro_brain/app.py` — suppression fallback Paris ; `observer()` → `Observer | None` ; store position client ; expose `position_provider` sur `app.state`.
- `backend/astro_brain/routes/alignment.py` — routes `GET /align/constellation/{abbr}`, `GET /align/stars/visible`, `POST /align/location/client` ; garde 409 sur `/align/start` sans position.
- `backend/astro_brain/deps.py` — `get_position_provider`.

**Frontend (créés)**
- `app/lib/features/alignment/widgets/constellation_chart.dart` — CustomPaint partagé.
- `app/lib/features/alignment/screens/star_navigator_screen.dart` — navigateur swap.

**Frontend (modifiés)**
- `app/lib/features/alignment/alignment_models.dart` — DTOs figure + visible-stars.
- `app/lib/features/alignment/alignment_repository.dart` — `fetchConstellation`, `fetchVisibleStars`, `postClientLocation`.
- `app/lib/features/alignment/screens/per_star_screen.dart` — nom constellation + bouton + bottom sheet.

---

## Phase A — Backend : données & catalogue

### Task 1: `constellation_of()` — dériver l'abréviation IAU depuis le champ `bayer`

Les 32 étoiles d'alignement portent leur constellation dans `bayer` (« α CMa » → `CMa`). Pas de nouveau champ.

**Files:**
- Modify: `backend/astro_brain/services/_alignment_catalog.py`
- Test: `backend/tests/test_alignment_catalog.py`

- [ ] **Step 1: Write the failing test**

Ajouter dans `backend/tests/test_alignment_catalog.py` :

```python
from astro_brain.services._alignment_catalog import constellation_of
from astro_brain.models.alignment import Star


def _star(bayer: str) -> Star:
    return Star(id="x", name="X", bayer=bayer, ra_deg=0.0, dec_deg=0.0, mag=1.0)


def test_constellation_of_extracts_iau_abbr():
    assert constellation_of(_star("α CMa")) == "CMa"
    assert constellation_of(_star("β UMa")) == "UMa"


def test_constellation_of_handles_no_greek_prefix():
    # Certains bayer n'ont pas de lettre grecque (ex. designation Flamsteed).
    assert constellation_of(_star("51 Peg")) == "Peg"


def test_constellation_of_returns_none_when_unparseable():
    assert constellation_of(_star("")) is None
    assert constellation_of(_star("Sirius")) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -k constellation_of -v`
Expected: FAIL — `ImportError: cannot import name 'constellation_of'`.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/astro_brain/services/_alignment_catalog.py`, ajouter à `__all__` la chaîne `"constellation_of"`, puis ajouter la fonction (la constellation IAU est le dernier token du `bayer`, toujours 3 lettres) :

```python
# Abréviations IAU officielles : 3 lettres, première en majuscule.
_IAU_ABBRS = frozenset({
    "And", "Ant", "Aps", "Aqr", "Aql", "Ara", "Ari", "Aur", "Boo", "Cae",
    "Cam", "Cnc", "CVn", "CMa", "CMi", "Cap", "Car", "Cas", "Cen", "Cep",
    "Cet", "Cha", "Cir", "Col", "Com", "CrA", "CrB", "Crv", "Crt", "Cru",
    "Cyg", "Del", "Dor", "Dra", "Equ", "Eri", "For", "Gem", "Gru", "Her",
    "Hor", "Hya", "Hyi", "Ind", "Lac", "Leo", "LMi", "Lep", "Lib", "Lup",
    "Lyn", "Lyr", "Men", "Mic", "Mon", "Mus", "Nor", "Oct", "Oph", "Ori",
    "Pav", "Peg", "Per", "Phe", "Pic", "Psc", "PsA", "Pup", "Pyx", "Ret",
    "Sge", "Sgr", "Sco", "Scl", "Sct", "Ser", "Sex", "Tau", "Tel", "Tri",
    "TrA", "Tuc", "UMa", "UMi", "Vel", "Vir", "Vol", "Vul",
})


def constellation_of(star: Star) -> str | None:
    """Dérive l'abréviation IAU (3 lettres) depuis le champ `bayer`.

    Le bayer est de la forme « <lettre/numéro> <Abbr> » (ex. « α CMa »,
    « 51 Peg »). On lit le dernier token. Renvoie None si non reconnu.
    """
    parts = star.bayer.split()
    if not parts:
        return None
    abbr = parts[-1]
    return abbr if abbr in _IAU_ABBRS else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -k constellation_of -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/_alignment_catalog.py backend/tests/test_alignment_catalog.py
git commit -m "feat(backend): constellation_of() dérive l'abréviation IAU du bayer"
```

---

### Task 2: `visible_stars()` — étoiles d'alignement pointables, groupées par constellation

Le navigateur du swap a besoin de **toutes** les étoiles visibles (pas seulement 3 distribuées). On extrait la logique de filtrage visible déjà présente dans `select_candidates`.

**Files:**
- Modify: `backend/astro_brain/services/_alignment_catalog.py`
- Test: `backend/tests/test_alignment_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import UTC, datetime
from astro_brain.services._alignment_catalog import (
    MountLimits, Observer, visible_stars,
)


def test_visible_stars_groups_by_constellation_and_filters_horizon():
    obs = Observer(lat_deg=43.6, lon_deg=1.44)  # Toulouse
    t = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)

    groups = visible_stars(obs, t, limits)

    # Renvoie un dict {abbr: [(star, az, alt), ...]} non vide, toutes alt >= min.
    assert isinstance(groups, dict)
    assert groups, "au moins une constellation visible attendue"
    for entries in groups.values():
        for _star, _az, alt in entries:
            assert alt >= 10.0


def test_visible_stars_excludes_below_horizon():
    # Pôle sud géographique : les étoiles très nord ne se lèvent jamais.
    obs = Observer(lat_deg=-89.0, lon_deg=0.0)
    t = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    groups = visible_stars(obs, t, limits)
    # UMi (étoile polaire nord) ne doit pas apparaître.
    assert "UMi" not in groups
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -k visible_stars -v`
Expected: FAIL — `ImportError: cannot import name 'visible_stars'`.

- [ ] **Step 3: Write minimal implementation**

Ajouter `"visible_stars"` à `__all__`, puis :

```python
def visible_stars(
    observer: Observer,
    t_utc: datetime,
    limits: MountLimits,
    *,
    min_alt: float = 20.0,
) -> dict[str, list[tuple[Star, float, float]]]:
    """Étoiles d'alignement actuellement pointables, groupées par constellation.

    Filtre alt > min_alt et dans `limits` (mêmes critères que
    `select_candidates`). Renvoie {abbr_IAU: [(star, az, alt), ...]} trié par
    magnitude croissante dans chaque groupe.
    """
    groups: dict[str, list[tuple[Star, float, float]]] = {}
    for star in load_catalog():
        az, alt = sky_az_alt_from_ra_dec(star.ra_deg, star.dec_deg, observer, t_utc)
        if alt < min_alt or alt < limits.alt_min or alt > limits.alt_max:
            continue
        if not (limits.az_min <= az <= limits.az_max):
            continue
        abbr = constellation_of(star)
        if abbr is None:
            continue
        groups.setdefault(abbr, []).append((star, az, alt))
    for entries in groups.values():
        entries.sort(key=lambda e: e[0].mag)
    return groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_alignment_catalog.py -k visible_stars -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/_alignment_catalog.py backend/tests/test_alignment_catalog.py
git commit -m "feat(backend): visible_stars() — étoiles d'alignement visibles groupées par constellation"
```

---

### Task 3: Asset des figures + script de build

L'asset est généré une fois à partir de sources publiques, puis commité. Le runtime ne lit que le JSON.

**Files:**
- Create: `backend/scripts/data/western_lines.fab`
- Create: `backend/scripts/build_constellation_figures.py`
- Create: `backend/astro_brain/data/constellation_figures.json`
- Test: `backend/tests/test_build_constellation_figures.py`

- [ ] **Step 1: Vendoriser les sources publiques**

Récupérer (sources stables, publiques) :

```bash
cd backend/scripts/data
# Tracés "western" Stellarium : paires de HIP par constellation (format .fab).
curl -L -o western_lines.fab \
  https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/constellationship.fab
# Base d'étoiles HYG (hip, proper, ra[h], dec[deg], mag, bayer, con).
curl -L -o hyg_v3.csv \
  https://raw.githubusercontent.com/astronexus/HYG-Database/master/hyg/v3/hyg_v3.csv
```

> Si l'environnement est hors-ligne : ces deux fichiers sont la seule dépendance externe et uniquement au moment du build. `hyg_v3.csv` n'est pas commité (volumineux) ; `western_lines.fab` l'est.

- [ ] **Step 2: Write the failing test (parser sur fixture)**

Créer `backend/tests/fixtures/western_lines_sample.fab` :

```
UMa 6 4301 4295 4295 4554 4554 5191 5191 5054 5054 4905 4905 4660
CMa 2 2491 2657 2657 2693
```

Créer `backend/tests/test_build_constellation_figures.py` :

```python
from pathlib import Path

from scripts.build_constellation_figures import parse_fab_lines


def test_parse_fab_lines_returns_segments_as_hip_pairs():
    fab = Path("tests/fixtures/western_lines_sample.fab").read_text()
    figures = parse_fab_lines(fab)
    assert set(figures) == {"UMa", "CMa"}
    # UMa : 6 segments déclarés → 6 paires.
    assert len(figures["UMa"]) == 6
    assert figures["UMa"][0] == (4301, 4295)
    assert figures["CMa"] == [(2491, 2657), (2657, 2693)]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_build_constellation_figures.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.build_constellation_figures'`.

- [ ] **Step 4: Write the build script**

Créer `backend/scripts/__init__.py` (vide) si absent, puis `backend/scripts/build_constellation_figures.py` :

```python
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
    "Gru": "Grue", "Oph": "Ophiuchus", "Sco": "Scorpion", "Aqr": "Verseau",
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
    """HIP → {ra_deg, dec_deg, mag, label}. ra HYG est en heures."""
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
        index = {h: i for i, h in enumerate(hip_order)}
        nodes = [
            {"label": hyg[h]["label"], "ra_deg": round(hyg[h]["ra_deg"], 5),
             "dec_deg": round(hyg[h]["dec_deg"], 5), "mag": hyg[h]["mag"]}
            for h in hip_order
            if h in hyg
        ]
        if len(nodes) < 2:
            continue
        segments = [
            [index[a], index[b]]
            for a, b in seg_hips
            if a in hyg and b in hyg
        ]
        out[abbr] = {"name": _FR_NAMES.get(abbr, abbr),
                     "nodes": nodes, "segments": segments}

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    here = Path(__file__).parent
    build(here / "data",
          here.parent / "astro_brain" / "data" / "constellation_figures.json")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_build_constellation_figures.py -v`
Expected: PASS.

- [ ] **Step 6: Générer + vérifier l'asset**

Run: `cd backend && uv run python scripts/build_constellation_figures.py`
Puis vérifier que chaque constellation des 32 étoiles a une figure :

Run: `cd backend && uv run python -c "import json; d=json.load(open('astro_brain/data/constellation_figures.json')); print(len(d), 'figures:', sorted(d))"`
Expected: ~25-30 figures listées (dont UMa, CMa, Ori, Lyr…).

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/__init__.py backend/scripts/build_constellation_figures.py \
        backend/scripts/data/western_lines.fab \
        backend/astro_brain/data/constellation_figures.json \
        backend/tests/test_build_constellation_figures.py \
        backend/tests/fixtures/western_lines_sample.fab
git commit -m "feat(backend): asset constellation_figures.json + script de build"
```

---

### Task 4: Loader runtime `constellation_figures.py` (figure + matching cible + projection)

**Files:**
- Create: `backend/astro_brain/services/constellation_figures.py`
- Test: `backend/tests/test_constellation_figures.py`

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_constellation_figures.py` :

```python
from datetime import UTC, datetime

from astro_brain.services._ephemeris import Observer
from astro_brain.services.constellation_figures import (
    figure_for, load_figures, render_figure,
)


def test_load_figures_integrity_segments_reference_existing_nodes():
    figures = load_figures()
    assert figures, "asset non vide attendu"
    for abbr, fig in figures.items():
        n = len(fig["nodes"])
        for a, b in fig["segments"]:
            assert 0 <= a < n and 0 <= b < n, f"{abbr}: segment hors bornes"


def test_figure_for_known_constellation():
    fig = figure_for("UMa")
    assert fig is not None
    assert fig["name"] == "Grande Ourse"


def test_figure_for_unknown_returns_none():
    assert figure_for("ZZZ") is None


def test_render_figure_marks_target_by_proximity_and_computes_altaz():
    obs = Observer(lat_deg=43.6, lon_deg=1.44)
    t = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    fig = figure_for("UMa")
    # cible : coordonnées de Dubhe (≈ ra 165.93, dec 61.75).
    out = render_figure(fig, target_ra=165.932, target_dec=61.751,
                        observer=obs, t_utc=t)
    assert out["oriented"] is True
    targets = [n for n in out["nodes"] if n["is_target"]]
    assert len(targets) == 1
    assert "Dubhe" in targets[0]["label"]
    for node in out["nodes"]:
        assert "az" in node and "alt" in node


def test_render_figure_without_observer_is_not_oriented():
    fig = figure_for("UMa")
    out = render_figure(fig, target_ra=165.932, target_dec=61.751,
                        observer=None, t_utc=None)
    assert out["oriented"] is False
    assert all(n["az"] is None and n["alt"] is None for n in out["nodes"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_constellation_figures.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'astro_brain.services.constellation_figures'`.

- [ ] **Step 3: Write minimal implementation**

Créer `backend/astro_brain/services/constellation_figures.py` :

```python
"""Chargement de l'asset des figures + rendu (matching cible + alt/az).

Le matching de l'étoile cible se fait par proximité angulaire (robuste aux
divergences de désignation entre l'étoile d'alignement et le nœud de figure).
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from functools import lru_cache
from importlib import resources

from astro_brain.services._ephemeris import Observer, sky_az_alt_from_ra_dec

_TARGET_MATCH_DEG = 1.0  # tolérance de matching cible


@lru_cache(maxsize=1)
def load_figures() -> dict[str, dict]:
    raw = resources.files("astro_brain.data").joinpath(
        "constellation_figures.json"
    ).read_text()
    return json.loads(raw)


def figure_for(abbr: str) -> dict | None:
    return load_figures().get(abbr)


def _angular_sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cos_sep = (math.sin(d1) * math.sin(d2)
               + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))


def render_figure(
    figure: dict,
    *,
    target_ra: float,
    target_dec: float,
    observer: Observer | None,
    t_utc: datetime | None,
) -> dict:
    """Renvoie {name, oriented, nodes:[{label,mag,ra_deg,dec_deg,az,alt,is_target}], segments}.

    - `is_target` posé sur le nœud le plus proche de (target_ra, target_dec)
      si < _TARGET_MATCH_DEG, sinon aucun.
    - alt/az calculés si observer/t_utc fournis, sinon None (oriented=False).
    """
    oriented = observer is not None and t_utc is not None
    best_i, best_sep = -1, _TARGET_MATCH_DEG
    for i, node in enumerate(figure["nodes"]):
        sep = _angular_sep_deg(target_ra, target_dec,
                               node["ra_deg"], node["dec_deg"])
        if sep < best_sep:
            best_i, best_sep = i, sep

    nodes = []
    for i, node in enumerate(figure["nodes"]):
        az = alt = None
        if oriented:
            az, alt = sky_az_alt_from_ra_dec(
                node["ra_deg"], node["dec_deg"], observer, t_utc)
        nodes.append({
            "label": node["label"], "mag": node["mag"],
            "ra_deg": node["ra_deg"], "dec_deg": node["dec_deg"],
            "az": az, "alt": alt, "is_target": i == best_i,
        })
    return {"name": figure["name"], "oriented": oriented,
            "nodes": nodes, "segments": figure["segments"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_constellation_figures.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/services/constellation_figures.py backend/tests/test_constellation_figures.py
git commit -m "feat(backend): loader figures + matching cible par proximité + alt/az"
```

---

## Phase B — Backend : position de l'observateur

### Task 5: Chaîne de position (fix Pi → téléphone → None), suppression du fallback Paris

**Files:**
- Modify: `backend/astro_brain/app.py` (classe `_AlignmentSensorsBridge`, lignes ~69-100, et `_candidates_provider` ~213)
- Test: `backend/tests/test_alignment_sensors_bridge.py`

- [ ] **Step 1: Write the failing test**

Ajouter dans `backend/tests/test_alignment_sensors_bridge.py` (le fichier construit déjà un `_AlignmentSensorsBridge` sur un `StateBus` — réutiliser ce pattern) :

```python
def test_observer_returns_none_without_fix_or_client(bus):
    bridge = _AlignmentSensorsBridge(bus)  # bus sans subsystem gps
    assert bridge.observer() is None


def test_observer_uses_client_location_when_no_fix(bus):
    bridge = _AlignmentSensorsBridge(bus)
    bridge.set_client_location(43.6, 1.44)
    obs = bridge.observer()
    assert obs is not None
    assert (obs.lat_deg, obs.lon_deg) == (43.6, 1.44)


def test_pi_fix_takes_precedence_over_client(bus, gps_fix_state):
    # gps_fix_state : helper de la suite qui publie un subsystem gps fix_3d.
    bridge = _AlignmentSensorsBridge(bus)
    bridge.set_client_location(0.0, 0.0)
    gps_fix_state(bridge, lat=48.0, lon=2.0)
    obs = bridge.observer()
    assert (obs.lat_deg, obs.lon_deg) == (48.0, 2.0)
```

> Adapter les fixtures (`bus`, `gps_fix_state`) au style déjà présent dans ce fichier de test ; s'il n'y a pas de helper de publication GPS, publier directement via `bus.publish("gps", SubsystemState(state="fix_3d", details={"lat":48.0,"lon":2.0}, since=...))`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_alignment_sensors_bridge.py -k "observer_returns_none or client" -v`
Expected: FAIL — `observer()` renvoie un `Observer` (Paris) au lieu de `None` / `set_client_location` n'existe pas.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/astro_brain/app.py`, modifier `_AlignmentSensorsBridge` :

```python
class _AlignmentSensorsBridge:
    """Adapts the StateBus + observer position to the duck-typed `sensors`
    interface AlignmentServiceImpl expects (`gps_fix`, `sky_az_alt_for`).

    Chaîne de position : fix GPS Pi → position client (téléphone) → None.
    Plus de fallback codé en dur.
    """

    def __init__(self, bus: StateBus) -> None:
        self._bus = bus
        self._client: tuple[float, float] | None = None

    def set_client_location(self, lat: float, lon: float) -> None:
        self._client = (lat, lon)

    def clear_client_location(self) -> None:
        self._client = None

    def gps_fix(self) -> tuple[float, float] | None:
        gps = self._bus.get_full_state().subsystems.get("gps")
        if gps is None or gps.state != "fix_3d":
            return None
        details = gps.details or {}
        lat = details.get("lat")
        lon = details.get("lon")
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon))

    def position(self) -> tuple[float, float] | None:
        return self.gps_fix() or self._client

    def observer(self) -> Observer | None:
        pos = self.position()
        if pos is None:
            return None
        return Observer(lat_deg=pos[0], lon_deg=pos[1])

    def sky_az_alt_for(self, star: Any) -> tuple[float, float] | None:
        obs = self.observer()
        if obs is None:
            return None
        return sky_az_alt_from_ra_dec(
            star.ra_deg, star.dec_deg, obs, datetime.now(UTC)
        )
```

Puis adapter `_candidates_provider` (renvoie `[]` si pas de position — `/align/start` traduira ça en 409, Task 7) :

```python
        def _candidates_provider() -> list[Any]:
            obs = sensors_bridge.observer()
            if obs is None:
                return []
            limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
            return select_candidates(obs, datetime.now(UTC), limits, exclude_ids=set())
```

Enfin, exposer le provider sur `app.state` (après la création de `sensors_bridge`) :

```python
        _app.state.position_provider = sensors_bridge
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_alignment_sensors_bridge.py -v`
Expected: PASS. Vérifier aussi la non-régression : `cd backend && uv run pytest tests/test_app.py -v`.

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/app.py backend/tests/test_alignment_sensors_bridge.py
git commit -m "feat(backend): chaîne de position fix Pi→téléphone→None, suppression fallback Paris"
```

---

## Phase C — Backend : routes

### Task 6: `deps.get_position_provider`

**Files:**
- Modify: `backend/astro_brain/deps.py`
- Test: couvert par les routes (Task 7/8) ; pas de test unitaire dédié.

- [ ] **Step 1: Write minimal implementation**

Ajouter dans `backend/astro_brain/deps.py` (suivre le style des autres résolveurs `get_*`) :

```python
def get_position_provider(request: Request):
    """Fournit le provider de position (fix Pi → téléphone → None)."""
    return request.app.state.position_provider
```

- [ ] **Step 2: Vérifier l'import**

Run: `cd backend && uv run python -c "from astro_brain import deps; print(deps.get_position_provider)"`
Expected: affiche `<function get_position_provider ...>`.

- [ ] **Step 3: Commit**

```bash
git add backend/astro_brain/deps.py
git commit -m "feat(backend): deps.get_position_provider"
```

---

### Task 7: Route `POST /align/location/client` + garde 409 sur `/align/start`

**Files:**
- Modify: `backend/astro_brain/routes/alignment.py`
- Test: `backend/tests/test_alignment_routes.py`

- [ ] **Step 1: Write the failing test**

Ajouter dans `backend/tests/test_alignment_routes.py` (réutiliser le `TestClient`/fixtures déjà en place) :

```python
def test_post_client_location_then_start_succeeds(client, no_gps_fix):
    # no_gps_fix : fixture qui garantit l'absence de fix Pi.
    r = client.post("/align/location/client", json={"lat": 43.6, "lon": 1.44})
    assert r.status_code == 200
    r2 = client.post("/align/start", json={})
    assert r2.status_code == 200


def test_start_without_position_returns_409(client, no_gps_fix):
    client.post("/align/location/client", json={"lat": None, "lon": None}) \
        if False else None  # pas de position posée
    r = client.post("/align/start", json={})
    assert r.status_code == 409
```

> Adapter `client`/`no_gps_fix` aux fixtures du fichier. Pour garantir l'absence de fix, ne pas publier de subsystem `gps` `fix_3d`. Le `position_provider` doit être celui câblé sur `app.state` (le bridge réel), pas un fake qui renverrait Paris.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -k "client_location or without_position" -v`
Expected: FAIL — route `/align/location/client` absente (404) ; `/align/start` renvoie 200 au lieu de 409.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/astro_brain/routes/alignment.py`, ajouter le body model et la route, et garder `/align/start` :

```python
class _ClientLocationBody(BaseModel):
    lat: float
    lon: float


@router.post("/location/client")
async def set_client_location(
    body: _ClientLocationBody,
    position=Depends(deps.get_position_provider),
) -> dict:
    position.set_client_location(body.lat, body.lon)
    return {"ok": True}
```

Modifier la route `start` existante pour refuser sans position :

```python
@router.post("/start")
async def start(
    service: AlignmentService = Depends(deps.get_alignment),
    bus: StateBus = Depends(deps.get_bus),
    position=Depends(deps.get_position_provider),
):
    if position.position() is None:
        raise HTTPException(status_code=409, detail="position requise")
    try:
        sess = await service.start()
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    _publish_session(bus, service)
    return sess
```

> Garder la signature de `start` cohérente avec l'existante (mêmes `Depends` déjà présents + le nouveau `position`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -v`
Expected: PASS (existants + nouveaux).

- [ ] **Step 5: Commit**

```bash
git add backend/astro_brain/routes/alignment.py backend/tests/test_alignment_routes.py
git commit -m "feat(backend): POST /align/location/client + 409 /align/start sans position"
```

---

### Task 8: Routes `GET /align/constellation/{abbr}` et `GET /align/stars/visible`

**Files:**
- Modify: `backend/astro_brain/routes/alignment.py`
- Test: `backend/tests/test_alignment_routes.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_constellation_known_marks_target(client, client_located):
    # client_located : pose une position via /align/location/client.
    r = client.get("/align/constellation/UMa",
                   params={"target_ra": 165.932, "target_dec": 61.751})
    assert r.status_code == 200
    body = r.json()
    assert body["abbr"] == "UMa"
    assert body["name"] == "Grande Ourse"
    assert sum(1 for n in body["nodes"] if n["is_target"]) == 1
    assert body["oriented"] is True


def test_get_constellation_unknown_404(client, client_located):
    r = client.get("/align/constellation/ZZZ",
                   params={"target_ra": 0.0, "target_dec": 0.0})
    assert r.status_code == 404


def test_get_visible_stars_grouped(client, client_located):
    r = client.get("/align/stars/visible")
    assert r.status_code == 200
    body = r.json()
    # {abbr: [star,...]} ; chaque star a id/name/bayer/mag/az/alt.
    assert isinstance(body["constellations"], dict)
    for stars in body["constellations"].values():
        for s in stars:
            assert {"id", "name", "bayer", "mag", "az", "alt"} <= set(s)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -k "constellation or visible_stars" -v`
Expected: FAIL — routes absentes (404 sur des chemins non déclarés).

- [ ] **Step 3: Write minimal implementation**

Dans `backend/astro_brain/routes/alignment.py`, importer les helpers et ajouter les routes :

```python
from datetime import UTC, datetime

from astro_brain.services._alignment_catalog import (
    MountLimits, visible_stars,
)
from astro_brain.services.constellation_figures import figure_for, render_figure


@router.get("/constellation/{abbr}")
async def get_constellation(
    abbr: str,
    target_ra: float,
    target_dec: float,
    position=Depends(deps.get_position_provider),
) -> dict:
    figure = figure_for(abbr)
    if figure is None:
        raise HTTPException(status_code=404, detail=f"constellation inconnue: {abbr}")
    obs = position.observer()
    t = datetime.now(UTC) if obs is not None else None
    rendered = render_figure(
        figure, target_ra=target_ra, target_dec=target_dec,
        observer=obs, t_utc=t,
    )
    return {"abbr": abbr, **rendered}


@router.get("/stars/visible")
async def get_visible_stars(
    position=Depends(deps.get_position_provider),
) -> dict:
    obs = position.observer()
    if obs is None:
        raise HTTPException(status_code=409, detail="position requise")
    limits = MountLimits(alt_min=10.0, alt_max=85.0, az_min=0.0, az_max=360.0)
    groups = visible_stars(obs, datetime.now(UTC), limits)
    return {
        "constellations": {
            abbr: [
                {"id": s.id, "name": s.name, "bayer": s.bayer,
                 "ra_deg": s.ra_deg, "dec_deg": s.dec_deg, "mag": s.mag,
                 "az": round(az, 2), "alt": round(alt, 2)}
                for s, az, alt in entries
            ]
            for abbr, entries in groups.items()
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_alignment_routes.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite + commit**

Run: `cd backend && uv run pytest -q`
Expected: tout passe.

```bash
git add backend/astro_brain/routes/alignment.py backend/tests/test_alignment_routes.py
git commit -m "feat(backend): GET /align/constellation/{abbr} + GET /align/stars/visible"
```

---

## Phase D — Frontend

### Task 9: DTOs figure + visible-stars

**Files:**
- Modify: `app/lib/features/alignment/alignment_models.dart`
- Test: `app/test/features/alignment/alignment_models_test.dart` (créer si absent)

- [ ] **Step 1: Write the failing test**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:astro_brain/features/alignment/alignment_models.dart';

void main() {
  test('ConstellationFigureDto.fromJson parses nodes and segments', () {
    final dto = ConstellationFigureDto.fromJson({
      'abbr': 'UMa',
      'name': 'Grande Ourse',
      'oriented': true,
      'nodes': [
        {'label': 'Dubhe', 'mag': 1.79, 'ra_deg': 165.9, 'dec_deg': 61.7,
         'az': 312.4, 'alt': 47.1, 'is_target': true},
        {'label': 'Merak', 'mag': 2.37, 'ra_deg': 165.4, 'dec_deg': 56.3,
         'az': 310.0, 'alt': 42.0, 'is_target': false},
      ],
      'segments': [[0, 1]],
    });
    expect(dto.name, 'Grande Ourse');
    expect(dto.oriented, isTrue);
    expect(dto.nodes.length, 2);
    expect(dto.nodes.first.isTarget, isTrue);
    expect(dto.segments.first, [0, 1]);
  });

  test('ConstellationNodeDto handles null az/alt (not oriented)', () {
    final node = ConstellationNodeDto.fromJson({
      'label': 'X', 'mag': 2.0, 'ra_deg': 10.0, 'dec_deg': 20.0,
      'az': null, 'alt': null, 'is_target': false,
    });
    expect(node.az, isNull);
    expect(node.alt, isNull);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/alignment_models_test.dart`
Expected: FAIL — `ConstellationFigureDto` indéfini.

- [ ] **Step 3: Write minimal implementation**

Ajouter à `app/lib/features/alignment/alignment_models.dart` :

```dart
class ConstellationNodeDto {
  const ConstellationNodeDto({
    required this.label,
    required this.mag,
    required this.raDeg,
    required this.decDeg,
    required this.az,
    required this.alt,
    required this.isTarget,
  });

  final String label;
  final double mag;
  final double raDeg;
  final double decDeg;
  final double? az;
  final double? alt;
  final bool isTarget;

  factory ConstellationNodeDto.fromJson(Map<String, dynamic> j) =>
      ConstellationNodeDto(
        label: j['label'] as String,
        mag: (j['mag'] as num).toDouble(),
        raDeg: (j['ra_deg'] as num).toDouble(),
        decDeg: (j['dec_deg'] as num).toDouble(),
        az: (j['az'] as num?)?.toDouble(),
        alt: (j['alt'] as num?)?.toDouble(),
        isTarget: j['is_target'] as bool,
      );
}

class ConstellationFigureDto {
  const ConstellationFigureDto({
    required this.abbr,
    required this.name,
    required this.oriented,
    required this.nodes,
    required this.segments,
  });

  final String abbr;
  final String name;
  final bool oriented;
  final List<ConstellationNodeDto> nodes;
  final List<List<int>> segments;

  factory ConstellationFigureDto.fromJson(Map<String, dynamic> j) =>
      ConstellationFigureDto(
        abbr: j['abbr'] as String,
        name: j['name'] as String,
        oriented: j['oriented'] as bool,
        nodes: (j['nodes'] as List)
            .map((e) => ConstellationNodeDto.fromJson(e as Map<String, dynamic>))
            .toList(),
        segments: (j['segments'] as List)
            .map((e) => (e as List).map((i) => i as int).toList())
            .toList(),
      );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/features/alignment/alignment_models_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/alignment_models.dart app/test/features/alignment/alignment_models_test.dart
git commit -m "feat(app): DTOs ConstellationFigure/Node"
```

---

### Task 10: Méthodes repository `fetchConstellation` / `fetchVisibleStars` / `postClientLocation`

**Files:**
- Modify: `app/lib/features/alignment/alignment_repository.dart`
- Test: `app/test/features/alignment/alignment_repository_test.dart` (créer si absent ; suivre le style des tests repo existants qui mockent `api`)

- [ ] **Step 1: Write the failing test**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:astro_brain/features/alignment/alignment_repository.dart';
// import du type `api` mocké comme dans les autres tests repo du projet.

class _FakeApi extends Mock implements ApiClient {} // adapter au type réel

void main() {
  test('fetchConstellation hits the right path with query', () async {
    final api = _FakeApi();
    when(() => api.getJson('/align/constellation/UMa?target_ra=165.9&target_dec=61.7'))
        .thenAnswer((_) async => {
              'abbr': 'UMa', 'name': 'Grande Ourse', 'oriented': true,
              'nodes': <dynamic>[], 'segments': <dynamic>[],
            });
    final repo = AlignmentRepository(api: api);
    final fig = await repo.fetchConstellation('UMa', raDeg: 165.9, decDeg: 61.7);
    expect(fig.name, 'Grande Ourse');
  });
}
```

> Adapter `ApiClient`/`getJson` au type réel injecté dans `AlignmentRepository` (cf. en-tête du fichier `alignment_repository.dart`). Le projet a déjà rencontré le piège de la query string encodée (`f179db4`) : passer la query proprement (cf. Step 3).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/alignment_repository_test.dart`
Expected: FAIL — méthodes absentes.

- [ ] **Step 3: Write minimal implementation**

Ajouter à `app/lib/features/alignment/alignment_repository.dart` (importer les DTOs) :

```dart
  Future<ConstellationFigureDto> fetchConstellation(
    String abbr, {
    required double raDeg,
    required double decDeg,
  }) async {
    final j = await api.getJson(
      '/align/constellation/$abbr?target_ra=$raDeg&target_dec=$decDeg',
    );
    return ConstellationFigureDto.fromJson(j as Map<String, dynamic>);
  }

  Future<Map<String, List<StarDto>>> fetchVisibleStars() async {
    final j = await api.getJson('/align/stars/visible');
    final raw = (j as Map<String, dynamic>)['constellations']
        as Map<String, dynamic>;
    return raw.map((abbr, list) => MapEntry(
          abbr,
          (list as List)
              .map((e) => StarDto.fromJson(e as Map<String, dynamic>))
              .toList(),
        ));
  }

  Future<void> postClientLocation(double lat, double lon) =>
      api.postJson('/align/location/client', {'lat': lat, 'lon': lon});
```

> `StarDto.fromJson` accepte déjà `id/name/bayer/ra_deg/dec_deg/mag` ; les champs `az/alt` supplémentaires sont ignorés sans erreur.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/features/alignment/alignment_repository_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/alignment_repository.dart app/test/features/alignment/alignment_repository_test.dart
git commit -m "feat(app): repo fetchConstellation/fetchVisibleStars/postClientLocation"
```

---

### Task 11: Widget `ConstellationChart` (CustomPaint)

**Files:**
- Create: `app/lib/features/alignment/widgets/constellation_chart.dart`
- Test: `app/test/features/alignment/constellation_chart_test.dart`

- [ ] **Step 1: Write the failing test**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:astro_brain/features/alignment/alignment_models.dart';
import 'package:astro_brain/features/alignment/widgets/constellation_chart.dart';

ConstellationFigureDto _fig({required bool oriented}) => ConstellationFigureDto(
      abbr: 'UMa', name: 'Grande Ourse', oriented: oriented,
      nodes: [
        ConstellationNodeDto(label: 'Dubhe', mag: 1.79, raDeg: 165.9,
            decDeg: 61.7, az: oriented ? 312.0 : null,
            alt: oriented ? 47.0 : null, isTarget: true),
        ConstellationNodeDto(label: 'Merak', mag: 2.37, raDeg: 165.4,
            decDeg: 56.3, az: oriented ? 310.0 : null,
            alt: oriented ? 42.0 : null, isTarget: false),
      ],
      segments: const [[0, 1]],
    );

void main() {
  testWidgets('renders oriented figure with target label', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ConstellationChart(figure: _fig(oriented: true))),
    ));
    expect(find.text('Dubhe'), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
  });

  testWidgets('falls back to atlas projection when not oriented',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: ConstellationChart(figure: _fig(oriented: false))),
    ));
    // Pas de badge "orienté ciel" quand non orienté.
    expect(find.textContaining('orienté'), findsNothing);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/constellation_chart_test.dart`
Expected: FAIL — `ConstellationChart` indéfini.

- [ ] **Step 3: Write minimal implementation**

Créer `app/lib/features/alignment/widgets/constellation_chart.dart`. Projection : si `oriented`, axes (x = azimut local autour de la cible, y = altitude, **haut = zénith**) ; sinon projection RA/Dec. Couleurs depuis le thème (jour/nuit) via `Theme.of(context)`.

```dart
import 'package:flutter/material.dart';

import '../alignment_models.dart';

/// Schéma au trait d'une constellation, étoile cible mise en évidence.
/// Orienté comme le ciel (haut = zénith) si la figure est `oriented`,
/// sinon projection atlas (RA/Dec).
class ConstellationChart extends StatelessWidget {
  const ConstellationChart({super.key, required this.figure});

  final ConstellationFigureDto figure;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(figure.name, style: Theme.of(context).textTheme.labelLarge),
            if (figure.oriented)
              Text('N↑ orienté ciel',
                  style: Theme.of(context).textTheme.labelSmall
                      ?.copyWith(color: scheme.tertiary)),
          ],
        ),
        const SizedBox(height: 8),
        AspectRatio(
          aspectRatio: 16 / 10,
          child: CustomPaint(
            painter: _ChartPainter(figure: figure, color: scheme.onSurface,
                lineColor: scheme.outline, targetColor: scheme.primary),
            child: const SizedBox.expand(),
          ),
        ),
      ],
    );
  }
}

class _ChartPainter extends CustomPainter {
  _ChartPainter({
    required this.figure,
    required this.color,
    required this.lineColor,
    required this.targetColor,
  });

  final ConstellationFigureDto figure;
  final Color color;
  final Color lineColor;
  final Color targetColor;

  /// (u, v) brut par nœud selon le mode (orienté ou atlas).
  List<Offset> _rawPoints() {
    return figure.nodes.map((n) {
      if (figure.oriented && n.az != null && n.alt != null) {
        // u = azimut (déroulé), v = altitude ; haut = altitude max (zénith).
        return Offset(n.az!, n.alt!);
      }
      // Atlas : RA croissant vers la gauche (convention ciel), Dec vers le haut.
      return Offset(-n.raDeg, n.decDeg);
    }).toList();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final pts = _rawPoints();
    if (pts.isEmpty) return;

    // Normalisation dans le canvas avec marge.
    final xs = pts.map((p) => p.dx);
    final ys = pts.map((p) => p.dy);
    final minX = xs.reduce((a, b) => a < b ? a : b);
    final maxX = xs.reduce((a, b) => a > b ? a : b);
    final minY = ys.reduce((a, b) => a < b ? a : b);
    final maxY = ys.reduce((a, b) => a > b ? a : b);
    const m = 24.0;
    double sx(double x) => (maxX == minX)
        ? size.width / 2
        : m + (x - minX) / (maxX - minX) * (size.width - 2 * m);
    // v croît vers le haut → invertir l'axe écran (y vers le bas).
    double sy(double y) => (maxY == minY)
        ? size.height / 2
        : size.height - (m + (y - minY) / (maxY - minY) * (size.height - 2 * m));

    final screen =
        pts.map((p) => Offset(sx(p.dx), sy(p.dy))).toList(growable: false);

    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    for (final seg in figure.segments) {
      canvas.drawLine(screen[seg[0]], screen[seg[1]], linePaint);
    }

    for (var i = 0; i < figure.nodes.length; i++) {
      final n = figure.nodes[i];
      final r = (4.0 - n.mag * 0.6).clamp(1.5, 4.0);
      if (n.isTarget) {
        canvas.drawCircle(screen[i], 11,
            Paint()..color = targetColor.withValues(alpha: 0.20));
        canvas.drawCircle(screen[i], 4.5, Paint()..color = targetColor);
        final tp = TextPainter(
          text: TextSpan(
              text: n.label,
              style: TextStyle(color: targetColor, fontSize: 12)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, screen[i] + const Offset(8, -16));
      } else {
        canvas.drawCircle(screen[i], r, Paint()..color = color);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ChartPainter old) =>
      old.figure != figure;
}
```

> `withValues(alpha:)` est l'API Flutter récente (remplace `withOpacity`). Si l'analyse réclame une autre forme, suivre ce que `flutter analyze` indique.

- [ ] **Step 4: Run test + analyze to verify they pass**

Run: `cd app && flutter test test/features/alignment/constellation_chart_test.dart && flutter analyze`
Expected: tests PASS, analyze sans erreur.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/widgets/constellation_chart.dart app/test/features/alignment/constellation_chart_test.dart
git commit -m "feat(app): widget ConstellationChart (CustomPaint, orienté/atlas)"
```

---

### Task 12: Intégration écran par-étoile (nom constellation + bouton + bottom sheet)

**Files:**
- Modify: `app/lib/features/alignment/screens/per_star_screen.dart`
- Test: `app/test/features/alignment/per_star_screen_test.dart` (créer si absent)

- [ ] **Step 1: Write the failing test**

```dart
testWidgets('shows "voir dans la constellation" button and opens sheet',
    (tester) async {
  // Construire PerStarScreen avec une candidate cible (bayer "α UMa")
  // et un repository fake renvoyant une figure UMa.
  // ... montage selon le constructeur réel de PerStarScreen ...
  expect(find.textContaining('constellation'), findsOneWidget);
  await tester.tap(find.textContaining('constellation'));
  await tester.pumpAndSettle();
  expect(find.byType(ConstellationChart), findsOneWidget);
});
```

> Adapter le montage au constructeur réel de `PerStarScreen` (cf. `screens/per_star_screen.dart:16`). Injecter un fake `AlignmentRepository.fetchConstellation` renvoyant une figure UMa de test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/per_star_screen_test.dart`
Expected: FAIL — bouton absent.

- [ ] **Step 3: Write minimal implementation**

Dans `per_star_screen.dart` : (a) afficher le nom de constellation dans le hero (dérivé via une petite table abréviation→français déjà présente côté catalogue, ou via `figure.name` après fetch) ; (b) ajouter un `OutlinedButton.icon` « Voir dans la constellation » qui appelle `repository.fetchConstellation(abbr, raDeg: target.raDeg, decDeg: target.decDeg)` puis `showModalBottomSheet` affichant `ConstellationChart(figure: fig)`.

```dart
OutlinedButton.icon(
  icon: const Icon(Icons.auto_awesome_outlined),
  label: const Text('Voir dans la constellation'),
  onPressed: () async {
    final abbr = target.bayer.split(' ').last; // "α UMa" → "UMa"
    final fig = await repository.fetchConstellation(
      abbr, raDeg: target.raDeg, decDeg: target.decDeg);
    if (!context.mounted) return;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(16),
        child: ConstellationChart(figure: fig),
      ),
    );
  },
)
```

> Le bouton n'est affiché que si `abbr` est non vide. En cas d'erreur 404 (constellation hors asset), capter l'exception et masquer/désactiver le bouton plutôt que de planter (le hero garde juste le nom de l'étoile).

- [ ] **Step 4: Run test + analyze to verify they pass**

Run: `cd app && flutter test test/features/alignment/per_star_screen_test.dart && flutter analyze`
Expected: PASS / pas d'erreur.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/screens/per_star_screen.dart app/test/features/alignment/per_star_screen_test.dart
git commit -m "feat(app): per-star — bouton + bottom sheet schéma constellation"
```

---

### Task 13: Écran navigateur (swap) + câblage

**Files:**
- Create: `app/lib/features/alignment/screens/star_navigator_screen.dart`
- Modify: `app/lib/features/alignment/alignment_wizard_screen.dart` (ou le point qui déclenche le swap) pour ouvrir le navigateur
- Test: `app/test/features/alignment/star_navigator_screen_test.dart`

- [ ] **Step 1: Write the failing test**

```dart
testWidgets('navigator lists visible constellations and selects a star',
    (tester) async {
  // Fake repo : fetchVisibleStars → {'UMa': [Dubhe, Merak]}.
  // Monter StarNavigatorScreen avec un callback onSelected.
  // Choisir "UMa" dans le filtre, taper "Dubhe", vérifier le chart,
  // valider → onSelected(StarDto Dubhe) appelé.
  expect(find.text('Grande Ourse'), findsWidgets);
});
```

> Adapter au style bloc/widget du projet ; le filtre par constellation se peuple **depuis `fetchVisibleStars()`** (et donc ne liste que des constellations réellement visibles — pas le filtre client-side du catalogue).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/star_navigator_screen_test.dart`
Expected: FAIL — écran absent.

- [ ] **Step 3: Write minimal implementation**

Créer `star_navigator_screen.dart` : `DropdownButton` des constellations (clés de `fetchVisibleStars`, libellé = nom français), liste d'étoiles du groupe sélectionné, tap d'une étoile → `fetchConstellation` → `ConstellationChart` (inline ou sheet), bouton « Choisir cette étoile » → `onSelected(star)`. Le déclencheur de swap (existant dans le wizard) ouvre cet écran ; `onSelected` appelle `repository.swap(idx, star)` (route inchangée, accepte déjà un `star`).

```dart
class StarNavigatorScreen extends StatefulWidget {
  const StarNavigatorScreen({
    super.key,
    required this.repository,
    required this.onSelected,
  });

  final AlignmentRepository repository;
  final ValueChanged<StarDto> onSelected;

  @override
  State<StarNavigatorScreen> createState() => _StarNavigatorScreenState();
}
```

> Implémenter l'état : charger `fetchVisibleStars()` en `initState`, gérer chargement/erreur, et le rendu décrit ci-dessus. Réutiliser les libellés français via la même table que le catalogue (ou via `fetchConstellation(...).name` au tap).

- [ ] **Step 4: Run test + analyze to verify they pass**

Run: `cd app && flutter test test/features/alignment/star_navigator_screen_test.dart && flutter analyze`
Expected: PASS / pas d'erreur.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/alignment/screens/star_navigator_screen.dart \
        app/lib/features/alignment/alignment_wizard_screen.dart \
        app/test/features/alignment/star_navigator_screen_test.dart
git commit -m "feat(app): écran navigateur étoiles par constellation (swap)"
```

---

### Task 14: Position téléphone (`geolocator`) + état prérequis Hub

**Files:**
- Modify: `app/pubspec.yaml` (dépendance `geolocator`)
- Modify: `app/lib/features/alignment/alignment_wizard_screen.dart` (push position au démarrage)
- Modify: Hub (carte alignement) — fichier du Hub central (`app/lib/features/hub/...`, cf. spec hub-central)
- Test: `app/test/...` selon le bloc concerné

- [ ] **Step 1: Ajouter la dépendance**

Run: `cd app && flutter pub add geolocator`
Vérifier la permission Android dans `app/android/app/src/main/AndroidManifest.xml` :
`<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>` (ajouter si absent).

- [ ] **Step 2: Write the failing test (logique de fallback, sans hardware)**

Tester la *logique* « si pas de position backend, tenter la position téléphone et la POSTer », via un service injectable mocké (ne pas appeler `geolocator` réel en test) :

```dart
test('pushes phone location when backend has no position', () async {
  // locationProvider mock → (43.6, 1.44) ; repo mock capte postClientLocation.
  // Appeler la routine d'amorçage et vérifier repo.postClientLocation(43.6,1.44).
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd app && flutter test test/features/alignment/`
Expected: FAIL — routine/abstraction absente.

- [ ] **Step 4: Write minimal implementation**

Introduire une fine abstraction `PhoneLocation` (interface `Future<({double lat, double lon})?> current()`), implémentée par `geolocator` en prod et mockée en test. Au démarrage du wizard, si le backend n'a pas de position (échec 409 sur `/align/start` ou état hub « position requise »), demander la permission + `current()` puis `repository.postClientLocation(lat, lon)` et réessayer. Le Hub affiche la carte alignement en état « Position GPS requise » tant qu'aucune position n'est disponible (même pattern que le bandeau non-aligné du catalogue, cf. `c570cda`).

- [ ] **Step 5: Run test + analyze**

Run: `cd app && flutter test && flutter analyze`
Expected: PASS / pas d'erreur.

- [ ] **Step 6: Commit**

```bash
git add app/pubspec.yaml app/pubspec.lock app/android/app/src/main/AndroidManifest.xml \
        app/lib/features/alignment/ app/lib/features/hub/ app/test/features/alignment/
git commit -m "feat(app): repli position téléphone (geolocator) + état prérequis Hub"
```

---

## Phase E — Finalisation

### Task 15: Suites complètes + docs

- [ ] **Step 1: Backend complet**

Run: `cd backend && uv run pytest -q`
Expected: tout passe.

- [ ] **Step 2: App complète**

Run: `cd app && flutter analyze && flutter test`
Expected: pas d'erreur, tous tests verts.

- [ ] **Step 3: Mettre à jour la doc projet**

- `docs/project/roadmap.md` : noter l'aide « identification étoile/constellation » livrée sous Macro 3 #2.
- `docs/project/journal.md` : entrée de session (décisions clés : asset autonome, chaîne de position fix→téléphone→none, suppression fallback Paris).
- `docs/project/backlog.md` : ajouter l'item **bug menu déroulant catalogue** (client-side, liste des constellations non filtrée par visibilité) — hors scope de cette livraison.

- [ ] **Step 4: Commit docs**

```bash
git add docs/project/roadmap.md docs/project/journal.md docs/project/backlog.md
git commit -m "docs: aide identification étoile/constellation (roadmap + journal + backlog)"
```

- [ ] **Step 5: Validation manuelle (post-dongle CP2102)**

Selon la spec § Intégration manuelle : (1) fix Pi → hero bonne constellation + schéma orienté cohérent ; (2) sans fix Pi mais position téléphone → wizard OK ; (3) sans aucune position → wizard non proposé, Hub « Position requise » ; (4) swap → navigateur ne liste que des constellations visibles.

---

## Notes d'implémentation transverses

- **TDD strict** : test rouge → implémentation minimale → vert → commit, à chaque étape.
- **Conventions** : PEP 8/257/484 côté Python ; pattern BLoC + design tokens jour/nuit côté Flutter ; validation visuelle sur Android physique (pas Chrome/émulateur).
- **Query string Flutter** : le projet a déjà été mordu par l'encodage `?` dans le path (`f179db4`). Si `api.getJson` réencode mal la query de `/align/constellation/...`, passer par `Uri.http(..., queryParameters: ...)` côté client HTTP comme pour le catalogue.
- **Asset & build** : `build_constellation_figures.py` ne tourne jamais au runtime ; seul `constellation_figures.json` est lu (et caché via `lru_cache`).
