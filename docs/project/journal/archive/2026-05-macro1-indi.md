# Archive — Macro 1 Migration INDI (mai 2026)

Sessions 15 + 16 du journal principal, archivées en clôturant la Session 21 (2026-05-09).
Macro 1 "backend INDI atterri sur main" est achevée côté code ; reste smoke test E2E bloqué par dongle CP2102.

---

### Session 16 — migration backend mount nexstarpy → INDI atterrie sur main (2026-05-04)

Suite directe de Session 15 (stack INDI installée sur le Pi). Découverte au tour de projet post-cleanup : la branche locale `feat/mount-indi` contenait déjà 15 commits livrant toute la migration backend, écrits en mode `subagent-driven-development` strict (TDD, fresh implementer + double review par task). Décision : rebase de la branche sur `main` (qui avait avancé avec le scaffold v0.2 Setup + cleanup docs INDI), puis revue complète, plutôt que tout réimplémenter.

**1. Rebase `feat/mount-indi` sur `main`**

15 commits rejoués proprement sur `main`. Conflits docs résolus en faveur du contenu le plus à jour : `architecture.md` garde la vue stack INDI (Astroberry + processus systemd) post-Session 15 + restaure le diagramme ASCII enrichi de la branche ; `journal.md` conserve la section "État du projet" consolidée et déplace le contenu Session 14 d'origine vers cette Session 16. Pas de perte de signal côté backend : tous les commits de code branche conservés tels quels.

**2. Récap des commits backend rejoués sur main**

| # | Commit | Sujet |
|---|---|---|
| 1 | `5786484` | helpers purs `_indi_property_helpers.py` (set_number, set_switch, state) |
| 2 | `0b6e92b` | `FakeIndiClient` mirroring de `PyIndi.BaseClient` |
| 3 | `61377d9` | `MountIndiAdapter` skeleton (`start`/`stop` + device discovery 5 s) |
| 4 | `8b4742c` | slew + stop_slew via `TELESCOPE_MOTION_NS/WE` + `TELESCOPE_SLEW_RATE` |
| 5 | `772c94e` | `set_time` / `set_location` via `TIME_UTC` + `GEOGRAPHIC_COORD` |
| 6 | `9e201a9` | `set_tracking` via `TELESCOPE_TRACK_STATE` |
| 7 | `df6a82c` | cordwrap (enabled + position 4 cardinaux) |
| 8 | `18fd745` | backlash 4 valeurs (degrade gracieusement si property absente) |
| 9 | `9d44732` | `AstroBrainIndiClient(PyIndi.BaseClient)` production subclass |
| 10 | `81967fa` | wire `MountIndiAdapter` dans `app.py`, drop `nexstarpy` + `pyserial` |
| 11 | `3449856` | systemd `indiserver.service` + `Requires=` côté `astro-brain.service` |
| 12 | `9ed68da` | script `build-indi-celestronaux.sh` (build .deb sur Pi + apt-mark hold) |
| 13 | `f40b2f7` | docs : bascule `architecture.md` + `deployment.md` + `INTEGRATION_CHECKLIST.md` |
| fix | `f2cb6c3` | `bus.publish` thread-safe via `loop.call_soon_threadsafe` (fix race PyIndi callback) |

**89/89 tests verts** (64 v0.1 + 25 migration INDI) à chaque étape de la branche, validés à nouveau post-rebase.

Patch C++ du driver dans un repo séparé : `/tmp/indi-research/indi-3rdparty/`, branche `astro-brain-backlash`, commit `538810c`. Expose `MOUNT_AXIS_BACKLASH` (Number RW × 4 : `AZ_POS`/`AZ_NEG`/`ALT_POS`/`ALT_NEG`) via les opcodes AUX `0x10`/`0x11`/`0x40`/`0x41`. Conventions modernes du driver respectées (`INDI::PropertyNumber`, dispatch via `processResponse`). Build .deb deferred au Pi (pas de `libindi-dev` sur workstation).

**3. Final review post-rebase**

`superpowers:code-reviewer` (Sonnet) sur `ae29dca..HEAD` pré-fix : **approuvé avec fixes**, aucun issue critique. 2 items "Important" appliqués immédiatement (commit `93e59bc`) :

- `logger.exception(...)` dans chaque `except` de `MountIndiAdapter` (start/stop/slew/stop_slew/set_time/set_location/set_tracking/cordwrap_set_*/set_backlash). Le smoke test Pi sera diagnosticable via `journalctl` au lieu d'un état `error` opaque.
- `active_slews` deep-copié (`[dict(s) for s in ...]`) avant publish bus, côté `MountIndiAdapter` ET `FakeMount`, pour fermer la possibilité qu'une mutation in-place change silencieusement un `SubsystemState.details` déjà émis.

