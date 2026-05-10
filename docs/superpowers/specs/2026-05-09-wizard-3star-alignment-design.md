# Wizard d'alignement 3 étoiles — Design

**Date** : 2026-05-09
**Macro** : 3 (Mise en station + GoTo basique), étape #2
**Statut** : design validé, à implémenter

## Objectif

Permettre à l'utilisateur d'aligner la monture sur le ciel via un wizard guidé sur 3 étoiles, produisant un modèle de transformation `(sky_az, sky_alt) ↔ (mount_az, mount_alt)` utilisable par le futur `goto_service`. L'app Flutter et le backend doivent être prêts à l'arrivée du dongle CP2102 (validation INDI bloquée hardware).

## Décisions clés

1. **Pré-pointage** : auto-slew assisté capteurs (compass LIS3MDL + tilt ADXL345 + GPS) puis fine-tune joystick. Précision pré-pointage ≈ ±1°, suffisante pour amener l'étoile dans l'oculaire grand-champ.
2. **Sélection des étoiles** : hybride — le système suggère 3 étoiles candidates (mag<2.5, distribuées ~120° en AZ, isolées, dans les courses), l'utilisateur peut swap n'importe laquelle.
3. **Catalogue** : mini catalogue d'étoiles d'alignement (~30-50 entrées) embarqué dans le backend (`alignment_stars.json`), distinct du catalogue utilisateur de Macro 3 #3.
4. **Validation** : écran "Option C" — RMS global + 3 résiduels (outlier en accent rouge) + encart explicatif des causes possibles + 2 CTA (`REFAIRE <ÉTOILE>` outlined / `ACCEPTER` primaire).
5. **Persistance** : modèle persisté dans `state.db` (table `alignment_model`) avec horodatage UTC + position GPS. Au boot suivant, restore proposé **uniquement si** Δt < 12h ET ΔGPS < 20m. Sinon, fresh start.
6. **Edge cases** :
   - Slew unreachable → auto-suggest swap vers une candidate alternative.
   - Erreur dure (mount disconnect, INDI crash, backend reboot) → abandon, on recommence depuis zéro.
7. **Réutilisation widgets** : refactor de `DPadControl` et `RateControl` en widgets présentationnels (callbacks + paramètres de taille), partagés entre Manual et le wizard.
8. **AppBar** : réutilisation de `AstroAppBar` avec une nouvelle valeur `AstroScreen.alignment`. Pendant le wizard, `overall = transition` → pastille "EN COURS".
9. **UX par étoile** (mockup D2) : HudPanel avec axis-bars (label + bar marker current/target + delta numérique) pour AZ et ALT, D-Pad 3×3, RateControl 9-segments, CTA "CENTRÉ ✓". Le hero affiche `α Lyrae · mag 0.03 · AZ 248° / ALT 42°` (coords cible).

## Architecture

### Vue d'ensemble

```
[Hub] → [Intro: 3 candidates + swap]
        → boucle 3× : [Pré-pointage] → [Fine-tune] → [Record]
        → [Validation: RMS + résiduels + diagnostic]
        → [Done] → retour Hub
```

### Backend

```
backend/astro_brain/alignment/
├── catalog.py          # JSON load + select_candidates(observer, time, mount_limits)
├── solver.py           # compute_alignment(recorded) → AlignmentModel via SVD
├── service.py          # AlignmentService singleton (start/record/swap/finalize/cancel/restore)
├── repository.py       # state.db accès table alignment_model
└── models.py           # Pydantic: Star, StarRecord, AlignmentSession, AlignmentModel, Residuals
```

API (`backend/astro_brain/api/alignment_router.py`) :

| Verbe | Route | Description |
|---|---|---|
| `POST` | `/align/start` | Crée session + renvoie 3 candidates |
| `POST` | `/align/swap/{idx}` | Remplace une candidate (avant son record) |
| `POST` | `/align/slew/{idx}` | Demande pré-pointage de la candidate idx |
| `POST` | `/align/record` | Enregistre la position monture courante comme centrée sur idx |
| `POST` | `/align/finalize` | Calcule modèle + persiste + renvoie résiduels |
| `POST` | `/align/restart_star` | Tronque recorded_stars pour rejouer une étoile |
| `DELETE` | `/align/session` | Annule la session (ne touche pas le modèle persisté) |
| `GET` | `/align/session` | État courant (pour reprise après cold-start Flutter) |

SSE : un event `alignment.session` est diffusé quand une session existe (current_idx, recorded_count, dernier RMS si finalisé).

### Frontend

```
app/lib/features/alignment/
├── bloc/alignment_bloc.dart       # États + events
├── repository/alignment_repository.dart   # REST + SSE wrap
└── screens/
    ├── intro_screen.dart           # 3 candidates + swap
    ├── per_star_screen.dart        # Mockup D2
    ├── validation_screen.dart      # Option C
    └── done_screen.dart
```

