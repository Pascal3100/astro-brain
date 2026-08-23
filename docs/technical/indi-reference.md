# Référence INDI — Astro-Brain

Onboarding ciblé pour pilotage de la monture Celestron SLT depuis FastAPI via INDI. Pas une encyclopédie : couvre l'essentiel pour les 7 besoins Macros 2/3 + l'opérationnel Pi.

## TL;DR — Couverture des 7 besoins par `indi_celestron_aux`

| # | Besoin | Property INDI | Couverture |
|---|---|---|---|
| 1 | Backlash AZ/ALT × pos/neg (4 valeurs) | — | ❌ absent |
| 2 | Cordwrap on/off + position | `CORDWRAP` (switch) + `CORDWRAP_POS` (switch 4 cardinaux) ; 24-bit possible en bypass via `MC_SET_CORDWRAP_POS/0x3a` | ⚠️ partiel (UI 4 directions) |
| 3 | Sync RA/Dec | `EQUATORIAL_EOD_COORD` + `ON_COORD_SET=SYNC`, méthode `Sync()` à `celestronaux.cpp:1878` | ✅ complet |
| 4 | Set time + set location | `TIME_UTC` (text) + `GEOGRAPHIC_COORD` (number), capabilities `HAS_TIME`/`HAS_LOCATION` | ✅ complet (location pushé, time stocké) |
| 5 | Tracking on/off + mode | `TELESCOPE_TRACK_STATE` + `TELESCOPE_TRACK_MODE` (Sidereal/Solar/Lunar/Custom) | ✅ complet |
| 6 | Slew manuel joystick | `TELESCOPE_MOTION_NS` + `TELESCOPE_MOTION_WE` + `TELESCOPE_SLEW_RATE` (8 niveaux) | ✅ complet |
| 7 | Is aligned (état lisible) | proxy via Alignment Subsystem (`ALIGNMENT_SUBSYSTEM_ACTIVE`, taille `GetAlignmentDatabase()`) ; pas de booléen direct | ⚠️ partiel (proxy) |

Bonus : goto in progress = `EqNP.state == IPS_BUSY` (cf. `celestronaux.cpp:2019`). Echo/heartbeat = la connexion TCP elle-même + `serverConnected/Disconnected` callbacks pyindi.

**Verdict** : pivot INDI viable avec un seul vrai blocage (backlash). Voir `docs/project/decisions.md` pour la décision et le contournement.

## 1. Architecture INDI

INDI = trois processus distincts, communication via XML sur socket TCP.

```
Client(s) (pyindi-client / EKOS) <--TCP 7624 (XML)--> indiserver <--stdin/stdout (XML)--> driver(s) C++
                                                                                       └── matériel (USB/série/réseau)
```

- **`indiserver`** : binaire C++ permanent, multiplexeur. Lance et fork chaque driver demandé sur sa ligne de commande (`indiserver indi_celestron_aux indi_simulator_focuser`). Écoute par défaut sur `0.0.0.0:7624`. Empreinte mémoire ~50–80 MB RSS.
- **Driver** : binaire C++ qui parle un protocole matériel (ici série/AUX vers la monture). Expose un état via le **modèle des Properties**.
- **Client** : nous (FastAPI + pyindi-client). Découvre les devices et leurs properties, lit/écrit, écoute les updates.

### Modèle des Properties

Une property est un **vecteur typé nommé** attaché à un device. Quatre types :

| Type | Élément | Exemple |
|---|---|---|
| `Number` | flottant + format | `EQUATORIAL_EOD_COORD` { RA, DEC } |
| `Switch` | ISS_ON / ISS_OFF, règle 1OFMANY / ATMOST1 / NOFMANY | `ON_COORD_SET` { SLEW, TRACK, SYNC } |
| `Text` | string | `DEVICE_PORT` { PORT } |
| `Light` | indicateur read-only IPS_OK/BUSY/ALERT/IDLE | `TELESCOPE_TRACK_STATE` |