Items "Minor" (~10) non bloquants laissés en suspens — la plupart sont liés à des comportements à observer pendant le smoke test (driver round-trip `TIME_UTC`, vrais noms d'éléments `CORDWRAP_POS`, ordre de lecture env vars). Détail dans le rapport reviewer (non archivé). 89/89 tests verts post-fix.

**4. Hardware en attente — dongle CP2102 5V**

Smoke test E2E (Task 14 du plan migration) bloque sur la livraison du **dongle USB-TTL CP2102 5V** pour le port HC RJ12. Tant qu'il n'arrive pas, la monture ne peut pas être branchée → pas de validation terrain.

**Reprise quand le dongle arrive** :
1. Câbler selon `docs/technical/hardware.md` section "Monture — USB-série via dongle CP2102" (⚠️ vérif multimètre broche 2 RJ12 : peut exposer +12 V selon HC).
2. Sur le Pi : `git pull && bash backend/deploy/install.sh` (installe `indiserver.service` + relance `astro-brain.service`).
3. Forker `indilib/indi-3rdparty` sur GitHub perso, pousser la branche `astro-brain-backlash` depuis `/tmp/indi-research/indi-3rdparty/`, cloner sur le Pi dans `~/code/indi-3rdparty/`, lancer `~/code/astro-brain/backend/deploy/build-indi-celestronaux.sh`.
4. Dérouler `INTEGRATION_CHECKLIST.md` sections 0 (Stack INDI), 3 (Mount), Backlash, Cordwrap. Noter les `### Findings`.
5. Une fois la checklist verte, ouvrir le chantier v0.2 Setup (`superpowers:writing-plans` sur la spec validée Session 13).

**Risques de déploiement à vérifier sur le Pi** (notés dans le plan, lignes 2549-2554) :
- `pyindi-client` indispo en wheel pip → probablement `apt install python3-indi-client` requis. Si `uv sync --extra hardware` échoue à compiler, fallback : paquet apt + venv `--system-site-packages`.
- `INDI_DEVICE_NAME = "Celestron AUX"` est une supposition. À confirmer via `indi_getprop -h localhost '*.CONNECTION'` une fois `indiserver` lancé. Ajuster la constante si besoin.
- `PORT_TYPE` / baud rate : adapter ne pousse pas `PORT_TYPE` ; s'appuie sur le default. Si la connexion échoue, ajouter `PORT_TYPE=PORT_HC_USB` 9600 dans `MountIndiAdapter.start()` après `_await_device`.

**Items deferred au final review de la branche** (volontairement non corrigés ici, à traiter post-smoke-test) :
- `MountIndiAdapter._serial_device` stocké mais jamais poussé au driver via `DEVICE_PORT`. À traiter selon comportement réel : pousser `DEVICE_PORT` si le default ne tape pas `/dev/ttyUSB0`, ou supprimer le champ mort.
- `_await_device()` polle `getDevice()` sur le thread asyncio (pas dans `to_thread`). Reviewer initial juge low-risk pour un flow one-shot de startup ; à reconsidérer si pause observable au boot.

**5. Plan v0.2 Setup écrit**

Tour de spec v0.2 (`docs/superpowers/specs/2026-05-01-astro-brain-v02-setup-design.md`) après le merge migration. Génération du plan d'implémentation via `Plan` agent : `docs/superpowers/plans/2026-05-04-v02-setup-implementation.md` — 34 tasks structurées en 5 slices (INFRA / A capteurs / B courses ALT / C about / D mount-tuning bloqué dongle), stratégie 1 branche par slice avec merge incrémental.

Décisions arbitrées en relisant le plan :
- **Algo ellipsoid fit LIS3MDL** : Li-Lawley analytique simplifié (~50 LOC) + filtre outliers, fallback least-squares si terrain bruité.
- **Heading compass tilt-compensé en v0.2** (initialement reporté v0.3) : ADXL co-localisé sur la base tournante avec compass + DroTek → fusion possible. Justification utilisateur : la mise en station impose une monture nivelée, donc l'ordre #1 → #2 est naturel. Helper pure numpy ajouté en Task A-5b ; stream payload `/sensors/compass/stream` gagne `tilt_compensated: bool`. Fallback naïve documenté.
- **Merge slice par slice** dans `main` plutôt qu'attendre le milestone complet. Plus simple, moins de conflits.

Slice D reste mergeable seulement après livraison dongle CP2102 + smoke INDI vert (Task 14 du plan migration).

**6. Méta**

Journal au plafond après cette session (Sessions 9-16 = 8 sessions). Prochaine session : archiver Sessions 9-14 dans `journal/archive/2026-04-mount-indi-migration.md` (milestone : migration mount nexstarpy → INDI), garder Sessions 15-16 + la suivante en tête de file.

### Session 15 — install INDI 2.2.0 + driver Celestron AUX sur le Pi (2026-05-04)

Session ops sur le Pi, dans le prolongement direct de Session 14 (où le build INDI from source tournait en arrière-plan pendant le scaffold Flutter v0.2). Plusieurs détours avant de trouver la voie propre.

**1. Diagnostic du build interrompu**

Le `make` source démarré en Session 14 s'était arrêté à 39 % sans message d'erreur dans le log et sans trace OOM dans `dmesg`. Pi rebooté entre-temps (uptime 4 min). Hypothèse retenue : déconnexion SSH → SIGHUP → make tué. Pas un manque de mémoire — zram ~926 Mi tenait largement.

**2. Détour build (~2 h)**

Première tentative de redémarrage encadré : install `tmux`, ajout swapfile disque 2 Go priorité 10 (en backup du zram prio 100), relance `make -j3` détaché en tmux, surveillance via cron 20 min. Build qui dépasse 41 % avec 143 targets construits, swap qui s'allume à 1.3 Go (l'ajout swap était bien utile pour les `.cpp` lourds malgré l'absence d'OOM précédent). Question légitime de l'utilisateur en cours de route : *"si on ne modifie rien, pourquoi compiler ?"*. Première confusion de ma part : j'ai d'abord regardé le paquet `indi-bin` Debian Trixie (1.9.9, sans driver AUX, donc inadapté au cap projet visé en libindi 2.x). J'ai relancé le build source en pensant que c'était la seule option.

