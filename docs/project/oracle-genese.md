# Oracle — genèse : idées et contraintes essentielles

> Le « pourquoi » du module `oracle/`. Le « comment consommer » vit dans
> [`oracle/README.md`](../../oracle/README.md) ; la décision formelle dans
> l'ADR [`2026-07-24`](decisions.md).

## Le problème

Planifier une soirée d'observation et piloter le télescope sont **deux moments
disjoints** :

- **Le Pi est éteint quand on planifie.** Le Raspberry Pi vit au télescope,
  alimenté seulement pendant l'observation. La planification se fait avant, à
  l'intérieur, souvent sans réseau côté matériel.
- **Les cibles éphémères bougent.** Les comètes surtout : nouvelles
  découvertes, éléments orbitaux réactualisés, sursauts de luminosité. Une
  donnée figée dans l'app se périme.
- **Calculer une éphéméride demande données + compute.** Il faut les éléments
  orbitaux (MPC) *et* un moteur (skyfield). Le faire sur le Pi supposerait
  réseau + Pi allumé — les deux manquent au moment de planifier. Et le Pi 3 B+
  n'est pas la bonne machine pour ça.

Conséquence : le **night planner doit fonctionner hors-ligne**, sans le Pi.

## L'idée : un plan de données de référence indépendant du Pi

Un service **autonome, hors Pi**, qui :

1. récupère les données éphémères **dans le cloud, sur planning** (GitHub
   Actions, cron hebdo) ;
2. **précalcule** les éphémérides et publie un artefact caché
   (`reference.sqlite` + `manifest.json`) ;
3. est **consommé hors-ligne** par l'app Flutter et le backend Pi.

Les consommateurs ne font que du calcul local trivial (LST → alt/az) : **jamais
de mécanique orbitale**. Comètes d'abord (le cas éphémère le plus dur),
extensible ensuite (NGC/IC, etc.).

> Ce à quoi on a renoncé : l'idée initiale du night planner s'appuyait sur un
> **snapshot tiré depuis le Pi**. Abandonnée — le Pi n'est ni la source fraîche
> (les données MPC ne vivent pas dessus) ni disponible à la planification. Un
> plan de données cloud, découplé du runtime, est le bon niveau.

## Contraintes essentielles

| # | Contrainte | Raison |
|---|---|---|
| 1 | **Zéro dépendance vers le Pi / `backend/` / `app/`.** `oracle/` est un paquet autonome ; les consommateurs ne l'importent jamais. | Découple le plan de données du runtime ; l'artefact est le seul contrat. |
| 2 | **Tourne uniquement en CI (GitHub Actions), jamais sur le Pi.** | Le Pi est contraint et souvent éteint ; le calcul lourd va dans le cloud. |
| 3 | **Déterminisme offline** : kernel JPL `de421.bsp` (~16 Mo) **commité dans git**. | Le build ne dépend pas d'un fetch réseau du kernel. |
| 4 | **Le fetch MPC ne casse jamais le build** : snapshot `CometEls` **bundlé** en fallback. | Une panne réseau MPC ne doit pas priver l'app de sa dernière référence. |
| 5 | **RA/Dec stockées en apparent / of-date (JNow)**, pas J2000/ICRS. | Le consommateur ne fait que LST → alt/az ; aucune précession/nutation côté client. |
| 6 | **Échantillonnage quotidien, fenêtre roulante 60 jours** ; interpolation linéaire côté conso. | Compromis taille de fichier / précision pour des objets lents. |
| 7 | **`predicted_mag` = estimation seulement.** | La luminosité cométaire est imprévisible (sursauts) : à afficher comme estimation, jamais comme filtre dur. |
| 8 | **`schema_version` verrouille la compatibilité.** Le conso refuse un schéma plus récent qu'il ne supporte. | Fait évoluer l'artefact sans casser les vieux clients. |
| 9 | **Publication via release roulante `almanac-latest`** ; `manifest.json` (schema_version, sha256, fenêtre) comme **point de synchro**. Poll du manifest → download du sqlite seulement si le sha256 change. Aucun binaire commité sur `main`. | Sync bon marché ; pas de bloat d'historique git. |
| 10 | **Stack ennuyeuse et cheap** : Python 3.13/uv, skyfield + pandas, `sqlite3` stdlib, PEP-compliant. | Maintenable, reproductible, sans dette. |

## Statut dans la roadmap

Oracle est un **fil transverse**, pas une macro-étape du train : il tourne en
continu et **alimente plusieurs features futures** (night planner offline,
catalogue intelligent…). Il n'a pas de « done » ; il gagne des sources au fil de
l'eau (comètes → plus tard NGC/IC, etc.).

## Hors périmètre (côté producteur)

Délibérément **repoussé aux plans consommateurs** (backend Pi, app Flutter) :

- comment l'app / le Pi **synchronisent et cachent** l'artefact ;
- la **projection alt/az** côté client et la résolution GoTo ;
- les **notifications** (nouvelle comète visible, etc.).

Le producteur s'arrête à : *publier un artefact correct, versionné et
vérifiable*. Le reste est un contrat, pas du code partagé.

## Références

- Contrat consommateur : [`oracle/README.md`](../../oracle/README.md)
- Décision : ADR [`2026-07-24`](decisions.md)
- Plan d'implémentation : [`docs/superpowers/plans/2026-07-24-oracle-producer.md`](../superpowers/plans/2026-07-24-oracle-producer.md)
- Backlog / roadmap : entrées « Oracle / Éphémères » et « Night planner offline »
