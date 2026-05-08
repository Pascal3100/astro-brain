# Spec — Hub central (Macro 3, item #1)

> Date : 2026-05-08
> Statut : design validé, prêt pour writing-plans
> Précédente : [v0.2 Setup design](2026-05-01-astro-brain-v02-setup-design.md)
> Macro : 3 — Mise en station + GoTo basique

## Contexte

Macro 2 (Setup) est quasi-livrée — il reste deux items dongle-bloqués (D-1..D-4) et un pack de finalisation (FINAL-1..4). Macro 3 ouvre la **mise en station + GoTo basique** : Hub central, wizard 3 étoiles, GoTo réel, catalogue minimal, page Catalogue.

L'item #1 du train Macro 3 est le **Hub central** : la landing post-Splash qui remplace `HomeScreen` (joystick) et qui devient le point d'entrée unique vers les surfaces de l'app. Aujourd'hui, post-Splash, on atterrit directement sur le joystick — Setup et Status sont accessibles via l'AppBar mais le joystick **est** la home, ce qui ne tient plus dès qu'on ajoute Wizard et GoTo comme features de premier niveau.

## Scope

**Cette spec couvre uniquement le Hub** — pas le Wizard, pas le GoTo, pas le catalogue. Ces items auront leur propre brainstorm et leur propre spec.

Travail livré par cette spec :

1. Nouvel écran `HubScreen` — landing post-Splash, 4 cartes en liste verticale.
2. Promotion de `HomeScreen` (joystick) en `ManualScreen` — feature parmi les autres, plus la racine.
3. Promotion de `AboutScreen` — sort de Setup, devient feature de premier niveau accessible via Hub.
4. Routing root revu : Splash → Hub.
5. AppBar mise à jour : enum `AstroScreen` étendu (`hub` ajouté, `home` → `manual`).