Un vecteur a un **nom** (ex: `EQUATORIAL_EOD_COORD`), des **éléments** nommés, une **permission** (RO/RW/WO), un **état** (IDLE/OK/BUSY/ALERT). Côté code on lit toujours `vecteur[élément]`. On modifie en local puis on appelle `sendNewProperty()` ; le driver répond async par un `updateProperty()`.

Les **BLOB** sont un cinquième type pour binaire (FITS) — pas pertinent Macros 2/3, utile Macro 5 pour les caméras.

## 2. pyindi-client : connexion et I/O

Install Pi : `sudo apt install python3-indi-client` (paquet PPA INDI). Pas de wheel pip propre — c'est un binding SWIG sur libindi. En dev workstation, mocker.

```python
import PyIndi, time

class AstroIndi(PyIndi.BaseClient):
    def serverConnected(self):  print("indiserver up")
    def serverDisconnected(self, code): print(f"indiserver down: {code}")
    def newDevice(self, dev):   print(f"device: {dev.getDeviceName()}")
    def updateProperty(self, prop):  # callback async sur tout changement
        print(f"prop changed: {prop.getName()}  state={prop.getStateAsString()}")

client = AstroIndi()
client.setServer("localhost", 7624)
client.connectServer()
time.sleep(1)
mount = client.getDevice("Celestron AUX")  # nom du device défini par le driver
```

Lecture / écriture d'un Number (ex: pousser des coords EOD) :

```python
eq = mount.getNumber("EQUATORIAL_EOD_COORD")  # PropertyNumber
eq[0].setValue(ra_hours); eq[1].setValue(dec_deg)
client.sendNewProperty(eq)
```

Toggle d'un Switch (ex: tracking ON) :

```python
ts = mount.getSwitch("TELESCOPE_TRACK_STATE")
ts[0].setState(PyIndi.ISS_ON);  ts[1].setState(PyIndi.ISS_OFF)  # TRACK_ON / TRACK_OFF
client.sendNewProperty(ts)
```

Pour FastAPI : un seul `BaseClient` long-vécu en singleton, expose une queue async vers SSE pour relayer les `updateProperty()` au front.

## 3. Drivers Celestron — config et properties principales

Deux candidats :

- **`indi_celestron_aux`** (3rdparty, BETA) : parle directement au bus AUX (PC/AUX port ou HC en pass-through). Cordwrap natif. **Recommandé pour SLT.**
- **`indi_celestron_gps`** (in-tree) : driver historique HC-only. Backup. Pas de cordwrap, pas de backlash mount-axis.

Config minimale AUX (à pousser dans `CONNECTION` + `DEVICE_PORT` + `PORT_TYPE`) : port `/dev/ttyUSB0` ou `/dev/ttyAMA0`, **baud 19200 par défaut** (cf. `celestronaux.cpp:489`, `serialConnection->setDefaultBaudRate(B_19200)`), `PORT_TYPE=PORT_AUX_PC` si câble droit DB-9 sur PC port AUX, `PORT_TYPE=PORT_HC_USB` si pass-through par le HC en USB. Le SLT est explicitement reconnu (`MountVersion::SLT_Nexstar = 0x0783` à `celestronaux.h:102`). Capabilities advertised : `TELESCOPE_CAN_PARK | CAN_SYNC | CAN_GOTO | CAN_ABORT | HAS_TIME | HAS_LOCATION | CAN_CONTROL_TRACK | HAS_TRACK_MODE | HAS_TRACK_RATE`, `nSlewRate=8` (`celestronaux.cpp:72-81`).

### Properties pertinentes (héritées d'`INDI::Telescope` sauf indication)

