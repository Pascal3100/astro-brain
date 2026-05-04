# Décisions d'architecture (ADRs)

Décisions structurantes du projet, sous forme de notes courtes. Une décision = un titre + contexte + choix + rationale. Pas un journal — uniquement les décisions qui méritent d'être retrouvables.

---

## 2026-04-15 — Pas d'Arduino dans la chaîne

**Contexte** : design initial prévoyait un Arduino comme intermédiaire entre Pi et monture pour temps-réel.

**Décision** : Pi communique directement avec la monture via série (port HC NexStar). _Lib révisée par l'ADR du 2026-05-01 (INDI)._

**Rationale** : la monture Celestron a déjà son micro-contrôleur interne pour le temps-réel moteur. Un Arduino ajouterait une couche série de plus, sans valeur. Le Pi reste réactif côté FastAPI via les patterns asyncio.

---

## 2026-04-15 — REST + SSE, pas de WebSocket

**Décision** : commandes via REST (`/slew`, `/stop`, `/tracking`, `/goto`), état via SSE (`/events`).

**Rationale** : simple à implémenter en FastAPI, simple à consommer en Flutter, compatible HTTP/1.1 partout. Le D-Pad fonctionne en start/stop (pas besoin de bidirectionnel temps-réel). SSE supporte la reconnexion auto.

---

## 2026-04-21 — Capteurs hardware via GPIO uniquement

**Contexte** : le Pi 3 B+ a 4 ports USB. Le projet final aura 3 caméras + monture (USB), ce qui sature.

**Décision** : tous les capteurs (GPS DroTek, compass LIS3MDL, ADXL345 ×2) passent par les GPIO (UART0 + I2C1), pas via USB.

**Rationale** : préserve les ports USB pour la monture et les caméras. Les bus GPIO ont la bande passante nécessaire (NMEA en UART à 9600/38400 bauds, I2C à 400 kHz).

---

## 2026-04-24 — Accéléromètres simples (ADXL345 ×2) plutôt que IMU 9DOF

**Contexte** : besoin de mesurer l'inclinaison du tube (zéro ALT, butées) et la planéité de la monture (mise à niveau).

**Décision** : 2 × ADXL345 (I2C, ~3 € pièce). Pas d'IMU 9DOF (MPU6050/BNO055).

**Rationale** : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas de fusion de capteurs ni cap tilt-compensé nécessaires (le plate solve v0.5 prendra le relais pour le pointage précis). Les 2 ADXL345 cohabitent sur I2C1 grâce à la pin SDO (`0x53` tube, `0x1D` monture). Précision < 0.5° brute, < 0.1° après calibration.

---

## 2026-04-24 — App Flutter native (pas PWA)

**Décision** : app Flutter native compilée pour Android (et iOS plus tard), pas une PWA servie par le Pi.

