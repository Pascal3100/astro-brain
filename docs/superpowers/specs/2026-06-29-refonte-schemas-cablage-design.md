# Refonte des schémas de câblage HTML — design

**Date** : 2026-06-29
**Statut** : design validé, prêt pour plan d'implémentation

## Contexte

Le fil matériel « liaison monture / bus AUX » (Macro 1) a produit **7 pages HTML** dans `docs/technical/`, accumulées au fil de l'investigation (diode 1N4007, Nano, 2× BC547, buffer 4093, comparateur LM2902…). Plusieurs décrivent des **voies mortes**, aucune n'offre de vue d'ensemble, et le câblage va de toute façon changer : on **pivote le TX vers un buffer tri-state 74AHCT125** (reproduction du schéma éprouvé g7ltt / Mark Lord).

**Objectif** : repartir de zéro avec un jeu de pages propre — une **page globale** (schéma bloc du système complet) qui pointe vers **4 pages sous-ensemble** (alimentation, capteurs Pi, pont ESP32, interface bus AUX). Chaque page ne montre que des **schémas fonctionnels et de câblage**, avec un **badge de statut** (validé / à valider) puisque le jeu mélange du prouvé et du planifié.

### Pages supprimées (7)

`astro-nano-interface.html`, `aux-montage-complet.html`, `aux-montage-lm2902.html`, `aux-rx-buffer-4093.html`, `aux-rx-buffer-4093-atelier.html`, `aux-single-wire-cablage.html`, `esp32-aux-bridge.html`.

Le contenu historique de ces pages reste tracé dans le journal et son archive `2026-06-bus-aux.md` — on ne perd pas la trace de décision, on retire seulement les pages de câblage périmées.

## Architecture matérielle de référence (vérité terrain)

### Alimentation — 3 sources distinctes

- **Pi** : adaptateur secteur **220 V → 5 V / 2,5 A** dédié (alimente le Pi seul).
- **Rail 5 V** : convertisseur **12 V → 5 V** dédié → alimente **tout le 5 V** du système : ESP32, interface AUX (LM2902 + 74AHCT125), pull-ups, **VCC des capteurs**. *Aucun 5 V ne sort du Pi.*
- **3,3 V** : fourni par le Pi (logique GPIO/I2C/UART côté Pi uniquement).
- **Masses communes obligatoires** : Pi GND ↔ rail 5 V GND ↔ GND bus AUX (broche 5 RJ-12). Point sensible — un domaine de masse séparé était suspecté dans le blocage S28.

### Capteurs Pi (GPIO) — validé

- **GPS DroTek Ublox M8N** — UART0 : `GPIO14 (TXD0) → GPS RX`, `GPIO15 (RXD0) ← GPS TX`. VCC ← rail 5 V (module à LDO intégré, logique 3,3 V), GND commun.
- **I2C1** (`GPIO2 SDA`, `GPIO3 SCL`) :
  - LIS3MDL (compass) `0x1E`
  - ADXL345 tube `0x53` (SDO = VCC)
  - ADXL345 monture `0x1D` (SDO = GND)
- VCC capteurs ← **rail 5 V** (modules à régulateur intégré, I2C 3,3 V-compatible avec le Pi). À vérifier que chaque breakout accepte bien 5 V en VCC avant branchement.

### Pont ESP32 ↔ bus AUX — validé (pont/RX/WiFi), à valider (OE TX)