| Vecteur | Type | Éléments | Notes |
|---|---|---|---|
| `EQUATORIAL_EOD_COORD` | Number RW | `RA`, `DEC` | hours / deg JNow. Set = goto/sync selon `ON_COORD_SET`. |
| `ON_COORD_SET` | Switch RW (1OFMANY) | `SLEW`, `TRACK`, `SYNC` | mode utilisé au prochain set d'EOD_COORD. |
| `TELESCOPE_TRACK_STATE` | Switch RW | `TRACK_ON`, `TRACK_OFF` | engage/désengage tracking. |
| `TELESCOPE_TRACK_MODE` | Switch RW | `TRACK_SIDEREAL`, `TRACK_SOLAR`, `TRACK_LUNAR`, `TRACK_CUSTOM` | AUX expose aussi un mode Alt-Az interne. |
| `TELESCOPE_MOTION_NS` | Switch RW | `MOTION_NORTH`, `MOTION_SOUTH` | joystick : ON démarre, OFF stoppe. |
| `TELESCOPE_MOTION_WE` | Switch RW | `MOTION_WEST`, `MOTION_EAST` | idem. |
| `TELESCOPE_SLEW_RATE` | Switch RW (1OFMANY) | `1x` … `8x` (8 niveaux générés par la base class quand `nSlewRate=8`) | la valeur sélectionnée est lue dans `MoveNS`/`MoveWE` (`celestronaux.cpp:1344, 1363`) et passée à `slewByRate(axis, signed_rate)`. Plus fin que les 4 niveaux INDI standards. |
| `TELESCOPE_ABORT_MOTION` | Switch RW | `ABORT_MOTION` | stop net. |
| `TIME_UTC` | Text RW | `UTC`, `OFFSET` | push UTC ISO + offset h. AUX advertise `TELESCOPE_HAS_TIME` mais **n'override pas `updateTime()`** — la valeur est stockée par la base class (`inditelescope.cpp:1727`) et sert aux calculs alignment/coords côté driver, pas pushée vers la monture (le SLT n'a pas de RTC accessible via AUX). Suffisant pour notre besoin : le Pi a l'heure GPS. |
| `GEOGRAPHIC_COORD` | Number RW | `LAT`, `LONG`, `ELEV` | push lat/lon depuis GPS DroTek. AUX override `updateLocation()` à `celestronaux.cpp:2348` ; il met à jour le subsystem alignment + sync cordwrap pos. |
| `CORDWRAP` (AUX only) | Switch RW (1OFMANY) | `INDI_ENABLED`, `INDI_DISABLED` | cordwrap on/off (`celestronaux.cpp:325-328`). Mappe `MC_ENABLE_CORDWRAP/0x38` & `MC_DISABLE_CORDWRAP/0x39`. |
| `CORDWRAP_POS` (AUX only) | Switch RW (1OFMANY) | `CORDWRAP_N`, `_E`, `_S`, `_W` | **position 24-bit côté monture**, mais l'UI INDI ne propose que les 4 cardinaux (`celestronaux.cpp:330-335`). En backend on peut envoyer un steps 24-bit arbitraire via `setCordWrapPosition(uint32_t)` (`celestronaux.h:241`) → `MC_SET_CORDWRAP_POS/0x3a`. |
| `CW_BASE` (AUX only) | Switch RW (1OFMANY) | `CW_BASE_ENC`, `CW_BASE_SKY` | référentiel encodeurs (zéro home) vs alignement (zéro sky). |
| `TELESCOPE_ENCODER_STEPS` (AUX) | Number RW | `AXIS_AZ`, `AXIS_ALT` | 24-bit raw, lecture/écriture directe. |
| `LIMIT_POS` (AUX only) | Number RW | `SLEW_LIMIT_AXIS{1,2}_{MIN,MAX}` | **courses ALT/AZ** en degrés (`celestronaux.cpp:345-349`). Propriété driver disponible ; non consommée côté app depuis le retrait de la feature Courses ALT (2026-07-17, voir ADR). |
| `AXIS1_LIMIT` / `AXIS2_LIMIT` (AUX only) | Switch RW | `INDI_ENABLED`, `INDI_DISABLED` | active/désactive les limites par axe. |
| `HOME` (AUX only) | Switch RW | `AXIS1`, `AXIS2`, `ALL` | seek home (`celestronaux.cpp:316-319`) — homing physique sur SLT à confirmer (capacité hardware). |
| `GUIDE_RATE` | Number RW | `GUIDE_RATE_WE`, `GUIDE_RATE_NS` | 0–1 × sidéral, pour pulse guiding. |
| `TELESCOPE_PIER_SIDE` | Switch RO | `PIER_EAST`, `PIER_WEST` | activé seulement si mount type ≠ ALT_AZ (`celestronaux.cpp:307`) — pas pertinent SLT. |

