# Vue technique

Comment Astro-Brain est construit : architecture, matériel, modèle d'état, API, déploiement.

## Sommaire

- [architecture.md](architecture.md) — vue d'ensemble Pi ↔ App, protocoles, choix de stack.
- [hardware.md](hardware.md) — câblage GPIO, capteurs (GPS, compass, ADXL345), périphériques USB.
- [state-model.md](state-model.md) — bus interne, sous-systèmes, agrégateur, format SSE.
- [api.md](api.md) — endpoints REST + flux SSE par version.
- [deployment.md](deployment.md) — installation Pi OS, dépendances, service systemd.
- [indi-reference.md](indi-reference.md) — onboarding INDI : architecture (`indiserver` + driver + client), modèle des Properties, `pyindi-client`, couverture des 7 besoins v0.2/v0.3 par `indi_celestron_aux`. **Source de vérité côté backend monture** depuis l'ADR 2026-05-01.
- [nexstar-capabilities.md](nexstar-capabilities.md) — historique : ce que la lib `nexstarpy` 0.1.0 (utilisée en v0.1) wrappait. Conservé pour mémoire ; remplacé par INDI à partir de v0.2.
- [nexstar-protocol-reference.md](nexstar-protocol-reference.md) — référence complète du protocole NexStar (HC + AUX). Toujours utile : le driver `indi_celestron_aux` parle ce protocole en pass-through, et les opcodes manquants (backlash mount-axis) seront ajoutés via patch upstream sur cette base.

Voir aussi : [project/decisions.md](../project/decisions.md) pour le rationale derrière les choix techniques importants.