- ESP32 DevKit (puce CP2102), alimenté par le **rail 5 V** (VIN).
- **WiFi STA**, IP fixe `192.168.1.200`, repli AP au boot ; **serveur TCP port 2000** (le driver `indi_celestron_aux` se connecte en mode Network).
- `Serial2` **19200 8N2** : `GPIO16` (RX, depuis le LM2902) / `GPIO17` (TX, vers l'entrée du 74AHCT125).
- `GPIO32` = **TX-enable** → pilote le `/OE` du 74AHCT125 (LOW pendant l'émission, HIGH au repos → buffer en Hi-Z, le LM2902 lit). Reproduit le timing `BUSYOUT` de la réf g7ltt, ici en **OE local pur** (pas relié à la ligne BUSY du bus).
- **Firmware** : relais bidirectionnel TCP↔UART ; **suppression d'écho** half-duplex (comparaison au dernier paquet émis) ; **fenêtre de turnaround** (assert `/OE` LOW avant TX, release HIGH après) ; robustesse WiFi (reconnect événementiel, watchdog `ESP.restart()` >30 s, `setNoDelay`).

### Interface bus AUX (single-wire) — RX validé, TX à valider

Brochage **RJ-12 6P6C** (port HAND CONTROL / AUX) :

| Broche | Fonction | Câblage |
|---|---|---|
| 3 | **+12 V** | ⚠️ **NE JAMAIS connecter** |
| 4 | **DATA** (single-wire bidirectionnel) | RX (LM2902) **et** TX (74AHCT125) |
| 5 | **GND** | masse commune |
| 6 | SELECT / BUSY | **non câblée** (mono-maître) |

**RX — comparateur LM2902 (PROUVÉ S33).** Lecture haute-Z qui *renifle* le bus sans le charger et bascule sur un seuil bas (insensible aux fronts montants lents du bus, signature qui aveuglait le 4093) :
- `DATA → diviseur 1M / 1M → entrée +`
- `Vréf ≈ 0,9 V` via `10k / 2k2 → entrée −`
- `sortie ampli (0/5 V) → diviseur 1k / 4k7 → ~2,9 V → GPIO16`
- découplage **100 nF** au boîtier.

**TX — buffer tri-state 74AHCT125 (ÉPROUVÉ g7ltt, à valider chez nous).** Drive **actif push-pull** (HIGH *et* LOW) pendant la fenêtre TX → fronts rapides dans les deux sens (corrige le TX round-trip négatif S33, dû aux fronts montants lents de l'open-collector BC547) :
- `GPIO17 (UART TX) → pin 2 (1A, entrée gate 1)`
- `GPIO32 (TX-enable) → pin 1 (1/OE, actif bas)`
- `pin 3 (1Y) → 470 Ω → DATA (broche 4)`
- `VCC pin 14 = rail 5 V`, `GND pin 7`, découplage **100 nF** au boîtier.
- gates inutilisées (2-3-4) : `/OE → VCC` (désactivées), entrées `A → GND`.

**Écart assumé vs réf** : la réf g7ltt câble aussi la ligne BUSY (broche 6, `GPIO32→BUSY` + `GPIO35←BUSYIN`) pour l'arbitrage multi-maître. Inutile chez nous (raquette débranchée = maître unique). On reproduit uniquement le **timing OE**, en local.

**Pourquoi deux composants et pas le 74AHCT125 seul** : sur notre NexStar SLT, le pull-up monture est très faible (~139 kΩ) → fronts montants lents → un buffer logique à seuil figé (4093, et par extension le 74AHCT125 en entrée) est aveuglé (prouvé S30→S32). Seul un comparateur haute-Z à seuil réglable bas (LM2902) lit le bus de façon fiable (prouvé S33). Le 74AHCT125 n'apporte sa valeur qu'en **émission** (drive actif), ce que le LM2902 ne peut pas faire. Rôles complémentaires : LM2902 = oreilles, 74AHCT125 = bouche.

## Pages livrables

Toutes : **HTML autonomes** (SVG inline, zéro dépendance externe), **thème sombre fixe** (reprise du squelette CSS de `aux-montage-lm2902.html`, la convention la plus récente — pas de toggle jour/nuit), **badge de statut** en tête (✅ validé / 🔬 à valider), lien retour vers la page globale.

| Fichier | Rôle | Statut |
|---|---|---|
| `cablage-global.html` | Schéma bloc du système : 3 alims, Pi↔capteurs, Pi↔WiFi↔ESP32↔bus AUX↔monture, masses communes. Blocs cliquables vers les pages sous-ensemble. Légende des badges. | mixte |
| `cablage-alimentation.html` | Les 3 sources, ce que chacune alimente, masses communes, découplages. | ✅ validé |
| `cablage-capteurs-pi.html` | Brochage header GPIO, GPS UART0, I2C1 (compass + 2× ADXL345 avec adresses/SDO), VCC depuis le rail 5 V. | ✅ validé |
| `cablage-pont-esp32.html` | ESP32 STA/TCP:2000, `Serial2` GPIO16/17 + GPIO32 OE, rôles firmware (relais, écho, turnaround, robustesse WiFi). | ✅ validé (pont) · 🔬 à valider (OE) |
| `cablage-interface-aux.html` | RJ-12, RX LM2902 (valeurs complètes), TX 74AHCT125 (brochage DIP-14 + 470 Ω + /OE), BUSY non câblée. | ✅ RX validé · 🔬 TX à valider |

## Mises à jour de doc associées (cohérence)

- **`docs/technical/README.md`** : remplacer la section « Schémas de câblage (HTML) » (qui indexe les 7 anciens) par l'index des 5 nouvelles pages, page globale en tête.
- **`docs/technical/hardware.md`** : synchroniser — c'est la source markdown et elle est désormais contredite. À corriger : (1) alim « 12 V batterie → buck 5 V/3 A vers Pi » → topologie 3 sources ; (2) VCC capteurs « Pin 2 (5V) du Pi » → rail 5 V ; (3) interface AUX « 2× BC547 » → RX LM2902 + TX 74AHCT125 ; (4) récap fils. Renvoyer vers les pages HTML pour le détail visuel.
- **`docs/project/journal.md`** : consigner la session (refonte schémas + pivot TX 74AHCT125 + sync hardware.md).

## Hors périmètre (YAGNI)

- Pas de PCB / routage (les pages restent au niveau schéma + netlist).
- Pas de câblage de la ligne BUSY (broche 6) tant qu'on est mono-maître.
- Pas de modification firmware dans cette tâche (la doc décrit le rôle attendu ; le code firmware vit dans `firmware/` et suivra à la validation matérielle du 74AHCT125).
- Pas d'ADR : le pivot TX prolonge le fil ESP32 déjà tracé, ce n'est pas une décision structurante nouvelle.

## Critères de succès

- Les 7 anciennes HTML sont supprimées ; les 5 nouvelles existent et s'ouvrent correctement (jour/nuit OK, SVG lisibles).
- La page globale lie chaque sous-ensemble ; chaque page sous-ensemble lie le retour global.
- Chaque schéma porte un badge de statut exact (RX = validé, TX = à valider).
- `README.md` indexe les 5 pages ; `hardware.md` ne contredit plus les schémas.
- Toutes les valeurs (résistances, GPIO, adresses I2C, brochages) sont cohérentes entre pages, README et hardware.md.
