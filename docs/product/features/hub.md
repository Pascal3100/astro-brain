# Hub central — Macro 3 item #1 (livré 2026-05-08)

## Pour quoi faire

Landing post-Splash de l'app. Index visuel des features livrées, qui grandit avec le train. Remplace l'ancien `HomeScreen` (joystick) comme écran d'accueil — le joystick est désormais accessible via la carte MANUEL.

## Écrans

### HubScreen

- **AppBar** partagée : pastille `overall` (→ SystemScreen), gear Setup, toggle thème, reconnect conditionnel.
- **Header** : overline `// ASTRO-BRAIN` + question d'accueil `Que fait-on ce soir ?`.
- **4 cartes en liste verticale** :
  - **MANUEL** (primary, gradient + glow) — `HugeIcons.strokeRoundedJoystick01` — `Joystick · piloter la monture` → `ManualScreen`.
  - **SETUP** — `HugeIcons.strokeRoundedSettings02` — `Calibration · niveau · réseau` → `SetupScreen`.
  - **STATUS** — `HugeIcons.strokeRoundedRadar01` — `Indicateurs · capteurs · mount` → `SystemScreen`.
  - **À PROPOS** — `HugeIcons.strokeRoundedInformationCircle` — `Versions · uptime · système` → `AboutScreen`.

Chaque carte : hero icon HugeIcons (stroke-rounded, 28 px) + libellé monospace JetBrains Mono + hint Inter sur une ligne + chevron Phosphor à droite. Tap → `Navigator.push` `MaterialPageRoute`.

## Stratégie évolutive

Le Hub n'affiche que les features **vivantes**. Pas de cartes "Coming soon". Quand une nouvelle feature de premier niveau est livrée (Wizard 3-étoiles, GoTo, Catalogue), elle s'ajoute comme nouvelle carte. Ordre indicatif des prochaines additions (Macro 3) : Wizard alignement → GoTo → Catalogue. Au-delà de ~6-7 cartes, réévaluer le layout (sections, grille).

## Architecture

- `app/lib/features/hub/hub_screen.dart` — `StatelessWidget`, `ListView.separated` de 4 `HubCard`. Pas de BLoC : tout est statique.
- `app/lib/features/hub/widgets/hub_card.dart` — widget réutilisable hero icon + label + hint + chevron, variant `primary`.
- Routing root : `app/lib/app.dart::_RootRouter` retourne `HubScreen` au lieu de `ManualScreen`.

## Refactors associés (livrés sur la même branche)

- `features/home/` → `features/manual/` : `HomeScreen` → `ManualScreen`, `HomeBloc` → `ManualBloc`, etc.
- `features/setup/about/` → `features/about/` : About sort de Setup, devient feature racine accessible depuis le Hub.
- Enum `AstroScreen` : `home` retiré ; `hub`, `manual`, `about` ajoutés.

## Tests

- 3/3 widget tests `HubCard` (rendu, tap, variant primary).
- 7/7 widget tests `HubScreen` (4 cartes en ordre, primary, header, 4 navigations).
- Suite app : 143/143 verts.

## Liens

- Spec : [`docs/superpowers/specs/2026-05-08-hub-central-design.md`](../../superpowers/specs/2026-05-08-hub-central-design.md)
- Plan : [`docs/superpowers/plans/2026-05-08-hub-central-implementation.md`](../../superpowers/plans/2026-05-08-hub-central-implementation.md)
- Design system (icônes) : [`design-system.md`](../design-system.md)
