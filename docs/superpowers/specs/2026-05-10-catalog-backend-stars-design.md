# Catalogue backend — tranche A : stars étendues

> Cette spec couvre la **première tranche** de Macro 3 #4 (catalogue minimal backend) : les étoiles brillantes nommées (IAU named stars cap mag ≤ 3, ~100-150 entrées). Les tranches suivantes (Messier, planètes, comètes) ré-utilisent l'infra posée ici sans la modifier.

## Goal

Exposer un endpoint REST `/catalog/objects` qui sert un catalogue d'étoiles brillantes nommées, persistées en sqlite, seedées au démarrage à partir d'un fichier SQL versionné. Poser une abstraction `CatalogProvider` extensible permettant d'ajouter ultérieurement des catalogues statiques, dynamiques ou calculés sans toucher au cœur du système.

## Scope

### In (tranche A)

- Table sqlite unifiée `catalog_objects` avec discriminateur `kind`
- `CatalogProvider` Protocol + `SqliteCatalogProvider` (paramétrable par kind)
- `CatalogRegistry` dispatch list/get par kind
- `seed_runner` idempotent appliqué au boot
- Script dev `tools/seed_stars.py` (pull IAU CSV → SQL committé)
- Endpoint `GET /catalog/objects` (filtres : kind, search, max_mag, limit, offset)
- Endpoint `GET /catalog/objects/{qualified_id}`
- Tests : seed idempotence, provider sqlite, routes REST

### Out (tranches suivantes ou hors-scope)

