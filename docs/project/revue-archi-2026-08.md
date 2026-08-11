# Revue d'architecture — backend Pi + app Flutter (2026-08)

> Revue « casquette architecte » demandée avant de continuer Macro 3 : antipatterns, logique absurde, cohérence, redondances, code mort, concepts douteux, optimisation. Read-only à la production ; les corrections sont pilotées sur la branche `refacto/archi-review` via le plan [`docs/superpowers/plans/2026-08-11-refacto-archi.md`](../superpowers/plans/2026-08-11-refacto-archi.md).

## Verdict de santé

Base mature et bien tenue (≈40 fichiers de tests backend, ≈55 app ; 3 TODO). Math vérifiée terme à terme (Kabsch/SVD, GMST, interpolation) et **portages Dart↔Python fidèles** (interpolation + projection ciel identiques, épinglés par tests). Seuil ports-and-adapters honnête, persistance confinée à un repository layer, **aucune valeur possédée par la monture n'est cachée** (re-fetch live de `_device`, cordwrap/backlash). Discipline BLoC au-dessus de la moyenne (une seule source live `AppBloc`/SSE, config séparée du bus). La revue porte sur l'**affinage**, pas le sauvetage.

### Non-problèmes vérifiés (ne pas y revenir)

Ownership reconnexion monture propre (`_reconnect_lock`) · les 2 chemins de reconnect (SSE vs `/mount/reconnect` INDI) sont volontairement distincts · les 4 fichiers modèles subsystem justifiés · pas d'emit-after-close / async-in-build · frontière local-first cohérente (seuls GoTo/stop vont au Pi).

---

## Décisions d'arbitrage (actées)

- **A1** — But « survivre à un restart sans re-wizard » retenu, **mais via INDI comme source de vérité**, pas via le blob SVD en DB. Fait clé : `astro-brain.service` et `indiserver` sont deux services systemd distincts → un restart backend ne perd pas le modèle d'alignement (il vit dans indiserver). Le `svd_matrix` persisté n'est appliqué à aucune coordonnée (GoTo = modèle natif INDI). **Prérequis** : vérifier sur le Pi si `indi_celestron_aux` expose le nombre de points de sync / présence du modèle en Property lisible.
- **A2** — Position GPS live sortie du bus *santé* vers une source typée dédiée.
- **A3** — `/reference/status` + `/reference/sync` gardées comme endpoints **ops/diagnostic** (documentées `api.md`) ; suppression des DTO/commentaires morts app ; feature « statut référence Pi dans l'app » → **backlog** (protection réelle = garde au moment du GoTo, pas un écran de statut).
- **B3** — `sigma` **calculé** (RMS résidu ellipsoïde), pas retiré.

---

## Checklist des corrections

### Tranche 1 — Code mort + commentaires trompeurs (C + D + nettoyage A3)

**Backend**
- [ ] Table `mount_limits` fantôme (créée `repository/migrations/_001_initial.py:17`, zéro lecture/écriture) → migration forward-only `DROP TABLE`.
- [ ] Helper mort `services/_alignment_solver.py:25-30` `_unit_vec_to_az_alt`.
- [ ] Helpers morts `adapters/_indi_property_helpers.py` `set_number_values:43`, `indi_state_string:70`.
- [ ] `services/_tilt_compensated_heading.py` mal nommé (ne contient que `naive_heading`, « no tilt compensation ») → renommer `_heading.py` + imports.
- [ ] Commentaire `services/interpolation.py:6` « partagé avec le resolver » (faux).
- [ ] Commentaire `routes/alignment.py:222` « 10° » (plancher effectif 20°).
- [ ] `api.md` : documenter `/reference/*` comme ops/diagnostic-only.
- [ ] `backlog.md` : entrée « garde version référence au moment du GoTo (404 id connu → référence Pi périmée) ».