États du `AlignmentBloc` : `AlignmentIdle`, `AlignmentLoadingCandidates`, `AlignmentPrePointing`, `AlignmentFineTuning`, `AlignmentValidating`, `AlignmentDone`, `AlignmentError`.

Refactor préalable :
- `app/lib/widgets/dpad_control.dart` → présentationnel : `DPadControl({ required onPress, required onRelease, double cellSize, double iconSize })`
- `app/lib/widgets/rate_control.dart` → présentationnel : `RateControl({ required value, required onChanged, int min, int max })`
- `app/lib/features/manual/screens/manual_screen.dart` adapté pour passer ses callbacks vers `ManualBloc`.

`AstroScreen.alignment` ajouté à l'enum dans `astro_app_bar.dart`.

### Schema SQLite

```sql
CREATE TABLE alignment_model (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  recorded_stars TEXT NOT NULL,    -- JSON [{star_id, sky_az, sky_alt, mount_az, mount_alt}]
  svd_matrix TEXT NOT NULL,        -- JSON 3×3
  rms_arcmin REAL NOT NULL,
  residuals TEXT NOT NULL,         -- JSON {star_id: arcmin}
  validated_at TEXT NOT NULL,      -- ISO UTC
  gps_lat REAL NOT NULL,
  gps_lon REAL NOT NULL
);
```

## Data flow détaillé

### 1. Démarrage

L'utilisateur tape "Aligner" depuis le Hub. Flutter appelle `GET /align/session` :
- `null` → `AlignmentIdle` → écran Intro vide.
- session existante ET (Δt < 12h ET ΔGPS < 20m) → propose la reprise. OUI → saute à l'étape courante. NON → `DELETE /align/session` puis `POST /align/start`.

### 2. Sélection candidates

`POST /align/start` lit GPS courant + UTC, appelle `catalog.select_candidates(...)` qui :
- filtre l'horizon (alt > 20°)
- filtre les courses ALT/AZ déclarées
- garde mag < 2.5
- filtre l'isolation (pas d'autre brillante < 5°)
- distribue 3 étoiles à ~120° en AZ

Réponse : `{ session_id, candidates: [s0, s1, s2], current_idx: 0 }`.

L'utilisateur peut `POST /align/swap/{idx}` tant qu'il n'a pas record cette étoile.

### 3. Boucle par étoile

Pour chaque idx ∈ [0, 1, 2] :

**Pré-pointage** : `POST /align/slew/{idx}` → backend convertit `(sky_az, sky_alt)` → `mount.goto(...)` avec heuristique progressive :

| Étoile | Modèle disponible | Stratégie |
|---|---|---|
| #1 (idx=0) | aucun | capteurs (compass + tilt + GPS) → cap brut |
| #2 (idx=1) | 1 étoile recorded | offset constant `(mount.az − sky.az)` |
| #3 (idx=2) | 2 étoiles recorded | modèle linéaire 2-points |

**Fine-tune** : SSE diffuse `mount.az_current/alt_current`, les axis-bars animent en temps réel. L'utilisateur centre avec D-Pad et RateControl (jog REST classique réutilisé via le `DPadControl` présentationnel).

**Record** : `POST /align/record { idx }` → backend lit la position courante de la monture, append à `recorded_stars`, **et pousse `MountService.sync_radec(star.ra_deg, star.dec_deg)`** pour alimenter le modèle d'alignement natif INDI/Celestron (`ON_COORD_SET=SYNC` puis `EQUATORIAL_EOD_COORD = (ra/15, dec)`). SSE diffuse `current_idx` incrémenté.

> **Amendé 2026-05-10 (ADR du même jour)** : le sync au record est la nouvelle source de vérité pour le tracking et le futur GoTo. Le solver SVD persiste comme indicateur qualité (RMS + résiduels + outlier) mais ne pilote pas la monture.

### 4. Finalize

Après le 3ᵉ record : `POST /align/finalize` → `solver.compute_alignment(...)` calcule :
- la matrice SVD (3×3) de transformation
- le RMS global
- les résiduels par étoile
- l'outlier candidat (résiduel > 3× moyenne des autres)

Modèle persisté dans `alignment_model`.

### 5. Validation utilisateur

Écran "Option C" : RMS + 3 résiduels (outlier en accent) + encart diagnostic des causes possibles. Deux issues :
- `ACCEPTER` → `AlignmentDone` → retour Hub.
- `REFAIRE <ÉTOILE>` → `POST /align/restart_star { idx: <outlier> }` → backend tronque `recorded_stars` pour ne garder que les indices `[0..idx-1]`, remet `current_idx=idx`. Boucle reprend à l'étape 3 pour cette étoile uniquement.

