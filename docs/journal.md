# Journal de sessions — Astro-Brain DIY

Fil rouge du projet. Seule la **session en cours** vit ici en détail ; les sessions passées sont archivées par milestone dans `docs/journal/archive/`.

## État du projet

**Version active** : `v0.1 backend` — code complet, service systemd `astro-brain.service` tournant sur le Pi à `http://astro-brain:8000`. Suite automatisée 64 tests verts. Validation physique **GPS + compass I2C + network + system** faite (voir `backend/deploy/INTEGRATION_CHECKLIST.md` sections 0, 1, 2, 4, 5, 6). **Monture pas encore branchée** : sections 3 et 7 à dérouler lors d'une passe dédiée.

**Prochain jalon** : passe avec monture branchée pour clore la v0.1 backend → démarrer le plan app Flutter (design HUD speccé en `docs/superpowers/specs/2026-04-16-astro-brain-v01-design.md`).

## Session en cours

### Session 6 — revue de code v0.1 + renforcement (2026-04-20 / 21)

Grosse revue de code sur tout le backend produit (Tasks 1→17 du plan v0.1). Verdict du reviewer : **« ship with caveats »** — 5 Critical + 6 Significant + nits. Consigne utilisateur : traiter Critical + Significant sans créer de document dédié, uniquement en commits.

Traité en 4 batches :

- **Batch 1 — purification de l'aggregator + chemins env-driven** (commit `ship-with-caveats` series)
    - `aggregator.py` : `FATAL_STATES` / `TRANSIENT_STATES` / `DEGRADED_STATES` dérivés des enums `MountState` / `GpsState` / `NetworkState` / `SystemInfoState`. Un rename dans `subsystems.py` casse maintenant l'aggregator à l'import au lieu de classer silencieusement mal.
    - `"gps=off"` ajouté dans `DEGRADED_STATES` (avant il était traité comme `green`).
    - Variables d'environnement introduites : `ASTRO_BRAIN_SERIAL_DEVICE` (nexstar), `ASTRO_BRAIN_WIFI_IFACE` (network_info). Plus besoin de patcher le code pour tester sur un laptop.

- **Batch 2 — logging + frontières d'exceptions**
    - `orchestrator.py` : `logger.info(...)` au moment du sync et du désarmement — traçable via `journalctl`.
    - `gpsd_adapter.py` : `logger.warning("gpsd poll failed", exc_info=True)` au lieu d'un `except Exception: continue` muet.
    - `nexstar_adapter.py` : `set_time` / `set_location` enveloppés dans try/except qui publient `mount=error` au lieu de faire péter tout le boot.
    - Message du watchdog mount précis (« Restart astro-brain.service to reconnect »), référence à la section 3 de `INTEGRATION_CHECKLIST.md`.

- **Batch 3 — `asyncio.to_thread` pour l'I/O hardware bloquant**
    - `nexstarpy` (constructor, `get_version`, `slew_fixed`, `stop_slew`, `set_time`, `set_location`, `set_tracking_mode`, `close`) : chaque appel synchrone série (9600 baud, 10-50 ms) tourne maintenant sur le thread-pool par défaut. La boucle asyncio reste réactive aux clients SSE, aux handlers REST, et au watchdog.
    - `gpsd-py3` : `gpsd.connect()` et `gpsd.get_current()` offloadés.
    - `network_info.py` : `_compute_network` (subprocess `ip` + `iwgetid`) offloadé ; `_publish_current` devenu async en conséquence.
    - `bus.py` : le docstring documente maintenant explicitement l'invariant « `publish()` ne se fait que sur la main-loop asyncio ». Les adapters qui reviennent du thread-pool via `await asyncio.to_thread(...)` reprennent sur la main-loop avant de publier — invariant préservé.