**App**
- [ ] Classe morte `models/calibration.dart:46-73` `Adxl345Offsets` + branche `fromJson` inatteignable (`:221`).
- [ ] `theme/theme_cubit.dart:40-48` `setDay()`/`setNight()` jamais appelés.
- [ ] `models/about.dart:31,50,61` `appVersionSeen` parsé jamais affiché.
- [ ] `features/setup/reference/reference_models.dart` DTO morts `ReferenceStatusDto.fromJson`/`ReferenceSyncResultDto.fromJson` + commentaire « miroir des routes /reference/* ».
- [ ] `features/catalogue/catalogue_models.dart:58` `CatalogObjectDto.fromJson` test-only (garder si un test l'utilise, sinon supprimer).
- [ ] Commentaire `features/catalogue/local/visibility.dart:2` cite `backend/.../catalog/visibility.py` inexistant.
- [ ] Commentaires « port de … » survendus `local_catalogue.dart:2`, `catalogue_providers.dart:2`.
- [ ] Commentaire `catalogue_screen.dart:364-365` `_KindDropdown` « filtrage backend » (c'est local).

### Tranche 2 — Correctness loop + consolidation (B2 + B1 + B4)

- [ ] **B2** — `adapters/lis3mdl_adapter.py` `start/stop/read_raw` sont `async def` mais appellent `write_byte`/`read_bytes` synchrones **sans `to_thread`** → I2C bloquante sur l'event loop (Pi 3B+ mono-cœur). Wrapper en `asyncio.to_thread` (cf. adapter monture, 18×).
- [ ] **B4** — `adapters/mount_indi_adapter.py` : ~10× le bloc `except → logger.exception → publish("mount", state="error")` copié-collé (l.360,411,456,475,505,532,613,648,679,723) → extraire `_publish_error(exc)` / `_publish_mount(state, **details)`.
- [ ] **B1** — `orchestrator.py`, `mount_connection_supervisor.py`, `alignment_invalidator.py` = même boucle `async for _ in bus.subscribe(): react to subsystems["mount"]` → **un** dispatcher mount-state fan-out vers handlers ; supervisor sans état → fonction.

### Tranche 3 — sigma calculé (B3)

- [ ] `services/_ellipsoid_fit.py` : après le fit, calculer RMS des résidus (distance des échantillons corrigés à la sphère unité) → `sigma`.
- [ ] Threader `sigma` dans `services/calibration.py` (init `:70`, reset `:104`, passes `:154,161`) au lieu du `0.0` figé.
- [ ] Vérifier l'affichage `app/lib/features/setup/calibration/calibration_progress.dart:78`.

### Tranche 4 — GPS hors bus santé (A2)

- [ ] Exposer la position GPS live via une source/accesseur typé dédié (pas `bus.get_full_state().subsystems["gps"].details["lat"/"lon"]`).
- [ ] Consommateurs à recâbler : `app.py:96-105` (`_AlignmentSensorsBridge.gps_fix`), `orchestrator.py:57-58` (sync heure/lieu).
- [ ] ADR daté (conflation bus/live).

### Tranche 5 — Alignement : INDI source de vérité (A1) — **bloqué sur vérif Pi**

- [ ] **Prérequis Pi** : lire les Properties de `indi_celestron_aux` — nombre de points de sync / présence du modèle d'alignement.
- [ ] Supprimer calcul SVD backend + persistance `svd_matrix` + `alignment_repo.load()` freshness jamais appelé + `_unit_vec_to_az_alt` (déjà en tranche 1).
- [ ] **Si INDI expose l'état** → `is_aligned` dérivé de l'état mount/INDI au boot + reconnexion ; zéro persistance.
- [ ] **Sinon** → persistance minimale des 3 points (star + timestamp) + **replay** `sync_radec` à la reconnexion, gardé par freshness 12 h / GPS-delta.
- [ ] ADR daté (fin du double modèle de pointage).

### Tranche 6 — Micro-optims (E) — à la carte

- [ ] `overall` recalculé ~4×/publish (`bus.py`).
- [ ] `_ellipsoid_fit.py:149-168` `coverage_pct` reboucle une constante 4³.
- [ ] `widgets/global_dot.dart:30-33` anime en continu même hors pulse (batterie).
- [ ] `SystemScreen` sans `buildWhen`.
- [ ] Boilerplate reconnect SSE dupliqué sur 3 services → helper `SseConnection` partagé (garder les 3 services).
- [ ] `app_bloc.dart` setup souscription dupliqué `_onStarted:26-32` vs `_onReconnect:49-55`.
