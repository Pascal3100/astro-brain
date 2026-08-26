# Vue technique

Comment Astro-Brain est construit : architecture, matériel, modèle d'état, API, déploiement.

## Sommaire

- [architecture.md](architecture.md) — vue d'ensemble Pi ↔ App, protocoles, choix de stack.
- [hardware.md](hardware.md) — câblage GPIO, UART0 réservé au pont ESP32, périphériques USB.
- [state-model.md](state-model.md) — bus interne, sous-systèmes, agrégateur, format SSE.
- [api.md](api.md) — endpoints REST + flux SSE par macro-étape.
- [deployment.md](deployment.md) — installation Pi OS, dépendances, service systemd.
- [indi-reference.md](indi-reference.md) — onboarding INDI : architecture (`indiserver` + driver + client), modèle des Properties, `pyindi-client`, couverture des 7 besoins Macros 2/3 par `indi_celestron_aux`. **Source de vérité côté backend monture** depuis l'ADR 2026-05-01.
- [nexstar-capabilities.md](nexstar-capabilities.md) — historique : ce que la lib `nexstarpy` 0.1.0 (utilisée dans Macro 0 Socle / livré v0.1) wrappait. Conservé pour mémoire ; remplacé par INDI à partir de Macro 1.
- [nexstar-protocol-reference.md](nexstar-protocol-reference.md) — référence complète du protocole NexStar (HC + AUX). Toujours utile : le driver `indi_celestron_aux` parle ce protocole en pass-through, et les opcodes manquants (backlash mount-axis) seront ajoutés via patch upstream sur cette base.

## Schémas de câblage (HTML)

Pages autonomes (SVG inline, thème sombre) décrivant le **câblage fonctionnel** du système, par sous-ensemble. Chaque page porte un badge de statut (✓ validé / 🔬 à valider). Point d'entrée = la page globale. Historique de l'investigation matérielle (voies mortes) : [journal](../project/journal.md) + [archive S26→S30](../project/journal/archive/2026-06-bus-aux.md).

- [cablage-global.html](cablage-global.html) — **schéma bloc du système complet** : 3 alimentations, Pi ↔ WiFi ↔ ESP32 ↔ bus AUX ↔ monture, masses communes. Chaque bloc pointe vers sa page de détail.
- [cablage-alimentation.html](cablage-alimentation.html) — les 3 sources (Pi 220→5 V/2,5 A ; rail 12→5 V ; 3,3 V du Pi), ce que chacune alimente, masses communes. ✓ validé.
- [cablage-pont-esp32.html](cablage-pont-esp32.html) — pont ESP32 STA WiFi / TCP:2000, `Serial2` GPIO16/17 + GPIO32 (/OE), rôles firmware (relais, écho, turnaround). ✓ pont · 🔬 OE.
- [cablage-interface-aux.html](cablage-interface-aux.html) — interface single-wire : RX comparateur LM2902 (✓ prouvé S33) + TX buffer tri-state 74AHCT125 (✓ validé S36, round-trip 30/30), brochage RJ-12. **Référence de câblage du bus AUX.**
- [cablage-carte-aux-pcb.html](cablage-carte-aux-pcb.html) — consolidation **PCB** de l'interface AUX (netlist + brochages en vue carte). Voir aussi `hardware/aux-bridge/` (spec + BOM).
- [cablage-carte-aux-perfboard.html](cablage-carte-aux-perfboard.html) — variante **perfboard** de l'interface AUX (plaque ROTH 16×64, implantation ESP32 + composants), générée par `gen_perfboard.py`. Voir aussi `hardware/aux-bridge/`.

Voir aussi : [project/decisions.md](../project/decisions.md) pour le rationale derrière les choix techniques importants.
