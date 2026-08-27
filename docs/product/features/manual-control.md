# Contrôle manuel — Macro 0 Socle (livré v0.1)

## Pour quoi faire

Contrôler manuellement la monture depuis le téléphone, comme on le ferait avec la raquette Celestron. Pointage en aveugle, joystick D-Pad, choix du rate, lecture de l'état du suivi sidéral.

## Écrans

### SplashScreen

Boot de l'app : 3 phases séquentielles (`contacting → loading → openingStream`), affichées au moins 350 ms chacune. Fallback `failure` avec message + bouton "continue offline" si le Pi est injoignable.

### HomeScreen (manuel)

Écran principal :
- **AppBar** : pastille `overall` (tap → SystemScreen), toggle thème, bouton reconnect quand offline.
- **D-Pad 3×3** : 4 directions ALT/AZ + bouton STOP central. `onTapDown/Up/Cancel` → POST `/slew` puis `/stop`. Feedback visuel au press (couleur lerp + glow).
- **Rate control** : 9 barres + boutons ± pour rate 1..9. Clamp côté bloc.
- **Indicateur de tracking** (lecture seule depuis le 2026-08-27) : `TRACKING SIDEREAL` / `TRACKING OFF` / `TRACKING —` quand `connection != connected` ou `mount.state ∉ {ready, moving}` — l'état publié n'est pas signifiant hors monture prête, on l'affiche comme inconnu plutôt que comme « off ». Le suivi s'arme tout seul à la première étoile validée de l'alignement ([ADR 2026-08-27](../../project/decisions.md)) : l'app ne le commande plus, elle le constate. Le libellé OFF est doublé de « s'arme à la 1ʳᵉ étoile validée » pour que l'état normal d'avant alignement ne se lise pas comme une panne.

### SystemScreen

Vue détaillée des sous-systèmes :
- 5 cartes : MOUNT, GPS, TRACKING, NETWORK, SYSTEM.
- Chaque carte : icône, libellé, détails contextuels (firmware monture, lat/lon/sats GPS, ssid/ip réseau, temp/load système), `depuis Xs/Xmin/Xh`, pastille calculée par sous-système, message d'erreur en rouge si présent.

## Interactions critiques

- **Press long sur D-Pad** = slew continu tant que pressé. Relâcher / sortir du bouton = stop immédiat.
- **Sécurité tracking** : plus de commande de suivi côté app — donc plus rien à garder. L'arrêt des moteurs en dernier recours, c'est la coupure d'alimentation de la monture (arbitré le 2026-08-27) ; `/stop` ne convient pas, il réengage le suivi par construction. L'endpoint `POST /tracking` reste exposé côté backend pour le diagnostic.
- **Messages d'erreur monture humanisés** : utilitaire `humanizeMountMessage` qui mappe les erreurs techniques (`[Errno 2] could not open port…`) vers des messages compréhensibles dans le SystemScreen. Les logs serveur restent techniques.

## Tests

53/53 verts (Dart) — modèles, parser SSE, services, blocs, cubits, humanizer.

## Liens

- Spec design : [`docs/superpowers/specs/archive/2026-04-16-astro-brain-v01-design.md`](../../superpowers/specs/archive/2026-04-16-astro-brain-v01-design.md)
- Plan d'implémentation : [`docs/superpowers/plans/archive/2026-04-24-astro-brain-v01-app.md`](../../superpowers/plans/archive/2026-04-24-astro-brain-v01-app.md)
- Modèle d'état : [`docs/technical/state-model.md`](../../technical/state-model.md)
- API utilisée : [`docs/technical/api.md`](../../technical/api.md) — section Macro 0 Socle