## Error handling

| Cas | Détection | Réponse |
|---|---|---|
| Mount disconnect (USB/INDI) | `mount.connected` SSE = false | `AlignmentError("Monture déconnectée")` ; AppBar `overall=error` ; bouton "Annuler" → `DELETE /align/session`. Pas de retry auto. |
| Slew failure (étoile inaccessible) | `mount.goto()` retourne 422 | Backend retourne `{ blocked: true, suggestion: <next_best> }`. Flutter dialog "Vega non atteignable, essayer Deneb ?" → swap+slew automatique si OK. |
| GPS lost mid-wizard | `sensors.gps.fix = false` | Wizard continue. À finalize, persistance sans `gps_lat/lon` → forcera fresh start au prochain boot. |
| Compass/tilt NaN au pré-pointage idx=0 | erreur capteur | Skip pré-pointage capteurs, slew direct identité. L'utilisateur centre manuellement (D-Pad). |
| Backend redémarre mid-wizard | Flutter SSE coupe | Reconnexion → `GET /align/session` = null (RAM-only) → `AlignmentError("Wizard interrompu, recommencer")`. |
| App Flutter killée mid-wizard, Pi OK | cold-start Flutter | `GET /align/session` retourne la session backend en RAM → reprise propre. |
| User tap "Annuler" dans AppBar | back arrow | Confirm dialog "Abandonner ?" → `DELETE /align/session` + retour Hub. |
| RMS final > 20' | finalize calculation | Modèle persisté avec `quality = "poor"`. Validation montre tout en rouge ; user accepte ou refait tout. |

## Testing

### Backend (pytest)

- `test_catalog.py` : filtrage horizon/courses/mag/isolation, distribution 120°, swap atomique
- `test_solver.py` : input parfait → matrice identité ; offset constant → rotation pure ; outlier injection → identifié ; unités résiduelles en arc-min
- `test_service.py` : start crée session, record incrémente **et pousse `mount.sync_radec(ra_deg, dec_deg)`**, swap interdit après record, finalize → solver+repo, restart_star tronque, cancel n'efface pas le modèle persisté
- `test_repository.py` : roundtrip, load=null si Δt > 12h, load=null si ΔGPS > 20m, load=modèle sinon
- `test_alignment_router.py` (FastAPI TestClient) : status codes, 409 sur record-before-start, 409 sur finalize-before-3, 409 sur swap-after-record

### Frontend (flutter test)

- `alignment_bloc_test.dart` (bloc_test) : transitions complètes du wizard, RestartStarRequested, MountDisconnected, WizardCancelled
- `per_star_screen_test.dart` (widget) : AppBar conforme, axis-bars rendent depuis le state, D-Pad up déclenche bon callback, "CENTRÉ ✓" déclenche `RecordRequested`, palette jour/nuit
- `validation_screen_test.dart` (widget) : 3 résiduels, outlier accent, RMS en tête, encart diagnostic, CTA déclenchent les bons events
- `dpad_control_test.dart` : widget refactoré sans dépendance `ManualBloc`, callbacks invoqués, `cellSize`/`iconSize` paramétrables

### Intégration manuelle (post-dongle CP2102)

1. Wizard depuis Hub avec mount connectée
2. Pré-pointage capteurs amène l'étoile dans le grand-champ
3. Centering D-Pad sans glitch
4. RMS < 10' sur 3 étoiles bien centrées
5. Outlier injection volontaire → écran validation l'identifie
6. Restore après reboot Pi (mount allumée, pas bougée) : prompt OK + acceptation OK
7. Restore refusé si Pi déplacé > 20m

## Hors scope

- Le calcul `goto(target)` qui *utilise* le modèle est l'étape #4 de Macro 3, pas celle-ci. Cette spec produit le modèle ; elle ne le consomme pas.
- Le catalogue utilisateur (Messier + planètes + ~50-100 étoiles) est l'étape #3 de Macro 3, indépendant du mini catalogue d'alignement.
- Aucun lien avec la plate solving (Macro 5+).
- Le wizard ne gère pas le cas où la monture n'a pas été initialement nivelée — c'est un prérequis (Macro 2).

## Références

- Mockups : `.superpowers/brainstorm/42825-1778355945/content/per-star-d2-real-appbar.html` (per-star screen) et `validation-result-options.html` (option C validation)
- Design system : `docs/product/design-system.md`
- Tokens : `app/lib/theme/design_tokens.dart`
- Widgets existants : `app/lib/widgets/astro_app_bar.dart`, `hud_panel.dart`, `app/lib/features/manual/widgets/{dpad_control,rate_control}.dart`
- Roadmap : `docs/project/roadmap.md` (Macro 3 #2)