**Rationale** : performance et sensation native, accès USB-debug pour smoke test, pas besoin d'un serveur web servant l'app sur le Pi (la complexité d'un setup PWA n'apporte rien de plus qu'un APK installé).

---

## 2026-04-24 — Pattern BLoC pour Flutter

**Décision** : `flutter_bloc` (pattern BLoC, MVVM-like) avec `equatable` pour les états.

**Rationale** : pattern le plus idiomatique pour une app Flutter à état partagé entre écrans (status système global, thème, alignement). Documentation officielle dense (`docs.flutter.dev`), testable via `bloc_test`. Alternatives écartées : Provider seul (pas assez structuré), Riverpod (overkill ici, communauté plus jeune), Redux (verbeux pour le besoin).

---

## 2026-04-29 — Catalogue + calculs astro côté backend

**Décision** : Pi sert le catalogue (Messier, planètes, étoiles brillantes) via REST. Calculs astro (Alt/Az, éphémérides) faits en Python avec `skyfield` / `astropy`. App = client de présentation.

**Rationale** : le Pi a déjà l'heure GPS exacte + la position. Les libs Python d'astro sont matures et précises. Centraliser la logique astro dès maintenant prépare le night planner et le filtrage par visibilité (v0.4+). Inconvénient identifié pour le night planner offline : traité plus tard via pattern snapshot/cache (cf. backlog).

---

## 2026-04-29 — Hub central comme nouveau landing post-Splash

**Décision** : à partir de v0.3, l'app n'arrive plus directement sur le HomeScreen manuel. Splash → Hub agrégateur → écran feature.

**Rationale** : permet d'agréger Manuel / GoTo / Catalogues / Status / Setup / Night planner au fur et à mesure, sans charger un écran feature avec des boutons d'autres modes. Le hub n'affiche que les entrées actives — les autres apparaissent quand elles ont un contenu.

---

## 2026-04-29 — AppBar partagée sur tous les écrans

**Décision** : convention de template — tous les écrans Flutter affichent une AppBar commune contenant pastille de status global + toggle jour/nuit + bouton reconnect conditionnel.

**Rationale** : l'utilisateur veut garder l'état système et le toggle thème accessibles en permanence (utilisation terrain de nuit). Évite la duplication par écran et garantit la cohérence visuelle HUD.

---

## 2026-04-30 — Setup devient v0.2 (avant l'alignement)

**Contexte** : le brainstorm initial visait v0.2 = mise en station 3 étoiles + GoTo + catalogue minimal. En détaillant les prérequis, il est apparu qu'on ne peut pas faire un alignement sérieux sans : compass calibré, ADXL345 calibré, courses définies, backlash compensé.

**Décision** : Setup devient le milestone v0.2. La mise en station + GoTo passe en v0.3. Le décalage propage sur tout le reste.

**Rationale** : shipper un alignement sans calibration capteurs serait shipper une feature qui ne marche pas en pratique. Mieux vaut un Setup robuste qui débloque l'alignement, que l'inverse.

---

## 2026-05-01 — Pilotage monture via INDI (drop nexstarpy)

**Contexte** : v0.1 utilise `nexstarpy` 0.1.0 (HC-only, mono-auteur, pas d'AUX). v0.2 a besoin de backlash + cordwrap + sync RA/Dec + `is_aligned` + `goto_in_progress`, qui passent par les commandes AUX (pass-through `'P'`/0x50 du HC). v0.5 amène les caméras → INDI sera de toute façon dans la stack pour le plate solving / framing / capture.

**Décision** : pivoter dès v0.2 sur l'écosystème **INDI** — `indiserver` + driver `indi_celestron_aux` (BETA, repo `indi-3rdparty`) + client Python `pyindi-client`. Le nouveau backend wrappe INDI derrière la même interface `MountAdapter` (REST `/slew`, `/stop`, `/tracking`, `/goto` inchangés côté Flutter).

**Rationale** : tout code écrit autour de `nexstarpy` serait jeté à v0.5 — coût zéro de jeter maintenant vs cycle complet plus tard. INDI couvre 6 des 7 besoins v0.2/v0.3 nativement (vérifié par lecture source). Manque uniquement le mount-axis backlash (opcodes `MC_*_BACKLASH` non câblés dans `auxproto.h`) → patch upstream estimé ~70 lignes C++. Spec : [`docs/superpowers/specs/2026-05-01-mount-indi-design.md`](../superpowers/specs/2026-05-01-mount-indi-design.md). Doc onboarding : [`docs/technical/indi-reference.md`](../technical/indi-reference.md).

---

## 2026-05-01 — Câblage monture via dongle CP2102 USB-TTL 5V (port HC RJ12)

**Contexte** : la monture s'attache au Pi par le port HC en RJ12 (TTL 5V). Le DroTek GPS occupe déjà l'UART matériel (PL011, `ttyAMA0`) en GPIO. Pas de level shifter ni de câble Celestron #93920 dans le tiroir au moment de la décision.

**Décision** : interfacer le HC par un dongle USB-TTL **CP2102** (sélecteur sur **5V**) branché côté Pi sur un port USB libre, et côté HC sur un bornier maison RJ12 6P6C. Le HC apparaît en `/dev/ttyUSB0`. Les broches RX/TX/GND sont câblées 3↔TX-dongle / 4↔RX-dongle / 5↔GND ; broche 2 **non connectée** (peut exposer +12 V selon HC, à valider au multimètre).

**Rationale** : (1) zéro conflit avec le GPS (qui garde l'UART matériel pour lui), (2) coût équivalent à un level shifter + câble UART, (3) compatible avec le standard INDI (`/dev/ttyUSBx`), (4) chaud-débranchable contrairement au GPIO. Câblage et avertissements : [`docs/technical/hardware.md`](../technical/hardware.md#monture--usb-série-via-dongle-cp2102-port-hc).

---

## 2026-05-04 — Stack INDI installée via repo Astroberry Debian Trixie arm64

**Contexte** : exécution de la Task 0 du plan migration INDI (Session 15). Trois sources possibles pour `libindi` 2.x + `indi_celestron_aux` sur Pi 3 B+ Debian Trixie arm64 : (1) compilation source `indi-3rdparty`, (2) PPA officielle `ppa:mutlaqja/ppa`, (3) repo Astroberry. La compilation source à `-j3 / -j4` finit par tourner mais reste laborieuse sur 1 GB RAM même avec swap, et n'apporte rien tant qu'on ne patche pas le driver. La PPA mutlaqja `ppa.launchpadcontent.net:443` rejette activement les TCP depuis ce Pi (reset 47 ms IPv4 et IPv6, le reste du net OK) — pas exploitable aujourd'hui. Le repo Astroberry "old" `astroberry.io/repo/` est mort (404). Le repo "new" `astroberry.io/debian/` est documenté sur `indilib.org/download/raspberry-pi.html`, actif, signé GPG, et fournit `libindi 2.2.0` + `indi-celestronaux 1.5` + `indi-gpsd 0.6` pour Trixie arm64.

**Décision** : utiliser le repo Astroberry `https://astroberry.io/debian/` (suite `trixie`, composant `main`, archi `arm64`) comme source apt pour les paquets INDI sur le Pi. Source au format deb822 dans `/etc/apt/sources.list.d/astroberry.sources`, clé GPG dans `/etc/apt/keyrings/astroberry.gpg`. Paquets installés : `indi-bin`, `indi-celestronaux`, `indi-gpsd`, `libindi-dev`.

**Rationale** : (1) install en < 2 min, 0 conflit avec Debian Trixie (0 `apt-pin` requis, seules deps Debian tirées : `libxisf0`, `librtlsdr0`), (2) versions cohérentes avec la cible (`libindi 2.2.0`, plus récente que la 1.9.9 de Trixie qui ne contient pas le driver AUX), (3) repo restreint au scope INDI (pas tout l'écosystème astrophoto Astroberry, donc empreinte raisonnable malgré le RAM 1 GB), (4) déblocage du chantier migration sans dépendre de la PPA inaccessible. Compilation source restera l'option de fallback **uniquement** si on doit patcher upstream (typiquement les opcodes `MC_*_BACKLASH` mount-axis manquants dans `auxproto.h`). Détail repro Session 15 du journal : `docs/project/journal.md`.

---

## 2026-04-30 — Arborescence de docs en 3 vues

**Décision** : `docs/INDEX.md` référence trois vues — `technical/`, `project/`, `product/`. Chaque vue a un `README.md` index, et regroupe des docs courts et ciblés (1 sujet = 1 fichier).

**Rationale** : faciliter la navigation et minimiser le contexte chargé à chaque session. Un long document monolithique est dur à maintenir et oblige à charger trop de contexte. Trois angles de lecture (technique / projet / produit) couvrent les besoins du dev hybride humain + IA.
