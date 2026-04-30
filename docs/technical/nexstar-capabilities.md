# Capacités `nexstarpy` 0.1.0 + protocole NexStar

Source de vérité sur ce qu'on peut et ne peut pas faire avec la lib actuelle. Évite les hypothèses pendant les brainstorms et les plans d'implémentation.

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

## Ce que le protocole NexStar **n'expose pas** (côté série)

Ces fonctions existent **uniquement dans le menu de la raquette HC**, pas dans le protocole série standard :

- ❌ **Sync / alignment point** — pas de `sync_radec(ra, dec)`. Le wizard d'alignement de la HC est interne à la monture et n'est pas pilotable via `0x50` ou autre. On devra **soit** étendre la lib (si une commande non-documentée existe — à creuser), **soit** faire l'alignement **Pi-side** (matrice de rotation 3D maintenue par notre backend, monture vue comme actuator dumb).
- ❌ **Cordwrap on/off** — toggle exclusivement HC. Pas de commande série standard. Notre seule option : tracker l'AZ cumulé Pi-side via `get_azm_alt` polled.
- ❌ **Backlash compensation** — réglages HC. Pas d'API série pour les régler ni les lire. Notre option : faire la **compensation backlash software Pi-side** (intercepteur dans `nexstar_adapter` qui ajoute un mouvement de pré-charge à chaque inversion de direction).
- ❌ **Custom slew rates** — la raquette permet de personnaliser les 9 rates fixes ; pas exposé série.
- ❌ **PEC (Periodic Error Correction)** — réglage HC, pas pilotable série.
- ❌ **GoTo limits / slew limits** — pas de courses ALT/AZ à régler côté monture.
- ❌ **État alignement** — pas de commande "es-tu alignée ?". Si on alimente la monture sans HC, elle n'est jamais "alignée" dans son sens interne. C'est nous qui maintenons l'état d'alignement Pi-side.

## Conséquences pour la roadmap

### v0.2 (Setup)

| Item | Implémentation | Source |
|---|---|---|
| Calibration LIS3MDL (compass) | Off-mount, full Pi-side (lecture I2C, persistance disque). | Indépendant de NexStar. |
| Calibration ADXL345 ×2 | Off-mount, full Pi-side. | Indépendant de NexStar. |
| Courses ALT min/max | Lecture position via **ADXL345 tube**, pas via `get_azm_alt`. Stockées Pi-side. | L'ADXL345 donne l'ALT physique vraie, indépendante du référentiel monture. |
| **Cordwrap protection AZ** | **Option 2 retenue** : counter software Pi-side qui intègre les variations d'AZ depuis `get_azm_alt`. Alerte UI quand on approche d'un seuil (~1.5 tour). Optionnel : intercepter un GoTo qui éloignerait davantage. **Options 1 (NexStar) écartée** : pas exposée. | Polling `get_azm_alt` dans `MountService`. |
| **Backlash ALT/AZ** | **Software Pi-side** : à chaque inversion de direction de slew, on ajoute un mouvement de préambule (ex. 0.5° ALT en plus avant de slew dans la direction inverse). Valeurs réglées par calibration : la routine demande à l'utilisateur de centrer une étoile, puis renverse — elle mesure le retard avant que la monture ne réponde. | Wrapper autour de `slew_fixed`/`slew_variable` dans `nexstar_adapter`. |
| Network/IP config | Côté Pi (config réseau / hotspot). | Indépendant de NexStar. |
| À propos | Lecture `get_version`, `get_model`. | OK avec lib actuelle. |

### v0.3 (Mise en station + GoTo)

L'alignement 3 étoiles devra **vivre Pi-side**, parce que `nexstarpy` n'expose pas de sync :

- Notre backend maintient une matrice de rotation entre repère monture (AZ/ALT bruts de la monture, qui démarrent toujours à `(0,0)` au boot) et repère ciel (RA/Dec).
- Pour un GoTo sur RA/Dec : on convertit en AZ/ALT-monture via la matrice + `goto_azm_alt`.
- Pour un slew manuel : direct sur l'axe, pas de transformation.
- Pour la lecture position courante : on lit `get_azm_alt` puis on applique la matrice inverse pour afficher RA/Dec.

Trois `sync_star` accumulent 3 paires `(v_sky, v_mount)`, on résout Wahba (SVD) pour fitter la rotation rigide.

> **À investiguer au moment du plan v0.3** : certains forks/fork de protocole NexStar exposent une commande `Q` (Sync). Vérifier si la firmware de notre monture la supporte (commande série brute, hors `nexstarpy`). Si oui, ça simplifie tout — on push les 3 syncs à la monture et on lit les coordonnées RA/Dec qu'elle calcule. Si non, fallback Pi-side comme décrit.

### Ce qui demanderait de patcher `nexstarpy`

Si on a besoin d'aller plus loin, candidats à ajouter (fork ou PR upstream) :

- `is_goto_in_progress() -> bool` — utile pour bloquer les commandes pendant un GoTo.
- `get_location() / get_time()` — useful pour vérifier la sync GPS-monture.
- `echo(byte) -> byte` — heartbeat pour vérifier que la connexion est vivante (le watchdog actuel utilise `get_version`, ce qui marche aussi).
- Hypothétique `sync_radec(ra, dec)` si la firmware le supporte — à tester avec un capture série de la HC en mode alignement.

## Notes opérationnelles

- La lib utilise `pyserial` synchrone bloquant. On wrappe systématiquement les appels dans `asyncio.to_thread(...)` côté `nexstar_adapter` (cf. `docs/technical/architecture.md`).
- Le timeout par défaut est 3.5 s ; certaines commandes (GoTo) peuvent durer plus longtemps mais retournent immédiatement (le `0x52` répond avant la fin du mouvement). Pour savoir si le GoTo est terminé, il faudrait `is_goto_in_progress` (à ajouter) ou un polling de `get_azm_alt` jusqu'à stabilisation.
- `set_time` et `set_location` n'ont pas d'ACK structuré — on suppose le succès si pas de timeout.

## Liens

- Code de la lib : `pip download nexstarpy==0.1.0 --no-deps` (5.8 KB sdist, 4 fichiers).
- Spec protocole Celestron officielle : "NexStar Communication Protocol" (PDF Celestron, à archiver dans `docs/references/` quand utile).
- Adapter Pi : `backend/astro_brain/adapters/nexstar_adapter.py`.