- **Batch 4 — `deps.py` : fin de la mutation de module**
    - Le pattern `deps.get_bus = lambda: bus` a été remplacé par un pattern FastAPI idiomatique : chaque resolver prend un `Request` et lit `request.app.state.<service>`. Les routes déclarent leurs collaborateurs via `Depends(deps.get_<name>)`.
    - `build_app` installe le bus + les 5 services sur `app.state` au lieu de muter le module `deps`. Chaque instance de FastAPI est désormais autonome : deux apps peuvent co-exister (app réelle + app de test) sans se piétiner.
    - Fixtures de tests : plus de `prev = deps.get_bus ; deps.get_bus = lambda: bus ; ... ; deps.get_bus = prev`. À la place, les tests instancient leur propre `FastAPI()`, peuplent `app.state`, et exposent un `Harness(client, bus)` pour taper directement sur le bus dans les assertions.
    - Test du SSE `/events` : comme il bypasse la couche HTTP et invoque `events(...)` directement, on passe maintenant `bus=` explicitement (le `Depends(...)` n'est résolu que dans le flot HTTP de FastAPI).

64/64 tests verts à chaque batch. Les nits de la revue (typos, docstrings minimaux) ne sont pas traités pour l'instant — ils peuvent attendre le premier vrai cycle de maintenance.

**À faire ensuite** :
- Session de validation physique (câblage GPS, checklist hardware) pour clore officiellement le milestone « v0.1 backend ».
- Ce journal sera archivé au moment du démarrage du plan v0.1 app Flutter.

### Session 6 (suite) — validation physique GPS + compass + 2 fixes (2026-04-21)

GPS DroTek M8N branché sur UART GPIO + compass I2C. Passe de validation partielle (monture pas encore branchée) : sections 0, 1, 2, 4, 5, 6 de `backend/deploy/INTEGRATION_CHECKLIST.md` cochées, findings documentés.

**Section 0 étoffée** — trois étapes qui manquaient à la checklist initiale ont été ajoutées après découverte sur le terrain :
- Charger `i2c-dev` + persistance via `/etc/modules-load.d/i2c-dev.conf` (sans ça, `dtparam=i2c_arm=on` active le bus mais `/dev/i2c-1` n'apparaît pas).
- Désactiver `serial-getty@ttyAMA0.service` (la console de login squatte le port série et bloque gpsd avec `SER: already opened by another process`).
- Retirer `console=serial0,115200` de `/boot/firmware/cmdline.txt` (le kernel y pousse ses logs et pollue les trames NMEA).
- Note : `hciuart.service` n'existe plus sur Pi OS 64-bit Lite récent, `dtoverlay=disable-bt` suffit.

**Résultats hardware** :
- GPS u-blox NEO-M8N, fix_3d atteint en ~30 s (43.5023 N, 1.5194 E à Toulouse), 14 satellites utilisés, HDOP 0.83, 4 constellations (GPS/GLONASS/Galileo/BeiDou).
- Compass I2C : **LIS3MDL** (ST Microelectronics) à `0x1E`, identifié via `WHO_AM_I=0x3D`. Pas un HMC5883L contrairement à ce que supposait `docs/hardware_wiring.md` avant cette passe. Activé en mode continu (`CTRL_REG1=0x1C`, `CTRL_REG3=0x00`, `CTRL_REG4=0x0C`), mesures 3 axes live confirmées (variations de magnitude/heading quand on tourne le module). Non utilisé par la v0.1 backend, prêt pour v0.2.
- Network en mode `client`, SSID + IP corrects.
- System idle à 56 °C, load 0.05.

**Deux bugs découverts et fixés** (commit `57e7553`) :
- `gpsd_adapter` : `gpsd-py3.get_current()` renvoie le **dernier paquet** (typiquement TPV sans champ `sats`), pas un état agrégé. Résultat : `details.satellites = 0` alors que le GPS voit 14 sats. Fix : cacher la dernière valeur `sats_valid > 0` lue dans une trame SKY et l'utiliser comme valeur courante.
- `nexstar_adapter` : le subsystem `tracking` n'était publié **qu'après** une init monture réussie — quand la monture est débranchée (mount=error), `/state` ne remontait que 4 subsystems au lieu des 5 attendus par la checklist. Fix : publier `tracking=off` dès l'entrée de `start()`, avant la tentative de connexion.

64/64 tests verts après fix. Validation live post-deploy : `/state` remonte bien `tracking: off` + `satellites: 14`, les 5 subsystems présents.

**À faire** : passe dédiée avec monture Celestron branchée pour clore la v0.1 backend (sections 3 et 7 de la checklist).

### Session 7 — décision capteurs d'inclinaison (2026-04-24)

Arbitrage hardware sur la mesure d'inclinaison : choix de **2 × ADXL345** (accéléromètres I2C simples) plutôt qu'un IMU 9DOF.

- **ADXL345 tube** (`0x53`) → zéro ALT + détection butées d'inclinaison
- **ADXL345 monture** (`0x1D`) → mise à niveau pré-session (bulle virtuelle)

Justification : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas besoin de fusion de capteurs ni de cap tilt-compensé (le plate solve v0.4 prendra le relais pour le pointage précis). Les 2 modules cohabitent sur I2C1 grâce à la pin SDO qui sélectionne l'adresse — pas de multiplexeur, pas de conflit avec le LIS3MDL (`0x1E`).

Capteurs commandés. Détails et pages UI associées dans `docs/backlog.md` (section "Capteurs d'inclinaison tube + monture"). Mentions liées mises à jour : v0.2 mise en station (niveau), v0.5 réglages techniques monture (courses ALT), et piste IMU de "Position persistante" (écartée).

## Archives

- [`2026-04-backend-v0.1.md`](journal/archive/2026-04-backend-v0.1.md) — Sessions 1→5 (brainstorm, spec design, monorepo + uv, Tasks 1-16 du plan backend, checklist hardware).
