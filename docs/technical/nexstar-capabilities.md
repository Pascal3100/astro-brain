# Capacités `nexstarpy` 0.1.0 + protocole NexStar

Source de vérité sur ce que la **lib `nexstarpy` 0.1.0** expose. Évite les hypothèses sur ce qui est wrappé dans le code actuel.

> ⚠️ Pour la **liste exhaustive du protocole NexStar** lui-même (HC + AUX), incluant sync, backlash, cordwrap, hibernate, et toutes les commandes que la lib n'expose pas mais que la HC NexStar+ supporte : voir [`nexstar-protocol-reference.md`](nexstar-protocol-reference.md). Le présent document ne couvre que ce qui est wrappé par la lib Python actuelle.

> Lib utilisée : `nexstarpy==0.1.0` (PyPI, `requires-python >= 3.13`). Wrapper minimaliste autour du protocole série NexStar (9600 baud, 8N1, terminateur `#`, timeout 3.5 s).

## API exposée par `NexStar`

### Position
- `get_radec(precise: bool = False) -> (ra_deg, dec_deg)` — RA/Dec en degrés.
- `get_azm_alt(precise: bool = False) -> (azm_deg, alt_deg)` — Alt/Az en degrés.

`precise=True` utilise la résolution 24 bits (`0x1000000`/360°) au lieu de 16 bits (`0x10000`/360°).

### GoTo
- `goto_radec(ra, dec, precise=False)` — `0x52`/`0x72` selon précision.
- `goto_azm_alt(azm, alt)` — `0x42`, résolution 16 bits seulement.
- `cancel_goto()` — `0x4D`.

### Slew manuel
- `slew_fixed(axis, direction, rate)` — rate `0..9` (la raquette Celestron).
- `slew_variable(axis, direction, rate)` — rate `0..150` arcsec/sec.

`Axis ∈ {AZM_RA=0x10, ALT_DEC=0x11}`, `SlewDirection ∈ {POSITIVE_FIXED=0x24, NEGATIVE_FIXED=0x25, POSITIVE=0x06, NEGATIVE=0x07}`.

### Tracking
- `set_tracking_mode(mode)` / `get_tracking_mode()` — `TrackingMode ∈ {OFF=0, ALT_AZ=1, EQ_NORTH=2, EQ_SOUTH=3}`.

### Temps & position
- `set_time((h, m, s, mo, d, y, tz_offset, dst))` — 8 octets, `0x48`.
- `set_location((lat_deg, lat_min, lat_sec, hemi), (lon_deg, lon_min, lon_sec, hemi))` — `0x57`.
- `Hemisphere ∈ {NORTH=0, SOUTH=1, EAST=0, WEST=1}`.
- ⚠️ **Pas de `get_location`/`get_time` exposés** alors que les commandes existent en constants (`0x77`, `0x68`).

### GPS
- `is_gps_linked() -> bool` — pass-through `0x50` vers `DeviceID.GPS_UNIT=0xB0`. Vérifie qu'un GPS Celestron StarSense est branché — **sans rapport avec le DroTek qu'on utilise**.

### Misc
- `get_version() -> (major, minor)` — firmware monture.
- `get_model() -> Model` — `Model ∈ {GPS_SERIES=1, I_SERIES=3, I_SERIES_SE=4, CGE=5, ADVANCED_GT=6, SLT=7, CPC=9, GT=10, SE_4_5=11, SE_6_8=12}`.
- `close()` — ferme le port série.
- ⚠️ **Pas de `is_goto_in_progress`** (la commande `0x4C` est définie en constants mais pas wrappée).
- ⚠️ **Pas d'`echo`** (la commande `0x4B` est définie mais pas wrappée).

## Ce que la lib **n'expose pas** mais que le protocole **supporte**

> Mise à jour suite à la recherche complète du protocole (cf. [`nexstar-protocol-reference.md`](nexstar-protocol-reference.md)). La conclusion change radicalement par rapport à la version initiale de ce doc : presque tout ce qui manque dans `nexstarpy` est en réalité **disponible dans le protocole** — soit côté HC (PDF Celestron 2006 v1.2), soit côté AUX (Andre Paquette 2003).

| Fonction | Statut protocole | Wrappé par nexstarpy ? |
|---|---|---|
| **Sync `S`/`s`** (3-star wizard) | ✅ HC ≥ 4.10, dans le PDF officiel | ❌ |
| **Backlash get/set** (par axe, pos/neg, 0-99) | ✅ AUX `MC_GET/SET_*_BACKLASH` (msgIds 0x10/0x11/0x40/0x41) | ❌ |
| **Cordwrap on/off/poll/pos** | ✅ AUX (msgIds 0x38/0x39/0x3B/0x3A/0x3C, AZM only) | ❌ |
| **Is Aligned `J`** | ✅ HC, dans le PDF | ❌ |
| **GoTo in progress `L`** | ✅ HC | ⚠️ constant défini, méthode absente |
| **Echo `K`** | ✅ HC | ⚠️ constant défini, méthode absente |
| **Get Location `w` / Get Time `h`** | ✅ HC ≥ 2.3 | ⚠️ constants définies, méthodes absentes |
| **Hibernate `x` / Wake `y`** | ✅ Community (NexStar+ HC ≥ 5.22 GEM / 5.24 fork) | ❌ |
| **Autoguide rate** (par axe) | ✅ AUX `MC_SET/GET_AUTOGUIDE_RATE` | ❌ |
| **Slew Done par axe** (polling fin GoTo) | ✅ AUX `MC_SLEW_DONE` (cap polling à 10 Hz, sinon overshoot) | ❌ |
| **PEC** (record/playback) | ✅ AUX (mounts EQ uniquement — pas SLT) | ❌ |
| **Custom slew rates** | ✅ AUX (taux variables sur chaque axe) | ⚠️ partiel via `slew_variable` 0-150 |
| **Slew limits / courses ALT-AZ** | ❌ pas dans le protocole — réglages HC internes seulement | n/a |

