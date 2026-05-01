# Astro-Brain v0.1 — Design Spec

## Objectif

Contrôler manuellement une monture Celestron depuis un téléphone via un joystick virtuel, avec suivi sidéral et synchronisation GPS automatique. L'app Flutter est l'interface ; le Raspberry Pi est le backend qui pilote la monture.

## Principes directeurs

1. **Le Pi est un backend optionnel** — l'app démarre et reste utilisable même quand le Pi est injoignable. En v0.1 le mode offline est surtout un principe architectural (toutes les fonctionnalités actuelles nécessitent la monture) mais il prépare le terrain pour le planificateur (v0.3+), le catalogue (v0.4) et la séquence d'astrophoto (v0.5), qui doivent rester accessibles sans connexion au Pi.
2. **État déclaratif, commandes impératives** — l'état du système est poussé par le Pi via un flux événementiel (SSE). Les commandes restent en REST synchrone. Le client ne polle pas.
3. **Modèle unifié d'état système** — tous les sous-systèmes (monture, GPS, tracking, réseau, Pi) partagent la même structure et sont agrégés en un état global unique.
4. **Thème nuit protecteur de la vision nocturne** — en mode nuit, aucune couleur bleue ni verte. Toute l'UI passe en teintes rouges.

## Architecture

```
App Flutter (téléphone)
   │
   ├──[Wi-Fi / REST]───▶ POST /slew /stop /tracking
   │                    GET /state (snapshot one-shot)
   │
   └──[Wi-Fi / SSE]────▶ GET /events (flux d'état)
                               │
                               ▼
                    FastAPI (Raspberry Pi 3 B+)
                               │
                               ├── nexstarpy ──[USB-série 9600 baud]──▶ Monture Celestron (port HC)
                               │
                               ├── gpsd ──[USB]──▶ DroTek GPS
                               │
                               ├── /sys/class/net ── wlan0 / hotspot
                               │
                               └── /sys/class/thermal, /proc/loadavg
```

