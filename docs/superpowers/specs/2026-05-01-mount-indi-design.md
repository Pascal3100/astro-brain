# Spec — Bascule pilotage monture sur INDI

> Date : 2026-05-01
> Statut : design validé, prêt pour writing-plans
> Précédente : [v0.2 Setup design](2026-05-01-astro-brain-v02-setup-design.md) (qui consommera cette lib)
> Références protocole : [`docs/technical/indi-reference.md`](../../technical/indi-reference.md), [`docs/technical/nexstar-protocol-reference.md`](../../technical/nexstar-protocol-reference.md) (gardé comme référence protocole)

## Contexte

v0.1 backend pilote la monture via `nexstarpy` 0.1.0, wrapper Python minimaliste autour du protocole NexStar HC. Ça suffit pour le périmètre v0.1 (joystick + tracking + sync GPS), mais v0.2 Setup demande **backlash 4 valeurs**, **cordwrap on/off + position**, **sync RA/Dec ponctuel** (pour v0.3), tous absents de `nexstarpy` :

- Sync `S`/`s` : présent dans le protocole HC (≥ 4.10) mais pas wrappé.
- Backlash AZ/ALT × pos/neg : commandes AUX `MC_*_BACKLASH` (0x10/0x11/0x40/0x41), pass-through HC requis.
- Cordwrap on/off + position : commandes AUX `MC_*_CORDWRAP` (0x38/0x39/0x3a/0x3b/0x3c).
- Etc.

Trois options ont été arbitrées :

1. **Fork interne `nexstarpy`** : ré-écrire un wrapper série Python à partir de la spec protocole. ~600 lignes Python, dette de maintenance, **et code intégralement jeté à v0.5** quand on intégrera INDI pour les caméras + plate solving.
2. **INDI dès maintenant** : driver C++ mature `indi_celestron_aux` qui couvre 6 des 7 besoins en standard ; un seul trou (backlash mount-axis) qu'on patche upstream. Coût initial : intégrer `pyindi-client`, monter `indiserver` en service systemd, ré-écrire l'adapter Pi → INDI. Bénéfice : zéro dette à v0.5.
3. **Hybride INDI + canal série custom** pour le seul backlash. Refusé : conflit d'accès série, archi indéfendable.

**Décision** : option 2. La projection cycle de vie projet montre INDI inévitable à v0.5 (caméras astro Linux = standard INDI), donc autant payer le coût de l'intégration maintenant et le réutiliser pour tous les devices à venir (caméras, focuser, filter wheel).

ADR : [2026-05-01 — Pilotage monture via INDI (drop nexstarpy)](../../project/decisions.md). Câblage tranché en parallèle : [2026-05-01 — Câblage monture via dongle CP2102 USB-TTL 5V](../../project/decisions.md) (HC RJ12 → CP2102 → `/dev/ttyUSB0`).

## Scope

Ce chantier livre **uniquement la lib + l'orchestration INDI**, pas les UIs ni les endpoints v0.2. La spec v0.2 Setup consomme cette lib derrière les mêmes interfaces `MountService` / `TrackingService` qu'aujourd'hui.

### Inclus

1. **`indiserver` en service systemd** sur le Pi, démarre avant `astro-brain.service`, charge `indi_celestron_aux` (et plus tard caméras/focuser).
2. **`mount_indi_adapter.py`** : remplace `nexstar_adapter.py`. Implémente la même interface (`MountService` + `TrackingService` côté FastAPI) avec `pyindi-client` comme transport.
3. **Patch upstream `indi-3rdparty/indi-celestronaux`** : 4 opcodes AUX backlash + 1 property INDI `MOUNT_AXIS_BACKLASH`. PR upstream + fork local le temps du merge.
4. **`pyproject.toml`** : `nexstarpy` out, `pyindi-client` in (extra `hardware`).
5. **Doc** : mises à jour `architecture.md`, `hardware.md` (câblage CP2102 — déjà fait), `deployment.md` (apt deps INDI + procédure build local du paquet patché), `INTEGRATION_CHECKLIST.md` (smoke test des nouvelles capacités, à enrichir car le checklist actuel cible nexstarpy).
6. **`nexstar-protocol-reference.md`** : marqué "kept as protocol reference, not implemented directly" en tête.