**3. Bascule Astroberry après diagnostic réseau**

Sur retour de l'utilisateur (*"pourquoi accepter de faire des choses qui n'ont pas sens ?"*), réexamen complet :

- **PPA mutlaqja** (`ppa:mutlaqja/ppa`) — recommandée par INDI, mais `ppa.launchpadcontent.net:443` rejette activement les connexions TCP depuis le Pi (refus en 47 ms en IPv4 et IPv6). Pas un timeout, un reset actif. Le reste du net fonctionne (Debian, indilib.org). Inutilisable aujourd'hui.
- **Astroberry "old repo"** (`astroberry.io/repo/`) — mort, 404 sur tous les paths apt.
- **Astroberry "new repo"** (`astroberry.io/debian/`) — **actif**, release Trixie arm64 avec clé GPG 2 260 octets, documenté comme source officielle Pi par `indilib.org/download/raspberry-pi.html`.

Inspection du `Packages.gz` Astroberry Trixie : `libindi1` / `indi-bin` / `libindi-dev` en **2.2.0**, `indi-celestronaux` en **1.5**, plus `indi-gpsd 0.6`, `indi-gpsnmea 0.2`, `indi-rpi-gpio`. Tout ce dont la stack INDI a besoin pour l'archi du projet.

**4. Install effective**

Source `astroberry.sources` (deb822) installée à `/etc/apt/sources.list.d/`, clé GPG dans `/etc/apt/keyrings/astroberry.gpg`. Simulation `apt install -s indi-bin indi-celestronaux libindi-dev indi-gpsd` : 0 conflit, 8 paquets nouveaux (6 Astroberry + 2 deps Debian Trixie : `libxisf0`, `librtlsdr0`). Install vrai en moins de 2 minutes.

Vérifs :
- `which indi_celestron_aux` → `/usr/bin/indi_celestron_aux` (195K, daté 2024-08-26)
- `indiserver -v indi_celestron_aux` démarre, écoute port **7624** + socket `/tmp/indiserver`, snoope GPS Simulator + Dome Simulator, enumère 2 math plugins d'alignement (**SVD + Nearest** — bonus utile pour le wizard 3 étoiles v0.3)
- `pascal3100` ajouté automatiquement au groupe `dialout` (accès `/dev/ttyUSB0` quand connecteurs arrivent)

**5. Cleanup**

`/swapfile` 2 Go retiré (swapoff + rm + sed fstab) → retour à zram seul, état initial. `~/code/indi/` (source + 41 % de cache build, 971 Mi) supprimé. Disque libéré : 7.4 Go → 4.5 Go.

**Conséquence pour le cap migration INDI**

L'ADR `2026-05-01 — Pilotage monture via INDI (drop nexstarpy)` avait déjà tranché : on bascule sur `indi_celestron_aux` + `pyindi-client`. Cette session **concrétise la Task 0** du plan `docs/superpowers/plans/2026-05-01-mount-indi-migration.md` (install Pi de la stack INDI). Capacités vérifiées en sanity check (sync, alignement SVD + Nearest, properties cordwrap, slew rates 8 niveaux) cohérentes avec la couverture documentée dans `docs/technical/indi-reference.md`. Le seul vrai trou identifié reste **backlash mount-axis 4 valeurs** (opcodes `MC_*_BACKLASH` non câblés dans `auxproto.h` du driver), traité côté plan migration via patch upstream.

Reste à faire côté plan migration (cf. `docs/superpowers/plans/2026-05-01-mount-indi-migration.md`) : `MountIndiAdapter`, retrait de `NexStarMountAdapter` + extra hardware `nexstarpy`, unit systemd `indiserver.service`, smoke test connecteurs branchés.

**Refs**
- Repo : `https://astroberry.io/debian/` — clé `/etc/apt/keyrings/astroberry.gpg`, sources `/etc/apt/sources.list.d/astroberry.sources`
- Nouvelle ADR ajoutée : `2026-05-04 — Stack INDI installée via repo Astroberry Debian Trixie arm64` (cf. `docs/project/decisions.md`)