**Hors scope explicite** :
- Wizard 3-étoiles (item #2 Macro 3, brainstorm dédié).
- GoTo réel (item #3 Macro 3, brainstorm dédié).
- Catalogue backend + page Catalogue (items #4 et #5 Macro 3).
- Refonte des écrans cibles (Manual, Setup, System, About) — ils restent identiques.
- Mode tablette / orientation paysage (l'app reste portrait téléphone).
- Animations de transition entre Hub et leaves (transitions Material par défaut suffisent).

## Décision structurante : Hub évolutif, pas anticipateur

Le Hub livre **uniquement les cartes de features qui existent**. Pas de carte "Coming soon", pas d'entrée désactivée. Quand le Wizard sera livré, il s'ajoutera comme 5e carte. Quand GoTo arrivera, 6e carte. Etc.

Rationale :
- Pas de cartes orphelines qui frustrent l'utilisateur.
- Chaque livraison de feature = un commit qui ajoute sa carte au Hub. Cohésion item ↔ visibilité.
- Le Hub n'est pas figé : c'est un index vivant du train.

## Architecture

### Cartes Hub v1 (état post-Macro 2)

| Ordre | Carte | Hero icon (HugeIcons) | Route → écran | Statut |
|---|---|---|---|---|
| 1 | **MANUEL** | `gameController` | `ManualScreen` (ex `HomeScreen`) | Existe (v0.1) |
| 2 | **SETUP** | `settings02` | `SetupScreen` | Existe (Macro 2) |
| 3 | **STATUS** | `radar01` | `SystemScreen` | Existe (v0.1) |
| 4 | **À PROPOS** | `informationCircle` | `AboutScreen` | Existe (Slice C) |

L'icon mapping est indicatif — l'implémentation peut affiner si une icône HugeIcons précise rend mieux dans le HUD bleu/rouge.

### Layout — Liste verticale

Chaque carte fait pleine largeur, hauteur ~64-80px, structure :

```
┌─────────────────────────────────────────────────┐
│ ┌────┐  MANUEL                              ›  │
│ │icon│  Joystick · piloter la monture           │
│ └────┘                                          │
└─────────────────────────────────────────────────┘
```

- **Container icon** : 48×48, fond `accent @ 8%`, radius 12. La première carte (MANUEL aujourd'hui) est mise en avant avec un fond gradient `accent → transparent` et un glow accent doux — c'est l'action principale typique d'une session.
- **Libellé** : JetBrains Mono, 13px, letter-spacing 1.8, weight 600, color `accent text` (`#B4D7FF` jour / `#FFAA9B` nuit).
- **Hint** : texte 11px Inter, `textMuted`, une ligne — décrit l'action en français courant.
- **Chevron** : Phosphor `caretRight` ou simple `›`, accent @ 40%, à droite.

Espacement vertical entre cartes : 12px. Padding écran : 16px horizontal, espace généreux entre titre Hub et premières cartes (32px).

### En-tête Hub

Au-dessus des cartes :

- **Suréttiquette** : `// ASTRO-BRAIN` en JetBrains Mono, accent @ 60%, letter-spacing 2px.
- **Titre** : `Que fait-on ce soir ?` en Inter 18px, weight 500, color `accent text`. Phrase d'accroche unique, fixe (pas de personnalisation contextuelle).

Pas de sous-titre de statut ni de banner d'erreur — toute la signalisation système reste dans la pastille `overall` de l'AppBar.

### AppBar

L'AppBar partagée reste présente — convention design system non négociée. Contenu standard :
- Pastille `overall` cliquable → `SystemScreen`.
- Toggle thème jour/nuit.
- Reconnect conditionnel si déconnecté.

Note : la pastille AppBar et la carte STATUS du Hub routent au même endroit. Redondance assumée — la pastille est un raccourci permanent (4×4mm), la carte est une zone tactile explicite avec libellé. Pas de conflit, juste deux affordances pour la même destination.

### Routing

Modifications dans `app/lib/app.dart` :

```dart
// _RootRouter.build :
//   Splash → Hub (au lieu de Home)
return const HubScreen();
```

Modifications dans `app/lib/widgets/astro_app_bar.dart` :

```dart
enum AstroScreen { hub, manual, setup, system, about }
//                  ^^^         ^^^^^^^   ^^^^
//                  nouveau     ex-home   nouveau (était dans setup)
```

Toutes les leaves (Manual, Setup, System, About) ont un bouton retour → Hub via `Navigator.pop` standard. Le pattern de navigation reste push/pop classique : Hub est la racine, les leaves sont push-ées.

### Promotion `HomeScreen` → `ManualScreen`

Renommage strict :
- `app/lib/features/home/` → `app/lib/features/manual/`
- `home_screen.dart` → `manual_screen.dart` ; classe `HomeScreen` → `ManualScreen`
- `home_bloc.dart` → `manual_bloc.dart` ; classe `HomeBloc` → `ManualBloc`
- `home_event.dart` / `home_state.dart` idem.
- Tests `app/test/features/home/*` → `app/test/features/manual/*`

Pas de changement de comportement, pas de refactor BLoC. Renommage pur.

### Promotion `AboutScreen` hors de Setup

`app/lib/features/setup/about/` → `app/lib/features/about/`. La carte "À propos" actuellement présente dans `SetupScreen` est retirée. Setup retrouve une sémantique pure "configuration".

L'écran About lui-même ne change pas — même blocs versions/réseau/uptime, même appel `GET /about`.

## Composants Flutter à créer

### `HubScreen` — `app/lib/features/hub/hub_screen.dart`

`StatelessWidget`. Arborescence :

```
Scaffold
└─ Container (gradient bg via context.colors)
   └─ SafeArea
      └─ Column
         ├─ AstroAppBar(current: AstroScreen.hub)
         ├─ Padding (header)
         │  └─ Column [suréttiquette + titre]
         └─ Expanded
            └─ ListView (4 HubCard)
```

Pas de BLoC dédié au Hub : aucune donnée à charger. Les cartes sont statiques côté logique. Les libellés et routes sont définis dans une liste const dans le fichier.

### `HubCard` — `app/lib/features/hub/widgets/hub_card.dart`

`StatelessWidget` réutilisable. Props :

```dart
class HubCard {
  final IconData heroIcon;        // HugeIcons.X
  final String label;             // 'MANUEL'
  final String hint;              // 'Joystick · piloter la monture'
  final VoidCallback onTap;
  final bool primary;             // true = première carte mise en avant
}
```

Composition Material : `Material` + `InkWell` pour le ripple (cohérent M3), `Container` avec `BoxDecoration` (border, gradient si primary, radius), `Row` [icon container, texte, chevron].

### Modifications enum `AstroScreen`

`app/lib/widgets/astro_app_bar.dart` :
- Ajouter `hub` et `manual` dans l'enum.
- Retirer `home` (renommé en `manual`).
- Adapter les call sites : `SystemScreen`, `SetupScreen`, `AboutScreen`, `ManualScreen` passent `current` selon leur identité.

## Erreurs et états

Le Hub n'a aucun état d'erreur propre. C'est un index statique. Les erreurs système (déconnexion, mount fault) sont signalées par la pastille `overall` de l'AppBar — comportement déjà en place.

États de l'app dans l'AppBar :
- **Online + ok** : pastille verte `SYSTEM OK`.
- **Online + warn/error** : pastille orange/rouge `MOUNT FAULT`, etc.
- **Offline** : pastille rouge `OFFLINE` + bouton reconnect dans l'AppBar.

Aucune de ces conditions ne bloque le Hub — toutes les cartes restent cliquables. C'est aux écrans cibles (Manual, Setup, etc.) de gérer leur propre indisponibilité si pertinent.

## Tests

### Unitaires Flutter

- `test/features/hub/hub_screen_test.dart` :
  - Hub rend 4 cartes dans l'ordre prévu (MANUEL, SETUP, STATUS, À PROPOS).
  - Première carte a le styling primary (golden ou check d'attribut).
  - Tap sur chaque carte route vers le bon écran (vérif via `Navigator` mocké ou `MaterialPageRoute` capturé).
  - AppBar présente avec `current = AstroScreen.hub`.

- `test/features/hub/widgets/hub_card_test.dart` :
  - Rend label, hint, hero icon.
  - Variant primary applique gradient/glow.
  - `onTap` appelé au tap.

### Smoke navigation

- Test d'intégration léger : Splash → Hub (vérifie le `_RootRouter` modifié).
- Tap MANUEL depuis Hub → ManualScreen ; back → Hub.
- Idem SETUP, STATUS, ABOUT.

### Régression

- `flutter analyze` clean après renames.
- Tests existants `home_*` migrés en `manual_*` passent inchangés (logique pure, juste les imports).

### Validation visuelle

Sur Android physique en USB (pas Chrome / pas émulateur) :
- Hub jour : gradient bleu, première carte en glow accent. Cibles tactiles confortables avec gants.
- Hub nuit : gradient rouge, lisibilité préservée.
- AppBar pastille `overall` clique → SystemScreen ; back → Hub.

## Plan de livraison (suggéré, à raffiner par writing-plans)

Slice unique en une PR :

1. **Renames** : `home/` → `manual/`, déplacer `setup/about/` → `about/`. `flutter analyze` doit passer.
2. **Enum AstroScreen** : ajouter `hub` et `manual`, retirer `home`. Mettre à jour tous les call sites.
3. **`HubCard` widget** + tests unitaires.
4. **`HubScreen`** + tests unitaires + intégration de la liste des 4 cartes.
5. **Routing** : `_RootRouter` → `HubScreen`. Smoke navigation.
6. **Retirer carte About de SetupScreen**. Vérifier `SetupScreen` reste cohérent.
7. **Validation Android USB** : capture d'écran jour + nuit, parcours nominal.
8. **Doc** : feature card `docs/product/features/hub.md` (nouveau) + maj `docs/project/roadmap.md` (Macro 3 item #1 livré).

## Évolution prévue

Items futurs qui ajouteront des cartes au Hub (sans toucher à cette spec) :

- **Wizard 3-étoiles** (Macro 3 #2) → carte `WIZARD ALIGNEMENT` avec hero `HugeIcons.constellation`.
- **GoTo** (Macro 3 #3) → carte `GOTO` avec hero `HugeIcons.target02`.
- **Page Catalogue** (Macro 3 #5) → carte `CATALOGUE` avec hero `HugeIcons.satelliteCard` ou similaire.

Quand le nombre de cartes dépassera ~6-7, on réévaluera le layout (groupement par section, ou bascule grille). Pas un sujet pour aujourd'hui.

## Liens

- [Design system](../../product/design-system.md) — convention AppBar, tokens, double thème, iconographie Phosphor + HugeIcons.
- [Roadmap](../../project/roadmap.md) — Macro 3 décomposition.
- Mockup historique Session 12 : `.superpowers/brainstorm/14340-1777491506/content/hub-design.html` (3 cartes, anticipateur — superseded par cette spec).
- Mockup courant : `.superpowers/brainstorm/1020436-1778273540/content/hub-layouts.html` (2 layouts comparés, A retenu).