### Hors scope explicite

- Hibernate / Wake (HC `x`/`y`) : reporté v0.5+, conditionné à la version du HC (NexStar+ ≥ 5.22 GEM / 5.24 fork).
- Pulse-guide via INDI : v0.7 (PHD2).
- PEC : non applicable (SLT alt-az).
- Mesure automatique de backlash (procédure aller-retour + plate-solve) : reportée v0.5+, dépend de la caméra.
- Connexion réseau d'EKOS au-dessus d'`indiserver` : `indiserver` reste loopback-only (`127.0.0.1:7624`), un client distant éventuel passera par un port forward SSH.

## Architecture cible

```
App Flutter (téléphone) --[Wi-Fi REST + SSE]--> FastAPI (Pi)
                                                      │
                                                      ├── pyindi-client TCP 127.0.0.1:7624
                                                      │       ↓
                                                      │   indiserver (systemd, --user=astro-brain)
                                                      │       ↓
                                                      │   indi_celestron_aux driver C++
                                                      │       ↓
                                                      │   /dev/ttyUSB0 (port HC monture)
                                                      │
                                                      ├── gpsd → DroTek (UART0 / ttyAMA0)
                                                      └── i2c → LIS3MDL + 2× ADXL345 (I2C1)
```

Trois processus système distincts sur le Pi :
- `astro-brain.service` (FastAPI Python)
- `indiserver.service` (binaire C++ INDI)
- `gpsd.socket` + `gpsd.service` (déjà en place)

Ordre de boot : `gpsd` indépendant ; `indiserver` `Wants=astro-brain.service` ; `astro-brain.service` `Requires=indiserver.service` `After=indiserver.service`.

### Lifecycle de l'adapter

`mount_indi_adapter.py` instancie un `PyIndi.BaseClient` au démarrage de FastAPI :