### Ce qui **n'existe pas** dans les deux drivers

- **Backlash mount-axis (4 valeurs AZ+/-/ALT+/-)** : aucune property côté `indi_celestron_aux` ni `celestrongps`. Vérifié exhaustivement par grep — la seule occurrence "backlash" est `FOCUS_BACKLASH` (focuser uniquement, `celestronaux.cpp:409-412`, `celestrongps.cpp:227-230`). `auxproto.h` (lignes 34-65) liste les opcodes AUX disponibles : `MC_GET_POSITION`, `MC_GOTO_FAST/SLOW`, `MC_SET_POS_GUIDERATE`, `MC_SET_NEG_GUIDERATE`, `MC_*_CORDWRAP`, `MC_SET_AUTOGUIDE_RATE` — **aucun opcode backlash AZ/ALT**. Le NexStar HC protocol expose pourtant ces réglages (commande `0xC4`/`0xC5` ou via `P` passthrough non implémentés ici).
- **`is_aligned` exposé comme property** : pas de Light/Switch dédié. Le statut alignement vit dans le subsystem INDI Alignment (`InitAlignmentProperties` à `celestronaux.cpp:483`) qui expose `ALIGNMENT_SUBSYSTEM_ACTIVE` (switch RW), `ALIGNMENT_POINTSET_*`, `ALIGNMENT_SUBSYSTEM_MATH_PLUGIN_INITIALISE` — utilisables comme proxy mais pas de "is_aligned booléen" simple. Sur le legacy `celestrongps` la commande HC `J` est exécutée en interne C++ sans exposition.

### Pièges identifiés

- Driver AUX status **BETA** (`indi-celestronaux/README.md`, et `ISSUES.md`).
- ⚠️ **`indi_getprop "Device.*"` est une spec invalide** — piège d'outillage, pas de driver (S53). Une spec doit avoir **trois** composants (`device.property.element`) ; avec deux, `indi_getprop` n'affiche pas « rien trouvé » mais **son message d'usage complet** sur stdout. Un `| grep -iE "park|track|abort"` derrière ne matche donc rien, ce qui se lit à tort comme « ces propriétés sont absentes du driver » — conclusion fausse tirée en séance, alors que les 158 propriétés étaient bien là. Motif correct pour énumérer un device : `indi_getprop -t 5 "Celestron AUX.*.*"`.
- ⚠️ **`tcpReadResponse()` retourne toujours `true`** (relu sur les sources, S51). En mode **Network** — le nôtre depuis l'[ADR 2026-07-05](../project/decisions.md) — le driver drain le socket en `MSG_DONTWAIT | MSG_PEEK` puis `return true` inconditionnellement dès que `PortFD > 0` : il ne vérifie **jamais** qu'une réponse est arrivée. Conséquences :
  - `getVersion(AZM) && getVersion(ALT)` est vrai dès que le socket TCP vers le pont ESP32 est ouvert, donc le log `Got response from target ALT or AZM.` **ne prouve rien sur la monture**. C'est un faux positif qui a coûté une demi-session de diagnostic (S51) ; seul un proxy TCP inséré dans le chemin dit la vérité sur ce qui revient.
  - `connect()` réussit et le driver se déclare prêt même avec le chemin de retour du bus AUX totalement mort. Toutes les propriétés alimentées par des réponses restent alors à leur valeur d'init (`Firmware Info.*` = `Unknown`, `TELESCOPE_ENCODER_*` = 0, `HORIZONTAL_COORD` figée) — c'est **là** qu'on lit la panne, pas dans les logs.
  - Asymétrie : `serialReadResponse()` (mode Serial) bloque sur `aux_tty_read` avec `READ_TIMEOUT` et renvoie **`false`** au timeout. La détection ne fonctionne donc qu'en série ; en réseau elle est inopérante.
