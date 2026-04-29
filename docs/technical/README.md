# Vue technique

Comment Astro-Brain est construit : architecture, matériel, modèle d'état, API, déploiement.

## Sommaire

- [architecture.md](architecture.md) — vue d'ensemble Pi ↔ App, protocoles, choix de stack.
- [hardware.md](hardware.md) — câblage GPIO, capteurs (GPS, compass, ADXL345), périphériques USB.
- [state-model.md](state-model.md) — bus interne, sous-systèmes, agrégateur, format SSE.
- [api.md](api.md) — endpoints REST + flux SSE par version.
- [deployment.md](deployment.md) — installation Pi OS, dépendances, service systemd.

Voir aussi : [project/decisions.md](../project/decisions.md) pour le rationale derrière les choix techniques importants.