1. `connectServer()` vers `127.0.0.1:7624`.
2. `watchDevice("Celestron AUX")` ou nom équivalent (à confirmer en runtime via le label du driver).
3. À l'arrivée du device, set `CONNECTION.CONNECT=ON`, attend `CONNECTION` en `IPS_OK`, alors publie `mount=ready` sur le bus.
4. Set `DEVICE_PORT.PORT = /dev/ttyUSB0` et `BAUD_RATE = 9600` (HC pass-through ; câblage CP2102 dans [`hardware.md`](../../technical/hardware.md#monture--usb-série-via-dongle-cp2102-port-hc)).
5. Capture les `updateProperty()` callbacks pour propager :
   - `EQUATORIAL_EOD_COORD` → coords mount.
   - `TELESCOPE_TRACK_STATE` → bus `tracking`.
   - `CONNECTION` perdu → bus `mount=error` (équivalent du watchdog actuel).

### Surface API consommée par FastAPI

Mêmes méthodes que `MountService` aujourd'hui (joystick, tracking, sync GPS) — elles deviennent des push de properties INDI :

| Méthode actuelle | Property INDI ciblée |
|---|---|
| `slew(axis, direction, rate)` | `TELESCOPE_SLEW_RATE` (rate index) puis `TELESCOPE_MOTION_NS/WE` (switch ON) |
| `stop_slew(axis?)` | `TELESCOPE_MOTION_NS/WE` (switch OFF) ou `TELESCOPE_ABORT_MOTION` |
| `set_tracking(enabled)` | `TELESCOPE_TRACK_STATE` |
| `set_time(utc)` | `TIME_UTC` (push, stocké côté driver, voir caveat ci-dessous) |
| `set_location(lat, lon)` | `GEOGRAPHIC_COORD` (push, override `updateLocation()` natif) |
| `goto_radec(ra, dec)` (futur v0.3) | `ON_COORD_SET=SLEW` puis `EQUATORIAL_EOD_COORD` |
| `sync_radec(ra, dec)` (futur v0.3) | `ON_COORD_SET=SYNC` puis `EQUATORIAL_EOD_COORD` |

Plus les nouvelles capacités requises par v0.2 :

| Nouvelle méthode | Property INDI |
|---|---|
| `get_backlash(axis, direction)` / `set_backlash(...)` | `MOUNT_AXIS_BACKLASH` (Number RW × 4 éléments — **patch driver requis**) |
| `cordwrap_set_enabled(bool)` / `cordwrap_get_enabled()` | `CORDWRAP` (Switch RW) |
| `cordwrap_set_position(uint24)` / `cordwrap_get_position()` | `CORDWRAP_POS` (Switch UI 4 cardinaux ; pour 24-bit fin, étendre le driver ultérieurement — pas bloquant v0.2) |
| `set_alt_limits(min, max)` (bonus, courses ALT côté monture) | `LIMIT_POS` + `AXIS2_LIMIT` |

Caveat sur `set_time` : le driver AUX advertise `TELESCOPE_HAS_TIME` mais n'override pas `updateTime()` — la valeur est stockée par la base class et sert aux calculs internes du driver, pas pushée à la monture (le SLT n'a pas de RTC AUX-accessible). Aucun impact fonctionnel : le Pi a l'heure GPS, c'est lui le maître du temps.

## Patch driver `indi-celestronaux`

### Périmètre du patch

Ajouter une property `MOUNT_AXIS_BACKLASH` (Number RW, 4 éléments AZ_POS / AZ_NEG / ALT_POS / ALT_NEG, range 0–99) qui mappe les 4 opcodes AUX :

| Opcode | Nom | Direction | Cible |
|---|---|---|---|
| 0x10 | `MC_SET_POS_BACKLASH` | "push" | motor 0x10 (AZ) ou 0x11 (ALT) |
| 0x11 | `MC_SET_NEG_BACKLASH` | "pull" | idem |
| 0x40 | `MC_GET_POS_BACKLASH` | get | idem |
| 0x41 | `MC_GET_NEG_BACKLASH` | get | idem |

### Volume estimé

| Élément | Lignes | Fichier |
|---|---|---|
| 4 enum values dans `AUXCommands` | ~5 | `indi-3rdparty/indi-celestronaux/auxproto.h` |
| `IUFillNumber` × 4 + `IUFillNumberVector` + `defineProperty` | ~15 | `celestronaux.cpp` |
| Méthodes `getBacklash(motor, dir) -> uint8` / `setBacklash(motor, dir, value)` packant `AUXBuffer` et appelant `sendAUXCommand()` | ~30 | `celestronaux.cpp` |
| Override `ISNewNumber()` pour intercepter le set client | ~10 | `celestronaux.cpp` |
| Lecture initiale au connect dans `Handshake()` ou `updateProperties()` pour populer l'UI | ~10 | `celestronaux.cpp` |

**Total : ~70 lignes C++**, ~1 jour de dev + 0.5 jour de test sur le Pi + PR upstream.

### Stratégie fork local

Le temps du merge upstream :
- Fork `indilib/indi-3rdparty` sur GitHub perso, branche `astro-brain-backlash`.
- Build `.deb` maison via `cmake .. && make package` dans `indi-3rdparty`.
- Apt-pin du paquet local pour qu'une `apt upgrade` ne l'écrase pas par la version upstream non patchée.
- Dès le merge upstream → revert au paquet officiel (`apt unhold`).

Documenter cette procédure dans `docs/technical/deployment.md` section "Build local des drivers INDI".

## Migration de l'adapter Python

L'interface consommée par FastAPI (services `MountService` + `TrackingService`) ne change pas. Seul le transport sous-jacent change :

| Avant (`nexstar_adapter.py`) | Après (`mount_indi_adapter.py`) |
|---|---|
| `nexstarpy.NexStar(device)` au start | `PyIndi.BaseClient` + `connectServer()` au start |
| `await asyncio.to_thread(self._client.slew_fixed, ...)` | `mount.getNumber(...).setValue(...)` + `client.sendNewProperty(...)` |
| Watchdog `get_version()` à 0.5 Hz | Callback `serverDisconnected` + `CONNECTION` state changes |
| Publish bus `mount/tracking` à chaque transition | Publish bus dans les callbacks `updateProperty` |

`pyindi-client` est synchrone callback-based (héritage de `BaseClient`). L'adapter wrap les push de properties dans `asyncio.to_thread()` comme avant, et utilise une `asyncio.Queue` pour relayer les callbacks INDI vers la loop principale (équivalent du `bus.publish` actuel).

## Tests

| Niveau | Stratégie |
|---|---|
| **Unitaire workstation** | Fake `BaseClient` qui simule les properties (set/get/define), test du mapping `MountService.method()` → properties. Pas de vraie connexion. |
| **Intégration Pi** | `INTEGRATION_CHECKLIST.md` étendu avec une section dédiée : connect/disconnect, push/get backlash 4 valeurs, cordwrap toggle + poll, slew rate index, set_location round-trip, abort. |
| **Compatibilité firmware** | Lecture initiale `MOUNT_VERSION` au connect ; capability gating documenté pour Sync (HC ≥ 4.10) et cordwrap (forks only). |

Pas de tests INDI dans le repo principal (le driver est externe, c'est upstream qui le teste). On teste **notre** mapping vers INDI.

## Risques & mitigation

| Risque | Probabilité | Mitigation |
|---|---|---|
| Driver `indi_celestron_aux` BETA, comportement instable sur SLT | Moyenne | Smoke test exhaustif dans `INTEGRATION_CHECKLIST.md` avant de déclarer la migration faite. Coupe-circuit accessible (kill `indiserver` via FastAPI endpoint admin si besoin). |
| PR backlash refusée ou stagnante upstream | Moyenne | Fork local maintenable indéfiniment ; le patch est petit (~70 lignes), faible probabilité de conflit avec mainline. |
| `pyindi-client` cassé par update Python ou libindi | Basse | Pinned dans `pyproject.toml` + extra `hardware`. Alternative connue : `MMTObservatory/pyINDI` (asyncio pur, sans SWIG) — plan B documenté. |
| Charge mémoire `indiserver` + driver sur Pi 3 B+ (1 GB RAM) | Basse | ~30–80 MB RSS au repos selon mesures upstream. À mesurer en `INTEGRATION_CHECKLIST.md`. Largement dans les marges (Pi 3 B+ tourne déjà à <300 MB total avec backend Python actuel). |
| Conflit UART HC ↔ UART GPS | Résolu | HC accédé via dongle USB-TTL CP2102 (5V) sur `/dev/ttyUSB0`, UART matériel laissé au GPS. Câblage : [`hardware.md` § Monture](../../technical/hardware.md#monture--usb-série-via-dongle-cp2102-port-hc). |

## Impact sur la spec v0.2 Setup

`2026-05-01-astro-brain-v02-setup-design.md` reste valide en l'état. Une seule reformulation à faire dans la prochaine itération :

- **Item 5 + 6 (Backlash ALT/AZ)** : passe de "calibration backlash automatique" à "**ajustement manuel des 4 valeurs**" (4 sliders 0–99 dans la page Setup, push driver INDI, persistance côté monture). La calibration automatique (procédure aller-retour + mesure dérive via plate-solve) sera reportée à un futur écran "Backlash Tool" en v0.5/v0.6 quand la caméra sera disponible. Référence d'implémentation : *PHD2 Backlash Compensation Tool*.

À ré-éditer dans la spec v0.2 quand on enchaînera sur son implémentation.

## Liens

- Driver INDI Celestron AUX : <https://github.com/indilib/indi-3rdparty/tree/master/indi-celestronaux>
- Driver INDI HC legacy : <https://github.com/indilib/indi/tree/master/drivers/telescope> (`celestrongps.cpp`, `celestrondriver.cpp`)
- pyindi-client : <https://github.com/indilib/pyindi-client>
- Alternative client Python pur : <https://github.com/MMTObservatory/pyINDI>
- Doc INDI : <https://docs.indilib.org/>
- Référence locale onboarding INDI : [`docs/technical/indi-reference.md`](../../technical/indi-reference.md)
- Référence locale protocole NexStar (gardée comme spec, non implémentée directement) : [`docs/technical/nexstar-protocol-reference.md`](../../technical/nexstar-protocol-reference.md)
- PHD2 Backlash Compensation Tool (référence pour calibration auto v0.5+) : <https://openphdguiding.org/manual/?section=Tools.htm#Backlash_Compensation>
