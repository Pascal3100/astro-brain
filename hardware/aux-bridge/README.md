# Carte pont AUX — projet KiCad

Carte PCB qui remplace le montage breadboard du pont bus AUX : entrée **RJ-12** (bus AUX de la
monture NexStar SLT) → interface single-wire → **ESP32 enfiché** → WiFi → driver INDI sur le Pi.

**Pont de bus pur** : RX comparateur LM2902 (✓ S33) + TX buffer tri-state 74AHCT125 (✓ S36),
découplage, entrée 5 V.

## Source de vérité

- **Spec / schéma lisible** : [`docs/technical/cablage-carte-aux-pcb.html`](../../docs/technical/cablage-carte-aux-pcb.html)
  (netlist consolidée + BOM + connecteurs + notes fab).
- **Détail par étage** : [`cablage-interface-aux.html`](../../docs/technical/cablage-interface-aux.html)
  · [`cablage-pont-esp32.html`](../../docs/technical/cablage-pont-esp32.html)
  · [`cablage-alimentation.html`](../../docs/technical/cablage-alimentation.html)
- **Contexte matériel** : [`docs/technical/hardware.md`](../../docs/technical/hardware.md).

Le projet KiCad (`.kicad_pro` / `.kicad_sch` / `.kicad_pcb`) est la **source éditable** ;
le HTML reste la spec de référence. Les deux doivent rester cohérents.

## BOM

| Réf | Valeur / composant | Boîtier | Note |
|-----|--------------------|---------|------|
| U1 | LM2902 (quad op-amp) | DIP-14 sur support | seul l'ampli A utilisé |
| U2 | 74AHCT125 (quad tri-state) | DIP-14 sur support | seul le gate 1 utilisé |
| — | ESP32 DevKit (WROOM) | 2× barrette femelle | **enfiché** — mesurer nb pins + pas inter-rangées |
| R1, R2 | 1 MΩ | THT 1/4 W | diviseur d'entrée ÷2 |
| R3 | 10 kΩ | THT 1/4 W | haut diviseur Vréf |
| R4 | 2,2 kΩ | THT 1/4 W | bas diviseur Vréf |
| R5 | 1 kΩ | THT 1/4 W | haut diviseur sortie RX |
| R6 | 4,7 kΩ | THT 1/4 W | bas diviseur sortie RX |
| R7 | 470 Ω | THT 1/4 W | série 1Y → DATA |
| C1, C2 | 100 nF céramique | THT X7R | découplage, 1 par CI |
| C3 | 10 µF | céram. / tantale | réservoir près VIN ESP32 |
| J1 | RJ-12 6P6C | jack PCB traversant | vers HAND CONTROL monture |
| J2 | bornier 2 pts | screw / KF2510 | entrée 5 V (+ / GND) |
| J3 | barrette 3 pts | 1×03 pas 2,54 (ou toron soudé) | liaison série vers le Pi (TX / RX / GND) |

## Netlist

| Net | Nœuds |
|-----|-------|
| `+5V` | J2.1 · U1.4 · U2.14 · U2.4/10/13 · ESP32.VIN · R3(haut) · C1+ C2+ C3+ |
| `GND` | J2.2 · J1.5 · U1.11 · U2.7 · U2.5/9/12 · ESP32.GND · J3.3 · R2 R4 R6(bas) · C1– C2– C3– · réf. amplis inutilisés |
| `DATA` | J1.4 · R1(haut) · R7 470Ω → U2.3 (1Y) |
| `IN+` | R1(bas) · R2(haut) · U1.3 (IN1+) |
| `VREF` | R3(bas) · R4(haut) · U1.2 (IN1−) |
| `RX` | U1.1 (OUT1) → R5 1k → nœud · R6 4k7(bas→GND) · ESP32.GPIO16 |
| `TX_DATA` | ESP32.GPIO17 · U2.2 (1A) |
| `TX_OE` | ESP32.GPIO32 · U2.1 (1/OE, actif bas) |
| `PI_TX` | J3.1 (← Pi GPIO14/TXD0, broche 8) · ESP32.GPIO25 |
| `PI_RX` | ESP32.GPIO26 · J3.2 (→ Pi GPIO15/RXD0, broche 10) |

Rappel LM2902 (DIP-14) : `1`=OUT1, `2`=IN1−, `3`=IN1+, `4`=V+, `11`=GND.

