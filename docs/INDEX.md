# Astro-Brain DIY — index documentation

Point d'entrée de la documentation du projet. Trois angles de lecture, chacun avec son propre index.

## Vues

- **[Technique](technical/README.md)** — comment c'est fait (architecture, hardware, modèle d'état, API, déploiement).
- **[Projet](project/README.md)** — où on en est et où on va (roadmap, journal de sessions, backlog, décisions d'architecture).
- **[Produit](product/README.md)** — ce que l'utilisateur voit et utilise (features, parcours, design system).

## Repères rapides

- **État actuel & prochaine étape** : [project/journal.md](project/journal.md) — section "État du projet" en tête.
- **Roadmap canonique** : [project/roadmap.md](project/roadmap.md).
- **Genèse d'Oracle** : [project/oracle-genese.md](project/oracle-genese.md) — idées et contraintes qui ont mené au module `oracle/`.
- **Spec design en cours** : voir [superpowers/specs/](superpowers/specs/).
- **Plan d'implémentation en cours** : voir [superpowers/plans/](superpowers/plans/).

## Convention

- Chaque `README.md` est un index court (titre + 1 phrase + liens). Pas de contenu, uniquement de la navigation.
- Les docs de fond restent **petits et ciblés** (1 sujet par fichier). Quand un doc grossit, on le scinde.
- Les liens entre docs forment l'arbre de navigation — préférer les liens explicites aux références implicites.
- À chaque étape (commit significatif, fin de plan, livraison) : mettre à jour les docs concernés (en priorité le journal, puis les vues impactées).