- **Type de monture : jamais déduit de la monture** (corrige une entrée erronée de ce doc, relue sur les sources en S51). `MountTypeSP` est bien rempli et poussé (`celestronaux.cpp:276-303`), en **`IP_RO`** (`setPermission(IP_RO)`) donc non modifiable côté client. Sa valeur vient de, dans l'ordre : (1) défaut `ALT_AZ`, (2) **le fichier de config sauvegardé du driver** (`IUGetConfigOnSwitchIndex(getDeviceName(), "MOUNT_TYPE", …)`), (3) une heuristique sur le **nom du device** (`CGX`/`CGEM`/`Advanced VX`/`Advanced GT` → `EQ_GEM`, `Wedge` → `EQ_FORK`). `MC_GET_MODEL` ne sert qu'à remplir `m_ModelVersion` (affichage Firmware Info), **pas** le type. Enum : `ALT_AZ = 0, EQ_FORK = 1, EQ_GEM = 2` (`celestronaux.h:496`).
  - ⚠️ **Correction S53** : on a bien `TELESCOPE_MOUNT_TYPE.EQ_GEM = On` sur notre SLT — c'est **reproductible** (le journal S52 concluait à tort au non-reproductible), et c'est **cosmétique**. Cette propriété `IP_RO` n'est qu'un **affichage** ; le comportement est piloté par le membre interne `m_MountType`, et deux signaux comportementaux indépendants prouvent qu'il vaut bien `ALT_AZ` :
    - `TELESCOPE_TRACK_MODE` est **absent** de la liste des propriétés — le driver ne l'expose que pour les montures équatoriales ;
    - `TELESCOPE_PARK_POSITION.PARK_RA/PARK_DEC = 0` — un `EQ_GEM` utiliserait `GEM_HOME`.
  - Conséquence pratique : **aucun correctif requis** avant l'alignement et le GoTo, qui tourneront bien en alt-az. Ne pas partir en chasse au `~/.indi/*_config.xml` sur ce seul affichage — vérifier d'abord les deux discriminants ci-dessus. (Le type gate réellement `SetApproximateMountAlignment`, les track modes, les défauts de park et les tuners PID — mais via `m_MountType`, pas via le switch affiché.)
  - ⚠️ Le binaire installé (`indi-celestronaux 1.5`, paquet Debian) **ne correspond pas** aux sources amont relues : la table `Firmware Info` y expose ses 10 entrées par défaut, là où les sources la redimensionnent aux devices détectés. Tout raisonnement « d'après les sources » sur ce driver doit être confirmé par observation du driver vivant.