**Conséquence importante** : la position « monture vue comme actuator dumb » prise dans la version précédente de ce doc n'est plus la bonne. On peut, via le protocole, faire `sync_radec` natif, lire `is_aligned`, régler le backlash et le cordwrap directement côté monture. C'est juste que **`nexstarpy` 0.1.0 n'a pas de wrapper** pour ces commandes.

## Conséquences pour la roadmap

### Macro 2 — Setup (implémentations révisées)

| Item | Implémentation | Source |
|---|---|---|
| Calibration LIS3MDL (compass) | Off-mount, full Pi-side (lecture I2C, persistance disque). | Indépendant de NexStar. |
| Calibration ADXL345 ×2 | Off-mount, full Pi-side. | Indépendant de NexStar. |
| Courses ALT min/max | Lecture position via **ADXL345 tube**. Stockées Pi-side, appliquées en software (clamp côté backend avant émission slew/goto). | Pas de slew limits dans le protocole. |
| **Cordwrap protection AZ** | **Côté monture, via AUX** : `MC_CWRAP_ENABLE/DISABLE` (msgId 0x38/0x39), `MC_CWRAP_GET_POS/SET_POS` (0x3B/0x3C). On expose un toggle dans Setup + une position de cordwrap. | AUX pass-through, AZM motor (0x10). |
| **Backlash ALT/AZ** | **Côté monture, via AUX** : `MC_GET/SET_POS_BACKLASH` (msgId 0x40/0x10), `MC_GET/SET_NEG_BACKLASH` (0x41/0x11), valeur 0-99 par axe par direction. La monture gère le préambule elle-même. La routine de calibration mesure puis push la valeur. | AUX pass-through, motor 0x10 (AZ) et 0x11 (ALT). |
| Network/IP config | Côté Pi (config réseau / hotspot). | Indépendant de NexStar. |
| À propos | Lecture `get_version`, `get_model`, + `get_location`/`get_time` à ajouter. | HC standard. |

### Macro 3 — Mise en station + GoTo basique

L'alignement 3 étoiles peut désormais **utiliser le sync natif de la monture** :

- À chaque étoile centrée, on push `sync_radec(ra, dec)` (commande HC `S` / `s`, présente dans la firmware ≥ 4.10).
- La monture maintient son propre modèle d'alignement interne ; on lui demande ensuite des `goto_radec` natifs.
- Plus besoin de matrice de rotation Pi-side (Wahba/SVD) — fallback uniquement si le firmware s'avère < 4.10 (très improbable, à vérifier en début de plan Macro 3 via `get_version`).
- Avant le wizard : `is_aligned()` (`J`) pour vérifier l'état initial.
- Pendant un GoTo : `is_goto_in_progress()` (`L`) pour le polling fin.

### Conséquence : étendre `nexstarpy` ou bypasser

L'agent de recherche recommande de **ne pas dépendre de la lib upstream** pour la suite — c'est un wrapper minimaliste 0.1.0 mono-auteur, et on a besoin de l'AUX pass-through (cordwrap, backlash) qu'elle ne wrappera probablement jamais.

Deux options à arbitrer au plan Macro 2 :

1. **Fork interne** dans `backend/astro_brain/adapters/nexstar/` — réécriture maison ciblée, ne dépend plus du tout de `nexstarpy`. On garde l'interface du `Protocol` actuel pour ne rien casser au reste du backend.
2. **Patch local** + dépendance Git pinned — plus rapide à mettre en place mais on porte deux dettes : la lib upstream + nos additions.

Recommandation : option 1 (fork interne), parce que les ajouts AUX sont structurellement différents du wrapper HC actuel et qu'on aura besoin de la liberté.

## Notes opérationnelles

- La lib utilise `pyserial` synchrone bloquant. On wrappe systématiquement les appels dans `asyncio.to_thread(...)` côté `nexstar_adapter` (cf. `docs/technical/architecture.md`).
- Le timeout par défaut est 3.5 s ; certaines commandes (GoTo) peuvent durer plus longtemps mais retournent immédiatement (le `0x52` répond avant la fin du mouvement). Pour savoir si le GoTo est terminé, il faudrait `is_goto_in_progress` (à ajouter) ou un polling de `get_azm_alt` jusqu'à stabilisation.
- `set_time` et `set_location` n'ont pas d'ACK structuré — on suppose le succès si pas de timeout.

## Liens

- Code de la lib : `pip download nexstarpy==0.1.0 --no-deps` (5.8 KB sdist, 4 fichiers).
- Spec protocole Celestron officielle : "NexStar Communication Protocol" (PDF Celestron, à archiver dans `docs/references/` quand utile).
- Adapter Pi : `backend/astro_brain/adapters/nexstar_adapter.py`.