- **Refactor wizard** pour lire via le provider (tranche A+1 ou inclus dans tranche Messier — laisse `_alignment_stars.json` intact pour cette tranche, doublon temporaire assumé sur 32 entrées)
- **`visible_now`** filtre serveur (calcul Az/Alt courant, GPS-aware) — tranche suivante
- **Catalogue Messier** (tranche B) — même pattern, deuxième provider sqlite avec `kind="messier"`
- **Planètes** (tranche C) — `PlanetsProvider` calculé live via skyfield, pas de DB
- **Comètes** (Macro 4+) — table dédiée + `Refresher` périodique
- **Page Catalogue Flutter** (Macro 3 #5)

## Architecture

### Storage — sqlite, table unifiée pour les statiques

```sql
-- migration _003_catalog.sql
CREATE TABLE catalog_objects (
    id TEXT PRIMARY KEY,              -- "star:sirius", "messier:m31"
    kind TEXT NOT NULL,               -- "star" | "messier" | "ngc" | ...
    name TEXT NOT NULL,               -- "Sirius", "Andromeda Galaxy"
    designation TEXT,                 -- "α CMa", "M 31"
    ra_deg REAL NOT NULL,             -- J2000 ICRS, [0, 360)
    dec_deg REAL NOT NULL,            -- J2000 ICRS, [-90, 90]
    mag REAL,                         -- magnitude visuelle (NULL possible)
    constellation TEXT,
    object_type TEXT,                 -- pour DSO : "galaxy", "open cluster"
    angular_size_arcmin REAL,         -- pour DSO étendus
    extras_json TEXT                  -- échappatoire pour le rare (spectral_type, distance, etc.)
);
CREATE INDEX idx_catalog_kind ON catalog_objects(kind);
CREATE INDEX idx_catalog_name ON catalog_objects(name);
CREATE INDEX idx_catalog_mag ON catalog_objects(mag);
```

**Justification table unique** : 80 % des champs (id, kind, name, designation, ra_deg, dec_deg, mag, constellation) sont communs. Les rares spécifiques (object_type, angular_size_arcmin) restent nullables sans bloat. `extras_json` couvre les cas exotiques sans migration. Splitter par kind est cheap si pression future.

**Catalogues hors table unifiée** :
- **Comètes** (futur) : table dédiée `comets` (a, e, i, ω, Ω, M₀, epoch, magnitude, designation) — orbitales évoluent, calcul RA/Dec live au moment de la requête.
- **Planètes** (futur) : pas de table — calcul live skyfield à partir d'un BSP DE421s embarqué.

### Identifiants qualifiés

- Clé primaire en base : `"star:sirius"`, `"messier:m31"` (préfixe `kind:`).
- À l'extérieur du module catalog (ex. wizard `Star.id`, `alignment_sessions.recorded_stars[].star_id`), les IDs restent **sans préfixe** (`"sirius"`). Le préfixe est concaténé/strippé à la frontière du provider.
- Pas de migration des rows `alignment_sessions` existantes : aucune impact sur les sessions persistées.

### Pydantic models

```python
# astro_brain/services/catalog/models.py

class CatalogObject(BaseModel):
    qualified_id: str                 # "star:sirius"
    kind: Literal["star", "messier", "planet", "comet"]
    name: str
    designation: str | None = None
    ra_deg: float
    dec_deg: float
    mag: float | None = None
    constellation: str | None = None
    object_type: str | None = None
    angular_size_arcmin: float | None = None
    extras: dict[str, Any] = Field(default_factory=dict)

class CatalogFilter(BaseModel):
    kind: str | None = None
    search: str | None = None         # LIKE name OR designation
    max_mag: float | None = None
    limit: int = 100
    offset: int = 0
```

### Provider abstraction

```python
# astro_brain/services/catalog/providers.py

class CatalogProvider(Protocol):
    kind: str
    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]: ...
    async def get_object(self, raw_id: str) -> CatalogObject | None: ...

class SqliteCatalogProvider:
    def __init__(self, db, *, kind: str) -> None:
        self._db = db
        self.kind = kind

    async def list_objects(self, filter: CatalogFilter) -> list[CatalogObject]:
        # SELECT ... FROM catalog_objects WHERE kind = self.kind
        # AND (? IS NULL OR mag <= ?)
        # AND (? IS NULL OR (name LIKE ? OR designation LIKE ?))
        # ORDER BY mag NULLS LAST, name
        # LIMIT ? OFFSET ?
        ...

    async def get_object(self, raw_id: str) -> CatalogObject | None:
        # SELECT ... WHERE id = ? -- avec id = f"{self.kind}:{raw_id}"
        ...
```

`SqliteCatalogProvider` est instancié une fois par kind statique. Il prend `raw_id` (sans préfixe) et le qualifie en interne.

**Sérialisation `extras_json`** : la colonne TEXT contient du JSON. Le provider parse à la lecture (`json.loads`) pour peupler `CatalogObject.extras: dict`, et dump à l'écriture (utilisé par les seeds futurs). En tranche A toutes les entrées stars ont `extras = {}`.

### Registry

```python
# astro_brain/services/catalog/registry.py

class CatalogRegistry:
    def __init__(self, providers: dict[str, CatalogProvider]) -> None:
        self._providers = providers

    async def list_all(self, filter: CatalogFilter) -> list[CatalogObject]:
        if filter.kind is not None:
            provider = self._providers.get(filter.kind)
            if provider is None:
                return []
            return await provider.list_objects(filter)
        # Sans filtre kind : interroge tous les providers, concat puis applique
        # limit/offset au global. En tranche A il n'y a qu'un seul provider,
        # donc équivalent à appeler ce provider unique.
        results: list[CatalogObject] = []
        for provider in self._providers.values():
            results.extend(await provider.list_objects(filter.model_copy(update={"limit": filter.limit + filter.offset, "offset": 0})))
        # tri stable par mag NULLS LAST puis name, puis pagination globale
        results.sort(key=lambda o: (o.mag if o.mag is not None else float("inf"), o.name))
        return results[filter.offset : filter.offset + filter.limit]

    async def get_by_qualified_id(self, qid: str) -> CatalogObject | None:
        try:
            kind, raw_id = qid.split(":", 1)
        except ValueError:
            return None
        provider = self._providers.get(kind)
        if provider is None:
            return None
        return await provider.get_object(raw_id)
```

Wire dans `app.py` :

```python
registry = CatalogRegistry({
    "star": SqliteCatalogProvider(db, kind="star"),
    # à venir : "messier": SqliteCatalogProvider(db, kind="messier"),
    # à venir : "planet": PlanetsProvider(skyfield_loader),
    # à venir : "comet": CometsProvider(db),
})
app.state.catalog_registry = registry
```

## Seed workflow

### Dev-time (workstation, exécuté manuellement)

```
backend/tools/seed_stars.py
  ↓ pull IAU CSV via urllib (https://www.iau.org/static/public/themes/naming_stars/IAU-CSN.txt)
  ↓ filter mag ≤ 3
  ↓ écrit backend/astro_brain/data/seed_stars.sql
```

Le `.sql` généré contient des `INSERT OR REPLACE INTO catalog_objects (id, kind, name, designation, ra_deg, dec_deg, mag, constellation) VALUES ('star:sirius', 'star', 'Sirius', 'α CMa', 101.287, -16.716, -1.46, 'Canis Major');` — un par ligne, **committé dans le repo**.

Le script dev est :
- Idempotent (re-run regénère le même `.sql` si la source IAU n'a pas bougé)
- Hors `astro_brain/` package (dans `backend/tools/`) — pas embarqué runtime, pas de dep réseau au runtime
- Doc d'usage : commentaire d'en-tête + `python tools/seed_stars.py --output-dir astro_brain/data/`

### Boot-time (Pi)

Au démarrage backend, dans `_lifespan` après les migrations sqlite :

```python
# astro_brain/services/catalog/seed_runner.py

async def apply_seeds(db, data_dir: Path) -> None:
    for sql_path in sorted(data_dir.glob("seed_*.sql")):
        sql = sql_path.read_text()
        try:
            await db.executescript(sql)
        except Exception:
            logger.exception("seed: %s failed", sql_path.name)
            # ne bloque pas le boot ; le catalogue se chargera incomplet
```

Idempotent grâce à `INSERT OR REPLACE`. Le boot réussit même si un seed échoue (log warning + continue) — un Pi sans catalogue est dégradé mais reste manœuvrable.

### Ajouter un nouveau catalogue (futur)

Coût concret pour ajouter par exemple Messier :
1. `tools/seed_messier.py` (~80 lignes) — pull SIMBAD/VizieR ou Wikidata, génère `data/seed_messier.sql`
2. Ajouter au registry : `"messier": SqliteCatalogProvider(db, kind="messier")`
3. (option) tests d'intégration spécifiques au catalogue Messier
4. Done. Aucun changement à la migration sqlite, à la route REST, au provider.

Pour un catalogue dynamique (comètes) :
1. Migration table `comets` dédiée
2. `CometsRefresher` (job MPC périodique)
3. `CometsProvider` lisant `comets` et reconstituant `CatalogObject` (RA/Dec calculé au temps courant)
4. Ajouter au registry : `"comet": CometsProvider(db)`

Pour un catalogue calculé (planètes) :
1. `PlanetsProvider` (skyfield + DE421s embarqué)
2. Ajouter au registry : `"planet": PlanetsProvider(loader)`

## API REST

### `GET /catalog/objects`

Query params (tous optionnels) :
- `kind` : `star` | `messier` | `planet` | `comet` (en tranche A : seul `star` rend des résultats)
- `search` : LIKE `%search%` sur `name` ou `designation`
- `max_mag` : float, filtre `mag <= max_mag` (NULL exclus)
- `limit` : int, défaut 100, max 500
- `offset` : int, défaut 0

Response :
```json
{
  "objects": [
    {
      "qualified_id": "star:sirius",
      "kind": "star",
      "name": "Sirius",
      "designation": "α CMa",
      "ra_deg": 101.287,
      "dec_deg": -16.716,
      "mag": -1.46,
      "constellation": "Canis Major",
      "object_type": null,
      "angular_size_arcmin": null,
      "extras": {}
    },
    ...
  ],
  "count": 42,
  "limit": 100,
  "offset": 0
}
```

### `GET /catalog/objects/{qualified_id}`

Path : `qualified_id` URL-encoded (`star:sirius`).
- 200 : objet trouvé
- 404 : kind inconnu OU id inconnu

## Error handling

| Cas | Détection | Réponse |
|---|---|---|
| Seed `.sql` cassé au boot | exception `executescript` | Log error, boot continue. Le catalogue de ce kind sera vide tant que le seed n'est pas réparé. |
| Seed `.sql` absent | aucun match du glob | Pas d'erreur, simplement pas de seed appliqué. |
| Kind inconnu en query | `kind=foo` non dans registry | `objects: []` (pas d'erreur — équivalent à "filtre qui ne matche rien"). |
| Qualified ID invalide (pas de `:`) | parse fail dans registry | 404 |
| Qualified ID kind inconnu | `kind` strippé absent du registry | 404 |
| `limit > 500` | validation Pydantic | 422 |
| `max_mag` non-numérique | validation Pydantic | 422 |
| sqlite indisponible | exception aiosqlite | 503 (route catch + log) |

## Testing

### Backend (pytest)

- `test_catalog_seed_runner.py` : applique 2× le même `.sql`, vérifie idempotence (count stable, valeurs replacées). Seed mis à jour (changement valeur) → row mise à jour. Seed cassé → exception loggée, boot continue.
- `test_catalog_sqlite_provider.py` : `list_objects` filtre kind, search, max_mag, limit/offset ; `get_object` raw_id strippé/préfixé correctement, retour None si absent.
- `test_catalog_registry.py` : dispatch par kind, kind absent → liste vide ; `get_by_qualified_id` parse correct + 404 silencieux si kind inconnu.
- `test_catalog_routes.py` : status codes 200/404/422, query params propagés, response shape, limites par défaut.
- `test_catalog_seed_stars.py` (smoke) : applique le `data/seed_stars.sql` réel committé, vérifie que ≥ 50 stars sont chargées et que des entrées clés (Sirius, Vega, Polaris) sont présentes.

### Tooling (manuel)

- `python tools/seed_stars.py --output-dir astro_brain/data/` doit produire un `.sql` non-vide. Re-run produit un `.sql` identique (modulo dates/commentaires).

## Étapes ultérieures (hors tranche A)

- **Tranche A+1 (refactor wizard)** : `_alignment_catalog.load_catalog` lit via `stars_provider.list_objects(max_mag=2.5)`. `_alignment_stars.json` supprimé. Tests existants du wizard adaptés.
- **Tranche `visible_now`** : query param `visible_now=true` injecte une dépendance `SensorsService` dans la route, calcule Az/Alt courant pour chaque objet (réutilise `_alignment_catalog.az_alt_for(...)` extrait au passage), filtre `alt_deg >= alt_min`. Le DTO de réponse est enrichi avec `az_deg_now`/`alt_deg_now`.
- **Tranche Messier** : `tools/seed_messier.py` + `seed_messier.sql` + `registry["messier"] = SqliteCatalogProvider(db, kind="messier")`. Stresse les colonnes `object_type` et `angular_size_arcmin`.
- **Tranche planètes** : ajout dep `skyfield`, BSP DE421s embarqué dans `astro_brain/data/`, `PlanetsProvider` calculant live, `registry["planet"] = PlanetsProvider(loader)`. Aucune migration sqlite.
- **Comètes (Macro 4+)** : table `comets`, `Refresher` MPC périodique, `CometsProvider`.
