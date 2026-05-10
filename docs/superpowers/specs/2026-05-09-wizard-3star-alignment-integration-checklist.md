# Wizard 3 étoiles — checklist d'intégration sur ciel réel

À exécuter dès que le dongle CP2102 est en place et que la stack INDI tourne sur le Pi.

Référence : plan d'implémentation `docs/superpowers/plans/2026-05-09-wizard-3star-alignment.md`. Spec design : `docs/superpowers/specs/2026-05-09-wizard-3star-alignment-design.md`.

## Pré-requis

- [ ] Macro 1 INDI : `MountIndiAdapter` validé via smoke test E2E sur dongle (sections 0+3 de `backend/deploy/INTEGRATION_CHECKLIST.md`)
- [ ] Monture Celestron alimentée, GPS Pi avec fix 3D, heure synchronisée vers la monture
- [ ] Compass LIS3MDL + tilt ADXL345 (mount + tube) calibrés (Macro 2 Slice A — items #1 #2 #3)
- [ ] App Flutter `0.2.0+1` déployée sur l'Android USB (`flutter run --release` ou APK)
- [ ] Pi à jour sur `main` et `astro-brain.service` redémarré (la migration sqlite `_002_alignment` doit s'être appliquée)

## Wizard end-to-end (golden path)

1. [ ] Hub : tap **ALIGNER**. Le wizard s'affiche : hero "ALIGNEMENT", bouton DÉMARRER.
2. [ ] Tap DÉMARRER. Backend renvoie 3 candidates pertinentes pour l'heure et la position (≥ 30° d'altitude, séparation angulaire deux à deux ≥ 30°). PerStarScreen apparaît avec compteur "1/3".
3. [ ] Étoile 1 — la monture slew avec heuristique capteurs (compass + tilt + GPS). L'étoile est dans le grand-champ (~1°). Vérifier que l'AppBar reste en `EN COURS` (pastille muted) et `state.connection == online`.
4. [ ] Centrer avec D-Pad + RateControl. Vérifier que les axis-bars AZ/ALT bougent en temps réel et que le compteur d'écart converge.
5. [ ] Tap **CENTRÉ ✓**. Passage automatique à PerStarScreen "2/3" pour l'étoile suivante.
6. [ ] Étoile 2 — le pré-pointage utilise l'offset de la 1ère étoile (modèle 1-point). Centrer + tap CENTRÉ ✓.
7. [ ] Étoile 3 — le pré-pointage utilise un modèle linéaire 2-points. Centrer + tap CENTRÉ ✓.
8. [ ] **ValidationScreen** apparaît : RMS < 10', 3 barres de résiduels visibles, pas de bloc diagnostic (aucun outlier).
9. [ ] Tap **ACCEPTER**. Retour `DoneScreen` "MONTURE ALIGNÉE ✓" puis tap RETOUR HUB.
10. [ ] Le modèle d'alignement est persisté dans `state.db` (vérifier via `sqlite3 /var/lib/astro-brain/state.db "SELECT * FROM alignment_sessions ORDER BY id DESC LIMIT 1"`).

## Outlier path (REFAIRE)

11. [ ] Relancer le wizard depuis le Hub.
12. [ ] Sur l'étoile 2, **décentrer volontairement** d'au moins 30' avant de taper CENTRÉ ✓.
13. [ ] Continuer normalement sur l'étoile 3.
14. [ ] Sur ValidationScreen : la barre de l'étoile 2 doit être affichée en accent + glow. Le bloc diagnostic apparaît avec 3 causes possibles. RMS élevé (> 10').
15. [ ] Tap **REFAIRE <ÉTOILE>**. Retour à PerStarScreen 2/3 pour l'étoile à recommencer (les enregistrements 1 et 3 sont conservés côté backend).
16. [ ] Centrer correctement cette fois, tap CENTRÉ ✓. ValidationScreen ré-affichée avec RMS amélioré.

## Restore mid-wizard

17. [ ] Lancer le wizard, capturer 1 étoile, **fermer l'app** sans valider.
18. [ ] Rouvrir l'app, tap ALIGNER → DÉMARRER. Le wizard doit reprendre directement à PerStarScreen "2/3" (la session existante est restaurée par `existing ?? await repo.start()`).

## Persistance

19. [ ] Reboot Pi (`sudo reboot`) avec mount allumée — **ne pas bouger la monture physiquement**. À la reconnexion app, l'écran "DONE" du wizard doit indiquer que le modèle est toujours disponible (à valider une fois Macro 3 #4 livre la consommation du modèle).
20. [ ] Déplacer le Pi de plus de 20 m. Au reboot, le modèle doit être invalidé silencieusement (garde-fou ΔGPS 20 m / Δt 12 h dans le repository).

## Edge cases

21. [ ] **Mount disconnect** : pendant le wizard (entre 2 captures), couper l'alim de la monture. L'AppBar passe en error rouge. Le bloc reçoit `MountDisconnected` → `AlignmentError("Monture déconnectée")`. Vérifier le retour Hub manuel possible.
22. [ ] **Slew unreachable** : configurer une limite ALT 30°-60° (Setup Macro 2 Slice B) et choisir une étoile à 70° via `swap`. Le backend renvoie 422 ; l'app doit proposer un swap candidate plutôt que de crasher.
23. [ ] **Erreur réseau** : couper le Wi-Fi pendant le pré-pointage de l'étoile 2. Vérifier le retour propre à `AlignmentError`. À la reconnexion, relancer le wizard ; la session backend mid-wizard doit toujours être restaurable (cf. test #17).

## TODO software à résoudre avant validation manuelle

- [ ] `targetAz`/`targetAlt` dans `alignment_wizard_screen.dart` sont actuellement à `0.0` avec `// TODO(macro-3-runtime)`. À brancher quand la response `/align/start` exposera les coords cibles calculées (ajout `target_az`/`target_alt` au DTO `StarDto` ou wrapper). Sans ça, les axis-bars ne montrent pas l'écart à la cible — bloque la validation manuelle des étapes 4, 6, 7 ci-dessus.
- [ ] Consommation SSE `alignment.session` côté Flutter (actuellement le bloc fait du polling REST implicite via les events). À brancher si la latence wizard ressentie est trop grande lors du smoke test.

## Reporting

À l'issue du smoke, mettre à jour :
- `docs/project/journal.md` (session courante : "smoke wizard 3 étoiles OK / KO + détails")
- `docs/project/roadmap.md` : passer Macro 3 #2 de 🚧 à ✅ si tous les checks ci-dessus passent