## Netlist-as-code → import Pcbnew

La carte est décrite en Python dans [`gen_netlist.py`](gen_netlist.py) (composants + nets),
qui émet [`aux-bridge.net`](aux-bridge.net) — un netlist KiCad importable directement dans Pcbnew.
C'est la **source éditable** du board : on modifie le `.py`, on régénère, on ré-importe.

```bash
python3 gen_netlist.py        # régénère aux-bridge.net (16 composants, 15 nets)
```

**Import dans KiCad (snap) :**

1. Lancer Pcbnew : `kicad.pcbnew` (éditeur de circuit imprimé, en standalone).
2. `Fichier → Importer → Netlist…` → choisir `aux-bridge.net`.
3. Les empreintes arrivent empilées à l'origine avec le **chevelu** (airwires) → placer puis router.

Détails : les empreintes sont toutes résolues **sauf `A1` (ESP32)** — voir ci-dessous.
Les pins inutilisés sont déjà gérés (amplis LM2902 en suiveurs, `/OE`/`A` des gates tirés,
sorties `Y` volontairement libres, `J1.3` +12 V non connectée).

### A1 — ESP32 : empreinte à créer

Aucune empreinte DevKitC en lib stock. Dans le netlist, `A1` a une **empreinte vide** et
ses pins sont **nommés par fonction** (`VIN`, `GND`, `IO16`, `IO17`, `IO32`). Il faut créer une
empreinte (2 rangées de pads au **pas mesuré sur ta carte**) dont les pads portent ces noms →
le chevelu se résoudra alors tout seul. À l'import, Pcbnew signalera « A1 sans empreinte » : normal.

> ⚠️ Le netlist n'a **pas** pu être vérifié par import headless (pas de commande `kicad-cli`
> pour ça) — sa **structure S-expr est validée** (parse OK) et toutes les empreintes/pads
> référencés existent. Contrôle visuel à l'import.

## Correspondance symboles KiCad

| Réf | Symbole | Librairie |
|-----|---------|-----------|
| U1 | `LM2902` | `Amplifier_Operational` |
| U2 | `74AHCT125` | `74xx` |
| ESP32 | `ESP32-DEVKITC-V4` | `MCU_Module` |
| J1 | jack modulaire 6P6C | `Connector` |
| J2 | bornier 2 pts | `Connector_Generic` |
| J3 | barrette 3 pts | `Connector_Generic` |
| R*, C* | `R`, `C` | `Device` |

## Pièges à la saisie (ERC)

1. **`PWR_FLAG`** sur `+5V` **et** `GND`, sinon « power input not driven ».
2. **Unités inutilisées à placer + câbler** :
   - LM2902 amplis B/C/D en suiveurs : `IN+ → GND`, `OUT ↔ IN−`
     (B : `5→GND`, `7↔6` · C : `10→GND`, `8↔9` · D : `12→GND`, `14↔13`).
   - 74AHCT125 gates 2/3/4 : `/OE (4·10·13) → VCC`, `A (5·9·12) → GND`, sorties `Y (6·8·11)` en l'air.
3. **Aucun net 3,3 V** sur cette carte : la liaison série vers le Pi est en 3,3 V des deux côtés (GPIO ESP32 ↔ GPIO Pi), donc directe, sans adaptateur de niveau ni rail dédié.

## Sécurité — RJ-12 broche 3 (+12 V)

⚠️ **Pad totalement isolé, aucune piste, aucun cuivre proche**, sérigraphie « +12 V — NE PAS CONNECTER ».
Repérer l'orientation au multimètre (monture allumée) avant tout branchement — un câble RJ-12
*reversed* inverse l'ordre des broches. Un contact +12 V grille U1/U2/ESP32.

## État

- [x] Spec / netlist consolidée (HTML)
- [x] Netlist-as-code (`gen_netlist.py` → `aux-bridge.net`, structure validée)
- [ ] Empreinte ESP32 DevKitC à créer (pads `VIN/GND/IO16/IO17/IO32`, pas mesuré)
- [ ] Import netlist dans Pcbnew → placement des empreintes
- [ ] Routage 2 couches + plan de masse + isolement pad +12 V
- [ ] Export Gerbers → commande JLCPCB (~25 € les 5)