- **Angles d'axe bruts** : `TELESCOPE_ENCODER_ANGLES` (`AXIS_AZ` 0→360, `AXIS_ALT` −90→+90, `%.2f`, **`IP_RO`**) et `TELESCOPE_ENCODER_STEPS` (`AXIS_AZ`/`AXIS_ALT`, `IP_RW`) — `celestronaux.cpp:439-447`. C'est la source à lire pour une position dans le **repère monture**, indépendante du modèle d'alignement du driver (utilisée par `MountIndiAdapter.current_position()` pour le wizard 3 étoiles).
- `updateTime()` non override → si on attend que le driver pousse l'heure dans le SLT, il ne le fait pas. Pour un setup type "raquette qui demande date+lieu+heure", c'est nous qui orchestrons (l'INDI ne re-cache rien).
- `CORDWRAP_POS` UI = 4 cardinaux discrets ; pour un cordwrap fin (24-bit) il faut soit étendre le driver, soit envoyer `MC_SET_CORDWRAP_POS` en bypass.

## 4. Notes opérationnelles

- **systemd** : `indiserver` doit tourner en service (pas via SSH). Unit type `simple`, `ExecStart=/usr/bin/indiserver -v indi_celestron_aux`, `Restart=on-failure`. Le `-v` log la verbosité utile pour debug. À placer dans `/etc/systemd/system/indiserver.service`.
- **Port** : 7624 par défaut. Si on veut un client distant (laptop debug), exposer sur le réseau local — sinon `127.0.0.1` only.
- **Devices à charger** : pour Astro-Brain, `indi_celestron_aux` seul en Macros 2/3. Macro 5+ : ajouter caméras INDI (ex: `indi_asi_ccd`) et focuser.
- **Empreinte** : indiserver ~10 MB, chaque driver ~30–50 MB. Confortable sur un Pi 3 B+ avec 1 GB RAM.
- **Hot-reload** : tuer un driver via `indiserver` la-CLI ou redémarrer l'unit. Pas de hot-reload propre client-side.
- **Driver AUX = BETA** (cf. README upstream) : "not for unattended use, no slew limits". À surveiller en session, garder coupe-circuit accessible.

## 5. Ressources consultées

| Source | Type | Utilité |
|---|---|---|
| https://docs.indilib.org/ | officiel | doc protocole, properties, tutorials drivers |
| https://docs.indilib.org/interfaces/telescope-interface.html | officiel | liste des properties standard `INDI::Telescope` |
| https://github.com/indilib/indi/blob/master/drivers/telescope/celestrongps.cpp | source | driver HC, capabilities, properties exposées |
| https://github.com/indilib/indi/blob/master/drivers/telescope/celestrondriver.cpp | source | wrappers HC commandes (J, S, t, w, K, L) |
| https://github.com/indilib/indi-3rdparty/tree/master/indi-celestronaux | source | driver AUX, README, properties cordwrap. **Attention** : le driver AUX n'est **pas** dans `indilib/indi` — toute recherche dans `drivers/telescope/` du repo principal renvoie 404 (piège S51). |
| https://github.com/indilib/indi-3rdparty/blob/master/indi-celestronaux/auxproto.h | source | opcodes AUX (MC_GOTO_FAST, MC_SET_CORDWRAP_POS, etc.) — **confirme absence backlash** |
| https://github.com/indilib/pyindi-client | community | binding Python officiel SWIG |
| https://indilib.org/forum/mounts/13067-on-celestron-avx-and-indi-celestron-aux-driver.html | forum | usage AUX réel, statut beta |
| https://stellarmate.com/devices/mounts/celestron/248-celestron-aux.html | community | doc utilisateur AUX driver |
| https://www.indilib.org/api/classINDI_1_1Telescope.html | officiel | API base class telescope (Move/Sync/Goto/UpdateLocation) |
| https://github.com/MMTObservatory/pyINDI | community | client INDI 100% Python (asyncio), parseur XML maison — alternative à pyindi-client si on veut éviter le binding SWIG. Maintenance modeste mais actif. |
| https://github.com/MMTObservatory/indiclient | community | autre client Python pur (sync), plus ancien. |
| `docs/technical/nexstar-protocol-reference.md` | local | protocole HC NexStar série (référence existante, utile pour la compat backlash si besoin) |
| Doc Paquette AUX (PDF projet) | local | référence opcodes AUX bus interne (à confirmer si elle documente un opcode backlash non implémenté par le driver) |
| `/tmp/indi-research/indi-3rdparty/indi-celestronaux/` | source clonée | driver AUX scanné exhaustivement (cpp 3917 lignes, h 542) |
| `/tmp/indi-research/indi/drivers/telescope/celestrondriver.{h,cpp}` + `celestrongps.cpp` | source clonée | driver legacy HC, 3691 lignes total |
| `/tmp/indi-research/indi-3rdparty/indi-celestronaux/auxproto.h` | source clonée | enum `AUXCommands` (lignes 33-65), confirme **absence** opcodes backlash AZ/ALT |
| `/tmp/indi-research/indi/libs/indibase/inditelescope.{h,cpp}` | source clonée | base class : `TIME_UTC`, `GEOGRAPHIC_COORD`, `ON_COORD_SET`, `TELESCOPE_TRACK_*`, `TELESCOPE_MOTION_*`, `TELESCOPE_SLEW_RATE`, `TELESCOPE_ABORT_MOTION` |