- Pas d'Arduino : le Pi communique directement avec la monture via le port Hand Controller.
- Wi-Fi : le Pi se connecte à la box en dev. Un mode hotspot sera configuré pour le terrain (hors scope v0.1 mais pris en compte dans le modèle d'état via le sous-système `network`).

## Modèle d'état système

### Structure d'un sous-système

```json
{
  "state": "<enum propre au subsystem>",
  "details": { /* données contextuelles, peut être vide */ },
  "since": "2026-04-17T20:31:12Z",
  "message": null
}
```

- `state` : un enum fermé, propre au subsystem
- `details` : objet libre pour les données associées (lat/lon pour GPS, axes actifs pour mount…)
- `since` : horodatage du dernier changement d'état (ISO 8601 UTC)
- `message` : chaîne optionnelle, erreur ou info humaine

### Sous-systèmes v0.1

| Subsystem | Critique ? | États | Détails |
|-----------|-----------|-------|---------|
| `mount` | ✅ oui | `disconnected` · `connecting` · `ready` · `moving` · `error` | `firmware_version` (string), `active_slews` (liste de `{axis, direction, rate}`, 0 à 2 éléments, seulement en état `moving`) |
| `gps` | non | `off` · `no_fix` · `searching` · `fix_2d` · `fix_3d` | `lat`, `lon`, `altitude_m`, `satellites` (int), `hdop` (float) |
| `tracking` | non | `off` · `sidereal` | — (v0.2+ pourra ajouter `lunar`, `solar`) |
| `network` | non | `offline` · `client` · `hotspot` | `ssid`, `ip` |
| `system` | non | `ok` · `warning` · `critical` | `cpu_temp_c` (float), `cpu_load` (float), `uptime_s` (int) |

Seuils du subsystem `system` :
- `warning` si `cpu_temp_c ≥ 70` ou `cpu_load ≥ 1.5`
- `critical` si `cpu_temp_c ≥ 80`

### État agrégé global

```json
{
  "overall": "green",
  "subsystems": {
    "mount": { "state": "ready", "details": {"firmware_version": "11.01"}, "since": "...", "message": null },
    "gps": { "state": "fix_3d", "details": {"lat": 48.8566, "lon": 2.3522, "altitude_m": 45, "satellites": 8, "hdop": 0.9}, "since": "...", "message": null },
    "tracking": { "state": "sidereal", "details": {}, "since": "...", "message": null },
    "network": { "state": "client", "details": {"ssid": "BoxWifi", "ip": "192.168.1.42"}, "since": "...", "message": null },
    "system": { "state": "ok", "details": {"cpu_temp_c": 58.2, "cpu_load": 0.42, "uptime_s": 8120}, "since": "...", "message": null }
  },
  "seq": 142,
  "ts": "2026-04-17T20:31:12Z"
}
```

### Règles d'agrégation de `overall`

Évaluées dans l'ordre, premier match gagne :

1. Un subsystem **critique** en `error` / `disconnected` → **🔴 red**
2. Un subsystem en transition (`connecting`, `searching`) → **🔵 blue** (clignotant dans l'UI)
3. Un subsystem non-critique dégradé (`no_fix`, `warning`, `critical`, `offline`) → **🟠 orange**
4. Sinon → **🟢 green**

Seul `mount` est critique en v0.1 (sans lui, rien ne marche). L'ajout de futurs sous-systèmes critiques (focuseur mécanique moteur, par exemple) sera une décision explicite.

## API

### Endpoints REST (impératif)

| Méthode | Endpoint | Body | Réponse | Rôle |
|---------|----------|------|---------|------|
| GET | `/state` | — | `SystemState` | Snapshot one-shot, utile au démarrage de l'app et pour du debug curl |
| GET | `/events` | — | `text/event-stream` | Flux SSE des changements d'état |
| POST | `/slew` | `{ axis, direction, rate }` | `{ ok: true }` | Démarrer un mouvement sur un axe |
| POST | `/stop` | `{ axis? }` | `{ ok: true }` | Arrêter un mouvement (un axe ou les deux si `axis` omis) |
| POST | `/tracking` | `{ enabled }` | `{ ok: true }` | Activer/désactiver le suivi sidéral |

Paramètres :
- `axis` : `"alt"` ou `"az"`
- `direction` : `"+"` ou `"-"`
- `rate` : entier de 1 à 9 (vitesses fixes NexStar)

### Flux SSE `/events`

Format SSE standard, un événement = un bloc `event:` + `data:` (JSON) :

```
event: snapshot
data: {"overall":"green","subsystems":{...},"seq":42,"ts":"2026-04-17T20:31:12Z"}

event: update
data: {"subsystem":"gps","state":{...},"overall":"green","seq":43,"ts":"2026-04-17T20:31:14Z"}

: ping

```

| Type | Quand | Contenu |
|------|-------|---------|
| `snapshot` | À la connexion, puis toutes les **30 s** (resync de sécurité) | État complet `SystemState` |
| `update` | À chaque changement pertinent | `{ subsystem, state, overall, seq, ts }` |
| `: ping` | Keep-alive toutes les **15 s** | Commentaire SSE (maintient la connexion à travers NAT/proxies) |

- `seq` : compteur monotone croissant. Permet au client de détecter les trous → il peut alors forcer un resync via `GET /state`.
- `ts` : horodatage serveur, utile pour afficher "depuis Xs" dans l'UI.

### Throttling côté serveur

Un changement dans un service interne ≠ un événement SSE. Règles :

- **Transition d'état** (enum qui change) → `update` émis immédiatement.
- **Détails GPS** (lat/lon/sats qui bougent sans changement d'enum) → throttle à **1 Hz maximum**.
- **Métriques system** (temp CPU, load) → échantillonnage toutes les **5 s**.
- **Aucun changement** → rien n'est émis (seuls les pings et resync périodiques).

### Reconnexion côté client

- Une seule connexion SSE permanente, maintenue tant que l'app est au premier plan.
- Sur déconnexion : backoff exponentiel (1 s, 2 s, 4 s, max 10 s).
- À la reconnexion, le serveur envoie automatiquement un nouveau `snapshot` — le client n'a pas de logique spéciale de rattrapage.

## Backend — FastAPI sur Raspberry Pi 3 B+

### Architecture

```
┌─ FastAPI routes ───────────────────────────┐
│  POST /slew /stop /tracking                │
│  GET /state  ·  GET /events (SSE)          │
└──────────┬─────────────────────┬───────────┘
           │ commande            │ subscribe
           ▼                     ▲
┌── Services ─────────┐   ┌─ StateBus ─────────┐
│ MountService        │──▶│ - état par         │
│ GpsService          │──▶│   subsystem        │
│ NetworkService      │──▶│ - overall calculé  │
│ SystemService       │──▶│ - seq monotone     │
│ TrackingService     │──▶│ - asyncio pub/sub  │
└─────────────────────┘   └─────────┬──────────┘
                                    │ broadcast
                                    ▼
                             ┌─ SSE handler ─┐
                             │ 1 file        │
                             │ asyncio par   │
                             │ client        │
                             └───────────────┘
```

### Services et leurs boucles

| Service | Source | Fréquence interne | Publie quand |
|---------|--------|-------------------|--------------|
| `MountService` | nexstarpy + watchdog | Après chaque commande + watchdog toutes les 2 s | Transition d'état, démarrage/arrêt de slew |
| `GpsService` | gpsd (stream) | Event-driven sur le flux gpsd | Transition d'état GPS, throttle sur les détails à 1 Hz |
| `NetworkService` | `/sys/class/net`, `iwgetid` | Poll toutes les 5 s | Changement d'interface active ou de SSID |
| `SystemService` | `/sys/class/thermal`, `/proc/loadavg` | Poll toutes les 5 s | Franchissement de seuil (ok ↔ warning ↔ critical) |
| `TrackingService` | Commandes `/tracking` | Synchrone sur commande | Toggle on/off |

### StateBus — interface

```python
class StateBus:
    def publish(subsystem: str, state: SubsystemState) -> None
    def get_full_state() -> SystemState
    async def subscribe() -> AsyncIterator[Event]  # snapshot initial puis updates
```

- Source unique de vérité pour l'état en mémoire.
- Recalcule `overall` à chaque `publish`.
- Incrémente `seq` à chaque émission d'événement.
- Abonnement via file asyncio par client, buffer borné (drop les events anciens si client trop lent).

### Séquence de boot automatique

1. Démarrage FastAPI (systemd unit au boot du Pi).
2. `MountService.connect()` → publie `mount = connecting`, puis `ready` ou `error`.
3. `GpsService.start()` → publie `gps = no_fix`, évolue vers `searching` puis `fix_2d` / `fix_3d`.
4. Un petit orchestrateur écoute le bus : quand `mount = ready` **ET** `gps ∈ {fix_2d, fix_3d}`, il envoie automatiquement `set_time(utc)` et `set_location(lat, lon)` à la monture.
5. `NetworkService` et `SystemService` tournent en continu dès le démarrage, orthogonaux à tout le reste.

La gestion d'erreurs fine (retries série, timeouts, backoff) sera détaillée dans le plan d'implémentation.

### Commandes monture utilisées en v0.1

- `slew_fixed(axis, direction, rate)` — mouvement directionnel
- `stop_slew(axis)` — arrêt d'un axe
- `set_tracking_mode(mode)` — suivi sidéral on/off
- `set_location(lat, lon)` — envoi position GPS
- `set_time(time_tuple)` — envoi heure UTC
- `get_version()` — vérification connexion (utilisé par le watchdog)

### Structure des fichiers backend

```
backend/
  main.py                    # App FastAPI, startup/shutdown, montage des routes
  routes/
    commands.py              # POST /slew /stop /tracking
    state.py                 # GET /state, GET /events (SSE)
  services/
    mount_service.py         # Wrap nexstarpy, gère slews + tracking + watchdog
    gps_service.py           # Consomme gpsd, publie état GPS
    network_service.py       # Poll interfaces réseau
    system_service.py        # Poll temp CPU + load
    tracking_service.py      # État tracking (enum local, commandes monture déléguées)
    orchestrator.py          # Écoute le bus, déclenche set_time/set_location au boot
  state/
    bus.py                   # StateBus, modèles SubsystemState, SystemState, Event
    aggregator.py            # Règles de calcul de `overall`
  models.py                  # Modèles Pydantic (requêtes/réponses REST)
```

## App Flutter — Téléphone

### Principe : backend optionnel

L'app a deux modes de fonctionnement :

- **Mode connecté** : connexion SSE active, état en temps réel, tous les contrôles actifs.
- **Mode offline** : Pi injoignable (timeout HTTP au démarrage ou rupture de la connexion SSE persistante).
  - La pastille globale affiche `OFFLINE` (rouge fixe, distincte de `error`).
  - Les contrôles liés à la monture (D-Pad, rate, tracking) sont **désactivés visuellement** (grisés, non interactifs).
  - Un bouton "Reconnecter" est accessible depuis la status bar et depuis la SystemScreen.
  - Les fonctionnalités offline-safe (v0.3+ : planificateur, catalogue, historique) resteront opérationnelles. En v0.1 le mode offline est principalement un principe architectural.

Pour rendre ce mode possible, les modèles de données sur lesquels les futures features reposeront (objets observables, sessions planifiées, préférences utilisateur) devront être stockés localement côté app et synchronisés avec le Pi à la connexion. Les détails seront spécifiés dans les specs v0.3+.

### Découverte du Pi sur le réseau

L'app résout le Pi via **mDNS** à l'adresse `astro-brain.local` (hostname déjà configuré sur le Pi). Si la résolution échoue (mDNS non supporté ou Pi sur un autre réseau), l'app bascule en mode offline — la configuration manuelle d'une IP explicite est hors scope v0.1 mais devra être ajoutée avant un déploiement en conditions réelles.

Port par défaut du backend : `8000` (FastAPI).

### Écrans

Trois écrans en v0.1 :

- **SplashScreen** — transition au démarrage, animation de connexion au Pi
- **HomeScreen** — écran principal de contrôle
- **SystemScreen** — page de diagnostic, accessible depuis la pastille globale

### SplashScreen

Affiché au lancement de l'app. Trois phases :

| Phase | Indication visuelle | Action |
|-------|---------------------|--------|
| 1. Contacter le Pi | Étape active `CONTACTING ASTRO-BRAIN.LOCAL` | Ping/GET `/state` avec timeout 3 s |
| 2. Charger l'état initial | Étape active `LOADING STATE SNAPSHOT` | Parse de la réponse `/state` |
| 3. Ouvrir le flux d'événements | Étape active `OPENING EVENT STREAM` | Connexion SSE `/events` |

Transition fondu vers HomeScreen dès que la phase 3 réussit. En cas d'échec à n'importe quelle étape :

- Icône centrale devient `ph-warning`
- Message `ASTRO-BRAIN NOT REACHABLE` en rouge saturé
- Hints : vérifier le Wi-Fi, vérifier que le Pi est allumé
- Bouton primaire **`RETRY`** (relance la séquence)
- Lien secondaire **`CONTINUE OFFLINE →`** (entre dans l'app en mode offline)

Design visuel : logo central avec deux anneaux rotatifs contre-rotatifs, titre `ASTRO-BRAIN V 0.1`, police JetBrains Mono, animation halo sur l'icône centrale.

### HomeScreen

Un seul écran pour tout le contrôle.

| Widget | Rôle | Position |
|--------|------|----------|
| `StatusBar` | Pastille globale (🟢🔵🟠🔴) tappable + toggle jour/nuit | Haut |
| `DPadControl` | 4 boutons directionnels ALT+/-, AZ+/- | Centre |
| `RateControl` | `[−]` + 9 segments + `[+]` avec numéro courant affiché | Sous le D-Pad |
| `TrackingToggle` | Toggle suivi sidéral on/off avec icône `ph-crosshair-simple` | Bas |

Interactions :
- **Appui sur un bouton directionnel** → `POST /slew { axis, direction, rate }`
- **Relâche** → `POST /stop { axis }`
- **Boutons `−` / `+` du rate** → mise à jour locale, utilisée au prochain slew (1 à 9, valeur par défaut au lancement : **5**)
- **Toggle tracking** → `POST /tracking { enabled }`
- **Tap sur la pastille globale** → push `SystemScreen`

Aucun affichage brut de `lat / lon / UTC` sur cet écran — cette info vit dans `SystemScreen`.

### SystemScreen

Accessible par tap sur la pastille globale. Écran purement en lecture, 5 cartes.

Chaque carte contient :
- **Icône Phosphor** du subsystem (voir table ci-dessous)
- **Label** technique (`MOUNT`, `GPS`, `TRACKING`, `NETWORK`, `SYSTEM`)
- **État en texte** (`Ready`, `Fix 3D`, `Moving`, `Searching`…)
- **Détails** pertinents (lat/lon pour GPS, firmware pour mount, temp pour system…)
- **Pastille colorée** selon l'état local du subsystem
- **Durée "depuis X"** (calculée depuis `since`)
- **Message d'erreur** en rouge si présent

Aucune action sur cet écran — pas de bouton "Réessayer", pas de commandes. C'est du diagnostic pur. Les retries manuels arriveront en v0.2+ quand il y aura des procédures explicites à déclencher.

### Icônes (Phosphor Icons, variante bold)

- `ph-arrows-out-cardinal` — MOUNT (4 directions ALT/AZ)
- `ph-gps-fix` — GPS
- `ph-crosshair-simple` — TRACKING (verrouillage sur cible)
- `ph-wifi-high` — NETWORK
- `ph-cpu` / `ph-thermometer-simple` — SYSTEM (selon l'état, thermomètre quand warning/critical)
- `ph-caret-up/down/left/right` — flèches du D-Pad
- `ph-plus` / `ph-minus` — boutons du rate
- `ph-sun` / `ph-moon` — toggle thème
- `ph-warning` — splash en erreur
- `ph-arrow-clockwise` — retry
- `ph-check` / `ph-circle` — étapes du splash (fait / en attente)
- `ph-caret-left` — retour depuis SystemScreen

Package Flutter : `phosphor_flutter`.

### Thème — AstroTheme

Deux palettes, même structure.

**Mode jour (bleu spatial)**
- Fond : dégradé `#060A18 → #0A0818`, grille subtile `rgba(60,130,255,0.04)`
- Texte : `rgba(180,215,255)`
- Accent : `#60a0ff` avec glow `rgba(60,130,255,0.6)`
- Pastilles : vert `#00E676` · bleu `#40C4FF` · orange `#FFB300` · rouge `#FF5252`

**Mode nuit (rouge astro)**
- Fond : dégradé `#0C0606 → #0A0606`, micro-étoiles subtiles en rouge très atténué
- Texte : `rgba(255,170,155)`
- Accent : `#ff5a3a` avec glow `rgba(255,90,58,0.7)`
- Pastilles : tout en nuances de rouge uniquement
  - "vert" (ok) → `#8B2020` (rouge sombre)
  - "bleu" (transition) → `#C04040` (rouge moyen, clignotant)
  - "orange" (dégradé) → `#E04020` (rouge vif)
  - "rouge" (erreur) → `#FF3030` avec halo saturé
  - La différenciation passe par l'intensité + le label texte, pas par la teinte.
- **Aucun bleu ni vert en mode nuit**

Toggle jour/nuit : icône dans la status bar qui reflète le **mode courant** — `ph-sun` affichée en mode jour, `ph-moon` en mode nuit. Tap pour basculer.

### Polices

- **Inter** (400/500/600/700) — texte d'interface
- **JetBrains Mono** (400/500/700) — labels techniques, valeurs numériques, monospace pour le feel HUD

### Structure Flutter

```
lib/
  main.dart                       # Point d'entrée, initialisation thème + navigation
  app.dart                        # App widget, router
  screens/
    splash_screen.dart            # Séquence de connexion + fallback offline
    home_screen.dart              # Contrôle D-Pad + rate + tracking
    system_screen.dart            # Diagnostic des sous-systèmes
  widgets/
    status_bar.dart               # Pastille globale + toggle thème
    dpad_control.dart             # D-Pad 4 directions
    rate_control.dart             # [−] segments [+]
    tracking_toggle.dart          # Toggle suivi sidéral
    subsystem_card.dart           # Carte d'un sous-système dans SystemScreen
    global_dot.dart               # Pastille réutilisable (vert/bleu/orange/rouge)
  services/
    api_service.dart              # POST /slew /stop /tracking, GET /state
    event_stream_service.dart     # Connexion SSE /events avec reconnexion auto
    connectivity_service.dart     # État connecté / offline, switch de mode
  models/
    subsystem_state.dart
    system_state.dart
  state/
    app_state.dart                # Source de vérité côté client (alimenté par SSE)
  theme/
    astro_theme.dart              # Palettes jour (bleu) et nuit (rouge)
```

## Matériel requis pour la v0.1

| Composant | Rôle | Statut |
|-----------|------|--------|
| Mak Bresser 127/1900 | Tube optique | Disponible |
| Monture Celestron | Pointage motorisé | Disponible |
| Raspberry Pi 3 B+ | Backend, serveur | Disponible |
| Module DroTek GPS | Géolocalisation, heure UTC | Disponible |
| Câble USB-série | Pi → port HC monture | À vérifier |
| Téléphone Android/iOS | App Flutter | Disponible |

## Hors scope v0.1

- Focuseur motorisé (v0.2)
- Plate solving et alignement auto (v0.2)
- GoTo et catalogue d'objets (v0.3)
- Planificateur d'observations — utilisateur du mode offline (v0.3)
- Catalogue intelligent avec filtrage visuel/photo (v0.4)
- Module astrophoto, autofocus, guidage (v0.5)
- Joystick analogique (remplacement futur du D-Pad)
- WebSocket (SSE suffit, on n'ajoutera du bidirectionnel que si un besoin client→serveur push apparaît)
- Mode hotspot Wi-Fi sur le terrain (le sous-système `network` est déjà en place pour refléter l'état quand ce sera activé)

## Roadmap complète

| Version | Contenu |
|---------|---------|
| **v0.1** | Joystick + tracking + GPS/heure + état système événementiel |
| **v0.2** | Focuseur + plate solving + alignement auto |
| **v0.3** | GoTo + catalogue d'objets + planificateur d'observations (offline-capable) |
| **v0.4** | Catalogue intelligent (filtrage visuel/photo selon le tube) |
| **v0.5** | Module astrophoto (séquences, autofocus, guidage) |

## Matériel prévu pour les versions futures

| Composant | Version | Coût | Statut |
|-----------|---------|------|--------|
| T7C | v0.2+ (imagerie) | — | Disponible |
| Orion StarShoot Autoguider | v0.2 (plate solving) + v0.5 (guidage) | 40€ | Commandé |
| SVBONY SV165 | v0.2+ (lunette guide) | ~40-55€ | À commander |
| NEMA 17 + TMC2208 | v0.2 (focuseur) | — | À acquérir |
