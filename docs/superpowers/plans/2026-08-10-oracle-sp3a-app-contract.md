# Oracle SP3-A — Mise à niveau du contrat app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'app Flutter correcte contre le contrat backend SP2 mergé — GoTo par `id` + avertissement solaire, DTO catalogue v2, feedback GoTo non destructif, statut/resync référence, filtres famille + Messier — en restant un client REST online du Pi.

**Architecture:** Aucune infra locale nouvelle (pas de sqflite/drift/download). On étend le client REST existant (`ApiService`), le DTO catalogue, le `CatalogueBloc`/écran, on ajoute un petit `ReferenceRepository` + une tuile Setup + une bannière Catalogue. Les outcomes de GoTo passent par un canal transitoire (champ `gotoOutcome` nullable sur `CatalogueLoaded`, émis-puis-effacé) consommé par un `BlocListener` (SnackBar + dialogue solaire), sans polluer le rendu de la liste.

**Tech Stack:** Flutter, `flutter_bloc` (sealed events/states + `equatable`), `bloc_concurrency`, `http`, `mocktail` + `bloc_test`, `phosphor_flutter`.

## Global Constraints

- **Contrat backend figé** (ne pas modifier le backend). Endpoints : `POST /goto {id, confirm_solar}` ; `GET /catalog/objects` (query `kind?,search?,max_mag?,messier,visible_now,limit,offset`) ; `GET /catalog/objects/{qualified_id}` ; `GET /reference/status` ; `POST /reference/sync`. Détails et table d'erreurs : `docs/superpowers/specs/2026-08-10-oracle-sp3a-app-contract-design.md`.
- **Erreurs GoTo** (`HTTPException.detail`) : `reference_unavailable` (409), `unknown_id` (404), `ephemeris_stale` (409), `not_aligned` (409), `goto_in_progress` (409), `solar_ack_required` (409).
- **Avertissement solaire : server-driven** — l'app envoie toujours `confirm_solar:false` d'abord ; le dialogue solaire n'apparaît que sur `409 solar_ack_required` ; renvoi avec `confirm_solar:true`. Ne jamais coder en dur `kind=='sun'` côté app.
- **Un GoTo rejeté ne doit jamais effacer la liste catalogue.**
- **Pattern BLoC** : events/states `sealed` + `Equatable` ; recherche en `droppable` + debounce 300 ms (existant, ne pas régresser).
- **DI** via `RepositoryProvider`/`BlocProvider` (jamais `get_it`).
- **Thème** : `context.colors` / `context.textStyles` / `DesignTokens` ; double thème jour/nuit. Copie utilisateur en **français**.
- **Tests** miroir 1:1 de `lib` sous `test/` ; `mocktail` + `bloc_test` ; `MockClient` (`package:http/testing.dart`) pour `ApiService` ; MockBloc/mock repo pour les widgets câblés à un bloc async (ne jamais taper un bouton relié à un vrai bloc async).
- **Vérif finale** : `flutter analyze` sans erreur + `flutter test` vert (depuis `app/`).
- **Portée online-only** : aucun cache `reference.sqlite` local, aucune projection alt/az client, aucun night planner, aucune notif — reportés aux slices SP3 suivantes.

---

### Task 1: `ApiService` — propager le `detail` des erreurs

**Files:**
- Modify: `app/lib/services/api_service.dart`
- Test: `app/test/services/api_service_test.dart` (ajouts)

**Interfaces:**
- Consumes: rien (tâche isolée).
- Produces: `ApiException.detail` (`String?`) — la string `detail` du corps JSON `{"detail": "..."}` sur réponse non-200, ou `null` si le corps n'est pas ce JSON. `message` et `statusCode` inchangés. Alimenté par `_post`, `getJson`, `postJson`.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `app/test/services/api_service_test.dart` (nouveau groupe en fin de `main`) :

```dart
  group('ApiException.detail', () {
    test('postJson non-200 avec {"detail": x} peuple detail', () async {
      final client = MockClient(
        (_) async => http.Response('{"detail": "solar_ack_required"}', 409,
            headers: {'content-type': 'application/json'}),
      );
      final api = ApiService(host: host, client: client);
      try {
        await api.postJson('/goto', {'id': 'sun', 'confirm_solar': false});
        fail('devait jeter');
      } on ApiException catch (e) {
        expect(e.statusCode, 409);
        expect(e.detail, 'solar_ack_required');
      }
    });

    test('corps non-JSON → detail null', () async {
      final client = MockClient((_) async => http.Response('oops', 500));
      final api = ApiService(host: host, client: client);
      try {
        await api.getJson('/catalog/objects');
        fail('devait jeter');
      } on ApiException catch (e) {
        expect(e.detail, isNull);
        expect(e.statusCode, 500);
      }
    });
  });
```

- [ ] **Step 2: Lancer le test → échec attendu**

Run: `cd app && flutter test test/services/api_service_test.dart`
Expected: FAIL (`ApiException` n'a pas de champ `detail`).

- [ ] **Step 3: Implémenter**

Dans `app/lib/services/api_service.dart`, étendre `ApiException` :

```dart
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.detail});

  final String message;
  final int? statusCode;

  /// Valeur du champ `detail` du corps JSON d'erreur FastAPI
  /// (`{"detail": "..."}`), ou `null` si le corps n'est pas ce JSON.
  final String? detail;

  @override
  String toString() => 'ApiException($statusCode): $message${detail != null ? ' [$detail]' : ''}';
}
```

Ajouter un helper de niveau fichier (au-dessus de la classe `ApiService`) :

```dart
/// Extrait `detail` d'un corps d'erreur FastAPI (`{"detail": "..."}`).
/// Best-effort : retourne `null` si le corps n'est pas ce JSON.
String? _detailOf(String body) {
  try {
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) {
      final d = decoded['detail'];
      if (d is String) return d;
    }
  } catch (_) {
    // corps non-JSON : pas de detail
  }
  return null;
}
```

Puis, dans `_post`, `getJson` et `postJson`, remplacer chaque
`throw ApiException('… failed', statusCode: resp.statusCode);` par :

```dart
      throw ApiException('POST $path failed',
          statusCode: resp.statusCode, detail: _detailOf(resp.body));
```

(et l'équivalent `GET $path failed` dans `getJson`). Ne pas toucher aux
autres throws (calibration/about) — hors périmètre.

- [ ] **Step 4: Lancer les tests → vert**

Run: `cd app && flutter test test/services/api_service_test.dart`
Expected: PASS (nouveaux + anciens).

- [ ] **Step 5: Commit**

```bash
git add app/lib/services/api_service.dart app/test/services/api_service_test.dart
git commit -m "feat(app): expose FastAPI error detail on ApiException"
```

---

### Task 2: `CatalogObjectDto` — champs v2

**Files:**
- Modify: `app/lib/features/catalogue/catalogue_models.dart`
- Test: `app/test/features/catalogue/catalogue_models_test.dart` (ajouts)

**Interfaces:**
- Consumes: rien.
- Produces: `CatalogObjectDto` gagne `messier` (`String?`), `ngcIc` (`String?`), `illumination` (`double?`), `angularSizeArcmin` (`double?`), `ephemerisStale` (`bool`, défaut `false`). `fromJson` lit les clés `messier`, `ngc_ic`, `illumination`, `angular_size_arcmin`, `ephemeris_stale`. Champs existants inchangés.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `app/test/features/catalogue/catalogue_models_test.dart` :

```dart
  test('fromJson lit les champs v2 (messier/ngc_ic/illumination/size/stale)',
      () {
    final o = CatalogObjectDto.fromJson({
      'qualified_id': 'dso:m31',
      'kind': 'dso',
      'name': 'Andromède',
      'ra_deg': 10.68,
      'dec_deg': 41.27,
      'mag': 3.4,
      'object_type': 'galaxy',
      'angular_size_arcmin': 190.0,
      'messier': 'M31',
      'ngc_ic': 'NGC 224',
      'illumination': null,
      'ephemeris_stale': false,
    });
    expect(o.messier, 'M31');
    expect(o.ngcIc, 'NGC 224');
    expect(o.angularSizeArcmin, 190.0);
    expect(o.illumination, isNull);
    expect(o.ephemerisStale, isFalse);
  });

  test('fromJson : ephemeris_stale absent → false ; moon illumination', () {
    final o = CatalogObjectDto.fromJson({
      'qualified_id': 'moon:moon',
      'kind': 'moon',
      'name': 'Lune',
      'ra_deg': 200.0,
      'dec_deg': -10.0,
      'illumination': 0.42,
    });
    expect(o.ephemerisStale, isFalse);
    expect(o.illumination, 0.42);
  });
```

- [ ] **Step 2: Lancer → échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_models_test.dart`
Expected: FAIL (champs inexistants).

- [ ] **Step 3: Implémenter**

Dans `catalogue_models.dart`, ajouter les champs au constructeur, aux
propriétés, à `fromJson` et à `props` :

```dart
  const CatalogObjectDto({
    required this.qualifiedId,
    required this.kind,
    required this.name,
    required this.raDeg,
    required this.decDeg,
    this.designation,
    this.mag,
    this.constellation,
    this.objectType,
    this.angularSizeArcmin,
    this.messier,
    this.ngcIc,
    this.illumination,
    this.ephemerisStale = false,
    this.altitudeDeg,
    this.azimuthDeg,
  });

  // … champs existants …
  final double? angularSizeArcmin;
  final String? messier;
  final String? ngcIc;
  final double? illumination;
  final bool ephemerisStale;
  // altitudeDeg / azimuthDeg restent
```

`fromJson` — ajouter les lignes :

```dart
        objectType: j['object_type'] as String?,
        angularSizeArcmin: (j['angular_size_arcmin'] as num?)?.toDouble(),
        messier: j['messier'] as String?,
        ngcIc: j['ngc_ic'] as String?,
        illumination: (j['illumination'] as num?)?.toDouble(),
        ephemerisStale: (j['ephemeris_stale'] as bool?) ?? false,
        altitudeDeg: (j['altitude_deg'] as num?)?.toDouble(),
        azimuthDeg: (j['azimuth_deg'] as num?)?.toDouble(),
```

`props` — ajouter `angularSizeArcmin, messier, ngcIc, illumination, ephemerisStale` à la liste.

- [ ] **Step 4: Lancer → vert**

Run: `cd app && flutter test test/features/catalogue/catalogue_models_test.dart`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/catalogue/catalogue_models.dart app/test/features/catalogue/catalogue_models_test.dart
git commit -m "feat(app): add v2 fields to CatalogObjectDto"
```

---

### Task 3: GoTo par `id` + feedback non destructif (SnackBar)

**Files:**
- Modify: `app/lib/features/catalogue/catalogue_repository.dart`
- Modify: `app/lib/features/catalogue/catalogue_event.dart`
- Modify: `app/lib/features/catalogue/catalogue_state.dart`
- Modify: `app/lib/features/catalogue/catalogue_bloc.dart`
- Modify: `app/lib/features/catalogue/widgets/catalogue_detail_sheet.dart`
- Modify: `app/lib/features/catalogue/catalogue_screen.dart`
- Test: `app/test/features/catalogue/catalogue_repository_test.dart` (mise à jour)
- Test: `app/test/features/catalogue/catalogue_bloc_test.dart` (mise à jour)

**Interfaces:**
- Consumes: `ApiException.detail` (Task 1).
- Produces:
  - `CatalogueRepository.goto(String id, {bool confirmSolar = false})` → `POST /goto {id, confirm_solar}`.
  - `GoToRequested(String id, {bool confirmSolar = false})` (remplace `raDeg/decDeg/targetName`).
  - `sealed class GotoOutcome` : `GotoError(String message)` | `GotoSolarAck(String objectId)`.
  - `CatalogueLoaded` gagne `gotoOutcome` (`GotoOutcome?`) + `copyWith(...)`. Émis-puis-effacé (one-shot).
  - Fonction bloc `messageForGotoDetail(String? detail)` → message FR.

> Cette tâche change des signatures utilisées ailleurs (event `GoToRequested`, `repo.goto`) : elle doit laisser l'arbre **compilable et vert**, donc elle met à jour l'appelant (`catalogue_screen.dart` `_openDetail`) et les tests existants dans le même commit. Le cas `solar_ack_required` est mappé en message générique ici ; il sera promu en dialogue à la Task 4.

- [ ] **Step 1: Repository — écrire/mettre à jour le test**

Dans `catalogue_repository_test.dart`, remplacer le test `goto posts ra/dec/target_name` par :

```dart
  test('goto posts {id, confirm_solar}', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    final repo = CatalogueRepository(api: api);
    await repo.goto('star:sirius', confirmSolar: true);
    verify(() => api.postJson(
        '/goto', {'id': 'star:sirius', 'confirm_solar': true})).called(1);
  });

  test('goto défaut confirm_solar=false', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    final repo = CatalogueRepository(api: api);
    await repo.goto('planet:mars');
    verify(() => api.postJson(
        '/goto', {'id': 'planet:mars', 'confirm_solar': false})).called(1);
  });
```

- [ ] **Step 2: Lancer → échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_repository_test.dart`
Expected: FAIL (signature `goto` incompatible).

- [ ] **Step 3: Repository — implémenter**

Dans `catalogue_repository.dart`, remplacer la méthode `goto` :

```dart
  /// POST /goto — pointe la monture sur l'objet identifié par [id].
  /// [confirmSolar] à `true` acquitte l'avertissement solaire (cf. flux
  /// server-driven : n'est envoyé qu'après un 409 `solar_ack_required`).
  Future<void> goto(String id, {bool confirmSolar = false}) async {
    await api.postJson('/goto', {'id': id, 'confirm_solar': confirmSolar});
  }
```

- [ ] **Step 4: Event — implémenter**

Dans `catalogue_event.dart`, remplacer `GoToRequested` :

```dart
class GoToRequested extends CatalogueEvent {
  const GoToRequested(this.id, {this.confirmSolar = false});
  final String id;
  final bool confirmSolar;
  @override
  List<Object?> get props => [id, confirmSolar];
}
```

- [ ] **Step 5: State — ajouter `GotoOutcome` + `gotoOutcome` + `copyWith`**

Dans `catalogue_state.dart`, ajouter en haut (après les imports) :

```dart
/// Résultat transitoire (one-shot) d'un GoTo, consommé par un BlocListener.
sealed class GotoOutcome extends Equatable {
  const GotoOutcome();
  @override
  List<Object?> get props => [];
}

/// GoTo rejeté : message FR à afficher (SnackBar). N'efface pas la liste.
class GotoError extends GotoOutcome {
  const GotoError(this.message);
  final String message;
  @override
  List<Object?> get props => [message];
}

/// Le backend exige un acquittement solaire (409 solar_ack_required) pour
/// l'objet [objectId]. Déclenche le dialogue d'avertissement (Task 4).
class GotoSolarAck extends GotoOutcome {
  const GotoSolarAck(this.objectId);
  final String objectId;
  @override
  List<Object?> get props => [objectId];
}
```

Modifier `CatalogueLoaded` pour porter le champ + `copyWith` :

```dart
class CatalogueLoaded extends CatalogueState {
  const CatalogueLoaded({
    required this.objects,
    required this.filters,
    this.availableConstellations = const [],
    this.gotoOutcome,
  });

  final List<CatalogObjectDto> objects;
  final CatalogueFilters filters;
  final List<String> availableConstellations;

  /// Outcome transitoire d'un GoTo (SnackBar / dialogue), `null` au repos.
  final GotoOutcome? gotoOutcome;

  CatalogueLoaded copyWith({
    List<CatalogObjectDto>? objects,
    CatalogueFilters? filters,
    List<String>? availableConstellations,
    GotoOutcome? gotoOutcome,
    bool clearOutcome = false,
  }) =>
      CatalogueLoaded(
        objects: objects ?? this.objects,
        filters: filters ?? this.filters,
        availableConstellations:
            availableConstellations ?? this.availableConstellations,
        gotoOutcome: clearOutcome ? null : (gotoOutcome ?? this.gotoOutcome),
      );

  @override
  List<Object?> get props =>
      [objects, filters, availableConstellations, gotoOutcome];
}
```

- [ ] **Step 6: Bloc — écrire/mettre à jour les tests**

Dans `catalogue_bloc_test.dart` : supprimer les 2 anciens tests GoTo
(`GoToRequested calls repo.goto` et `GoToRequested failure → CatalogueError`)
et ajouter (le mock `goto` a désormais un named arg `confirmSolar`) :

```dart
  blocTest<CatalogueBloc, CatalogueState>(
    'GoTo OK → aucun CatalogueError, liste préservée',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      when(() => repo.goto(any(), confirmSolar: any(named: 'confirmSolar')))
          .thenAnswer((_) async {});
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const GoToRequested('star:vega'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>(),
    ],
    verify: (_) => verify(
        () => repo.goto('star:vega', confirmSolar: false)).called(1),
  );

  blocTest<CatalogueBloc, CatalogueState>(
    'GoTo not_aligned → GotoError, liste préservée',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      when(() => repo.goto(any(), confirmSolar: any(named: 'confirmSolar')))
          .thenThrow(ApiException('POST /goto failed',
              statusCode: 409, detail: 'not_aligned'));
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const GoToRequested('star:vega'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>().having((s) => s.gotoOutcome, 'outcome', isNull),
      isA<CatalogueLoaded>().having(
          (s) => (s.gotoOutcome as GotoError?)?.message,
          'msg',
          contains('non alignée')),
      isA<CatalogueLoaded>().having((s) => s.gotoOutcome, 'cleared', isNull),
    ],
  );
```

Ajouter l'import : `import 'package:astro_brain/services/api_service.dart';`

- [ ] **Step 7: Bloc — implémenter le mapping + le canal transitoire**

Dans `catalogue_bloc.dart`, ajouter la fonction de mapping (niveau fichier) :

```dart
/// Traduit le `detail` d'une erreur GoTo backend en message FR.
/// `solar_ack_required` n'a pas de message : il déclenche le dialogue.
String messageForGotoDetail(String? detail) => switch (detail) {
      'reference_unavailable' =>
        'Almanach indisponible — lance une resynchronisation dans Réglages.',
      'ephemeris_stale' => 'Éphémérides périmées pour cet objet.',
      'not_aligned' => 'Monture non alignée — aligne d\'abord.',
      'goto_in_progress' => 'Un GoTo est déjà en cours.',
      'unknown_id' => 'Objet introuvable côté monture.',
      _ => 'GoTo impossible.',
    };
```

Remplacer `_onGoTo` :

```dart
  Future<void> _onGoTo(GoToRequested e, Emitter<CatalogueState> emit) async {
    final current = state;
    if (current is! CatalogueLoaded) return;
    try {
      await repo.goto(e.id, confirmSolar: e.confirmSolar);
    } on ApiException catch (err) {
      // solar_ack_required est intercepté à la Task 4 ; ici → message générique.
      emit(current.copyWith(gotoOutcome: GotoError(
          messageForGotoDetail(err.detail))));
      emit(current.copyWith(clearOutcome: true));
    } catch (_) {
      emit(current.copyWith(gotoOutcome: const GotoError('GoTo impossible.')));
      emit(current.copyWith(clearOutcome: true));
    }
  }
```

Ajouter l'import : `import '../../services/api_service.dart';`

- [ ] **Step 8: UI — détail sheet + écran (id + SnackBar), sans casser la compile**

Dans `catalogue_screen.dart`, `_openDetail`, remplacer le `onGoto` :

```dart
        onGoto: () => bloc.add(GoToRequested(obj.qualifiedId)),
```

Envelopper le corps de la page dans un `BlocListener` pour le SnackBar.
Remplacer le `child: SafeArea( … Column …)` du `build` de
`_CatalogueScreenState` par un `BlocListener` autour du `Column` :

```dart
        child: SafeArea(
          child: BlocListener<CatalogueBloc, CatalogueState>(
            listenWhen: (p, c) =>
                c is CatalogueLoaded && c.gotoOutcome is GotoError,
            listener: (ctx, state) {
              final outcome = (state as CatalogueLoaded).gotoOutcome as GotoError;
              ScaffoldMessenger.of(ctx).showSnackBar(
                SnackBar(content: Text(outcome.message)),
              );
            },
            child: Column(
              children: const [
                AstroAppBar(current: AstroScreen.catalogue),
                _NotAlignedBanner(),
                _Filters(),
                Expanded(child: _ObjectList()),
                _SlewBarSlot(),
              ],
            ),
          ),
        ),
```

(Le `Scaffold` fournit déjà le `ScaffoldMessenger`.)

- [ ] **Step 9: Lancer les tests catalogue → vert**

Run: `cd app && flutter test test/features/catalogue/`
Expected: PASS. Puis `cd app && flutter analyze` → aucune erreur.

- [ ] **Step 10: Commit**

```bash
git add app/lib/features/catalogue app/test/features/catalogue
git commit -m "feat(app): GoTo by id + non-destructive goto feedback"
```

---

### Task 4: Flux d'avertissement solaire (dialogue + renvoi)

**Files:**
- Create: `app/lib/features/catalogue/widgets/solar_warning_dialog.dart`
- Modify: `app/lib/features/catalogue/catalogue_bloc.dart`
- Modify: `app/lib/features/catalogue/catalogue_screen.dart`
- Test: `app/test/features/catalogue/catalogue_bloc_test.dart` (ajout)
- Test: `app/test/features/catalogue/solar_warning_dialog_test.dart` (create)

**Interfaces:**
- Consumes: `GotoSolarAck` (Task 3), `GoToRequested(id, confirmSolar:true)`.
- Produces: `showSolarWarningDialog(BuildContext) → Future<bool>` (true = confirmer). Le bloc intercepte `detail == 'solar_ack_required'` et émet `GotoSolarAck(id)` au lieu d'un `GotoError`.

- [ ] **Step 1: Bloc — écrire le test du cas solaire**

Ajouter dans `catalogue_bloc_test.dart` :

```dart
  blocTest<CatalogueBloc, CatalogueState>(
    'GoTo solar_ack_required → GotoSolarAck(id)',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow')))
          .thenAnswer((_) async => [_vega()]);
      when(() => repo.goto(any(), confirmSolar: any(named: 'confirmSolar')))
          .thenThrow(ApiException('POST /goto failed',
              statusCode: 409, detail: 'solar_ack_required'));
      return CatalogueBloc(repo: repo);
    },
    act: (b) async {
      b.add(const CatalogueOpened());
      await Future<void>.delayed(const Duration(milliseconds: 10));
      b.add(const GoToRequested('sun:sun'));
    },
    expect: () => [
      isA<CatalogueLoading>(),
      isA<CatalogueLoaded>(),
      isA<CatalogueLoaded>().having(
          (s) => (s.gotoOutcome as GotoSolarAck?)?.objectId, 'id', 'sun:sun'),
      isA<CatalogueLoaded>().having((s) => s.gotoOutcome, 'cleared', isNull),
    ],
  );
```

- [ ] **Step 2: Lancer → échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_bloc_test.dart`
Expected: FAIL (le bloc émet `GotoError`, pas `GotoSolarAck`).

- [ ] **Step 3: Bloc — intercepter `solar_ack_required`**

Dans `_onGoTo` (`catalogue_bloc.dart`), dans le `on ApiException catch (err)`,
insérer avant le mapping générique :

```dart
    } on ApiException catch (err) {
      if (err.detail == 'solar_ack_required') {
        emit(current.copyWith(gotoOutcome: GotoSolarAck(e.id)));
        emit(current.copyWith(clearOutcome: true));
        return;
      }
      emit(current.copyWith(gotoOutcome: GotoError(
          messageForGotoDetail(err.detail))));
      emit(current.copyWith(clearOutcome: true));
    }
```

- [ ] **Step 4: Lancer le test bloc → vert**

Run: `cd app && flutter test test/features/catalogue/catalogue_bloc_test.dart`
Expected: PASS.

- [ ] **Step 5: Dialogue — écrire le test widget**

Créer `app/test/features/catalogue/solar_warning_dialog_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/widgets/solar_warning_dialog.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

ThemeData _theme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

void main() {
  testWidgets('confirmer retourne true', (tester) async {
    late Future<bool> result;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Builder(
        builder: (ctx) => ElevatedButton(
          onPressed: () => result = showSolarWarningDialog(ctx),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Soleil'), findsWidgets);
    await tester.tap(find.text('POINTER QUAND MÊME'));
    await tester.pumpAndSettle();
    expect(await result, isTrue);
  });

  testWidgets('annuler retourne false', (tester) async {
    late Future<bool> result;
    await tester.pumpWidget(MaterialApp(
      theme: _theme(),
      home: Builder(
        builder: (ctx) => ElevatedButton(
          onPressed: () => result = showSolarWarningDialog(ctx),
          child: const Text('open'),
        ),
      ),
    ));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('ANNULER'));
    await tester.pumpAndSettle();
    expect(await result, isFalse);
  });
}
```

- [ ] **Step 6: Dialogue — implémenter**

Créer `app/lib/features/catalogue/widgets/solar_warning_dialog.dart` :

```dart
import 'package:flutter/material.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';

/// Dialogue d'avertissement avant un GoTo sur le Soleil. Retourne `true`
/// si l'utilisateur confirme (→ renvoi du GoTo avec `confirm_solar: true`),
/// `false` sinon. Politique décidée côté backend (server-driven) ; ce
/// dialogue est purement l'acquittement humain du danger.
Future<bool> showSolarWarningDialog(BuildContext context) async {
  final colors = context.colors;
  final text = context.textStyles;
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: colors.bgGradientBottom,
      title: Text('⚠ Pointage vers le Soleil',
          style: text.hudValue.copyWith(color: colors.dotWarn)),
      content: Text(
        'Pointer le télescope vers le Soleil sans filtre solaire adapté '
        'peut détruire l\'instrument et causer des lésions oculaires '
        'irréversibles. Ne confirme que si tu sais ce que tu fais.',
        style: text.hudCaption.copyWith(color: colors.textPrimary),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: const Text('ANNULER'),
        ),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: colors.dotWarn),
          onPressed: () => Navigator.of(ctx).pop(true),
          child: const Text('POINTER QUAND MÊME'),
        ),
      ],
    ),
  );
  return confirmed ?? false;
}
```

- [ ] **Step 7: Écran — brancher le dialogue sur `GotoSolarAck`**

Dans `catalogue_screen.dart`, étendre le `BlocListener` (Task 3) pour couvrir
aussi `GotoSolarAck`. Remplacer `listenWhen`/`listener` par :

```dart
            listenWhen: (p, c) =>
                c is CatalogueLoaded && c.gotoOutcome != null,
            listener: (ctx, state) async {
              final outcome = (state as CatalogueLoaded).gotoOutcome;
              switch (outcome) {
                case GotoError(:final message):
                  ScaffoldMessenger.of(ctx)
                      .showSnackBar(SnackBar(content: Text(message)));
                case GotoSolarAck(:final objectId):
                  final confirmed = await showSolarWarningDialog(ctx);
                  if (confirmed && ctx.mounted) {
                    ctx.read<CatalogueBloc>().add(
                        GoToRequested(objectId, confirmSolar: true));
                  }
                case null:
                  break;
              }
            },
```

Ajouter l'import : `import 'widgets/solar_warning_dialog.dart';`

- [ ] **Step 8: Lancer les tests catalogue + analyze → vert**

Run: `cd app && flutter test test/features/catalogue/ && flutter analyze`
Expected: PASS, aucune erreur d'analyse.

- [ ] **Step 9: Commit**

```bash
git add app/lib/features/catalogue app/test/features/catalogue
git commit -m "feat(app): server-driven solar-ack GoTo dialog flow"
```

---

### Task 5: `ReferenceRepository` + DTOs

**Files:**
- Create: `app/lib/features/setup/reference/reference_models.dart`
- Create: `app/lib/features/setup/reference/reference_repository.dart`
- Test: `app/test/features/setup/reference/reference_repository_test.dart`

**Interfaces:**
- Consumes: `ApiService.getJson` / `postJson`.
- Produces:
  - `ReferenceStatusDto` : `ready` (bool), `schemaVersion` (`int?`), `generatedAt` (`String?`), `windowStart` (`String?`), `windowEnd` (`String?`) ; `fromJson`.
  - `ReferenceSyncResultDto` : `status` (String), `schemaVersion` (`int?`) ; `fromJson`.
  - `ReferenceRepository({required ApiService api})` : `Future<ReferenceStatusDto> getStatus()` (GET /reference/status) ; `Future<ReferenceSyncResultDto> sync()` (POST /reference/sync).

- [ ] **Step 1: Écrire le test qui échoue**

Créer `app/test/features/setup/reference/reference_repository_test.dart` :

```dart
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

void main() {
  late _MockApi api;
  setUp(() => api = _MockApi());

  test('getStatus parse ready + fenêtre', () async {
    when(() => api.getJson(any())).thenAnswer((_) async => {
          'ready': true,
          'schema_version': 2,
          'generated_at': '2026-08-01T00:00:00+00:00',
          'window_start': '2026-08-01',
          'window_end': '2026-09-30',
        });
    final repo = ReferenceRepository(api: api);
    final s = await repo.getStatus();
    expect(s.ready, isTrue);
    expect(s.schemaVersion, 2);
    expect(s.windowEnd, '2026-09-30');
    verify(() => api.getJson('/reference/status')).called(1);
  });

  test('getStatus ready:false minimal', () async {
    when(() => api.getJson(any())).thenAnswer((_) async => {'ready': false});
    final repo = ReferenceRepository(api: api);
    final s = await repo.getStatus();
    expect(s.ready, isFalse);
    expect(s.generatedAt, isNull);
  });

  test('sync parse status', () async {
    when(() => api.postJson(any(), any()))
        .thenAnswer((_) async => {'status': 'updated', 'schema_version': 2});
    final repo = ReferenceRepository(api: api);
    final r = await repo.sync();
    expect(r.status, 'updated');
    verify(() => api.postJson('/reference/sync', const {})).called(1);
  });
}
```

- [ ] **Step 2: Lancer → échec**

Run: `cd app && flutter test test/features/setup/reference/reference_repository_test.dart`
Expected: FAIL (fichiers inexistants).

- [ ] **Step 3: Implémenter les DTOs**

Créer `app/lib/features/setup/reference/reference_models.dart` :

```dart
/// DTOs miroir des routes `/reference/*` du backend
/// (`backend/astro_brain/routes/reference.py`).
library;

import 'package:equatable/equatable.dart';

class ReferenceStatusDto extends Equatable {
  const ReferenceStatusDto({
    required this.ready,
    this.schemaVersion,
    this.generatedAt,
    this.windowStart,
    this.windowEnd,
  });

  final bool ready;
  final int? schemaVersion;
  final String? generatedAt;
  final String? windowStart;
  final String? windowEnd;

  factory ReferenceStatusDto.fromJson(Map<String, dynamic> j) =>
      ReferenceStatusDto(
        ready: j['ready'] as bool? ?? false,
        schemaVersion: j['schema_version'] as int?,
        generatedAt: j['generated_at'] as String?,
        windowStart: j['window_start'] as String?,
        windowEnd: j['window_end'] as String?,
      );

  @override
  List<Object?> get props =>
      [ready, schemaVersion, generatedAt, windowStart, windowEnd];
}

class ReferenceSyncResultDto extends Equatable {
  const ReferenceSyncResultDto({required this.status, this.schemaVersion});

  final String status;
  final int? schemaVersion;

  factory ReferenceSyncResultDto.fromJson(Map<String, dynamic> j) =>
      ReferenceSyncResultDto(
        status: j['status'] as String? ?? 'unknown',
        schemaVersion: j['schema_version'] as int?,
      );

  @override
  List<Object?> get props => [status, schemaVersion];
}
```

- [ ] **Step 4: Implémenter le repository**

Créer `app/lib/features/setup/reference/reference_repository.dart` :

```dart
import '../../../services/api_service.dart';
import 'reference_models.dart';

/// Façade REST sur les routes `/reference/*` (statut + resync de l'almanach).
class ReferenceRepository {
  ReferenceRepository({required this.api});

  final ApiService api;

  Future<ReferenceStatusDto> getStatus() async {
    final j = await api.getJson('/reference/status');
    return ReferenceStatusDto.fromJson(j);
  }

  Future<ReferenceSyncResultDto> sync() async {
    final j = await api.postJson('/reference/sync', const {});
    return ReferenceSyncResultDto.fromJson(j);
  }
}
```

- [ ] **Step 5: Lancer → vert**

Run: `cd app && flutter test test/features/setup/reference/reference_repository_test.dart`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/setup/reference app/test/features/setup/reference
git commit -m "feat(app): ReferenceRepository + DTOs for /reference status & sync"
```

---

### Task 6: UI référence — tuile Setup + bannière Catalogue + DI

**Files:**
- Modify: `app/lib/app.dart` (RepositoryProvider `ReferenceRepository`)
- Modify: `app/lib/features/setup/setup_screen.dart` (tuile Almanach, index 6)
- Create: `app/lib/features/catalogue/widgets/reference_banner.dart`
- Modify: `app/lib/features/catalogue/catalogue_screen.dart` (insertion bannière)
- Test: `app/test/features/catalogue/reference_banner_test.dart` (create)
- Test: `app/test/features/setup/setup_screen_test.dart` (create ou ajout si existe)

**Interfaces:**
- Consumes: `ReferenceRepository` (Task 5) via `context.read<ReferenceRepository>()`.
- Produces: `ReferenceBanner` (widget) — bandeau visible **uniquement** quand le backend répond `ready == false` ; masqué si `ready == true` **ou** si l'appel échoue (Pi injoignable → l'indicateur global gère l'offline, pas de faux « indisponible »). Tuile Setup « ALMANACH » (index 6). `SetupScreen` : `itemCount` passe à 6, `_cardForIndex` gère `6`.

- [ ] **Step 1: DI — enregistrer `ReferenceRepository`**

Dans `app/lib/app.dart`, ajouter dans `MultiRepositoryProvider.providers`
(après `ApiService`) :

```dart
        RepositoryProvider<ReferenceRepository>(
          create: (ctx) =>
              ReferenceRepository(api: ctx.read<ApiService>()),
        ),
```

Ajouter l'import :
`import 'features/setup/reference/reference_repository.dart';`

- [ ] **Step 2: Bannière — écrire le test widget**

Créer `app/test/features/catalogue/reference_banner_test.dart` :

```dart
import 'package:astro_brain/features/catalogue/widgets/reference_banner.dart';
import 'package:astro_brain/features/setup/reference/reference_models.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}

class _FakeRepo extends ReferenceRepository {
  _FakeRepo(this._status) : super(api: _MockApi());
  final ReferenceStatusDto? _status;
  @override
  Future<ReferenceStatusDto> getStatus() async {
    if (_status == null) throw ApiException('offline');
    return _status;
  }
}

ThemeData _theme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

Widget _wrap(ReferenceRepository repo) => RepositoryProvider.value(
      value: repo,
      child: MaterialApp(theme: _theme(), home: const Scaffold(body: ReferenceBanner())),
    );

void main() {
  testWidgets('ready:false → bannière visible', (tester) async {
    await tester.pumpWidget(
        _wrap(_FakeRepo(const ReferenceStatusDto(ready: false))));
    await tester.pumpAndSettle();
    expect(find.textContaining('Almanach indisponible'), findsOneWidget);
  });

  testWidgets('ready:true → rien', (tester) async {
    await tester.pumpWidget(
        _wrap(_FakeRepo(const ReferenceStatusDto(ready: true))));
    await tester.pumpAndSettle();
    expect(find.textContaining('Almanach'), findsNothing);
  });

  testWidgets('backend injoignable → pas de faux bandeau', (tester) async {
    await tester.pumpWidget(_wrap(_FakeRepo(null)));
    await tester.pumpAndSettle();
    expect(find.textContaining('Almanach indisponible'), findsNothing);
  });
}
```

- [ ] **Step 3: Bannière — implémenter**

Créer `app/lib/features/catalogue/widgets/reference_banner.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../setup/reference/reference_models.dart';
import '../../setup/reference/reference_repository.dart';

/// Bandeau affiché quand l'almanach de référence n'est pas prêt côté backend
/// (`ready == false`) : dans ce cas GoTo et catalogue sont hors service.
/// Masqué si l'almanach est prêt, ou si le Pi est injoignable (l'offline est
/// géré par l'indicateur global — on n'affiche pas de faux « indisponible »).
class ReferenceBanner extends StatelessWidget {
  const ReferenceBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return FutureBuilder<ReferenceStatusDto>(
      future: context.read<ReferenceRepository>().getStatus(),
      builder: (ctx, snap) {
        // Pas de donnée exploitable (chargement ou erreur réseau) → rien.
        if (!snap.hasData || snap.data!.ready) return const SizedBox.shrink();
        return Container(
          margin: const EdgeInsets.all(DesignTokens.spaceMD),
          padding: const EdgeInsets.all(DesignTokens.spaceMD),
          decoration: BoxDecoration(
            color: colors.dotWarn.withValues(alpha: 0.1),
            border: Border.all(color: colors.dotWarn.withValues(alpha: 0.4)),
            borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
          ),
          child: Text(
            'Almanach indisponible — pointage et catalogue hors service. '
            'Resynchronise dans Réglages → Almanach.',
            style: text.hudCaption.copyWith(color: colors.dotWarn),
          ),
        );
      },
    );
  }
}
```

- [ ] **Step 4: Insérer la bannière dans l'écran catalogue**

Dans `catalogue_screen.dart`, ajouter `const ReferenceBanner(),` dans le
`Column` (juste après `AstroAppBar`, avant `_NotAlignedBanner`) et l'import
`import 'widgets/reference_banner.dart';`.

- [ ] **Step 5: Tuile Setup Almanach — écrire le test**

Créer `app/test/features/setup/setup_screen_test.dart` (wrap minimal fournissant
`ApiService`, `ReferenceRepository`, `AppBloc`, `ThemeCubit`) — mock
`getStatus`/`getCalibrationStatus` :

```dart
import 'package:astro_brain/features/setup/reference/reference_models.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/features/setup/setup_screen.dart';
import 'package:astro_brain/models/calibration.dart';
import 'package:astro_brain/models/system_state.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:astro_brain/services/event_stream_service.dart';
import 'package:astro_brain/state/app_bloc/app_bloc.dart';
import 'package:astro_brain/theme/app_colors.dart';
import 'package:astro_brain/theme/app_typography.dart';
import 'package:astro_brain/theme/theme_cubit.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _MockApi extends Mock implements ApiService {}
class _MockStream extends Mock implements EventStreamService {}
class _MockRefRepo extends Mock implements ReferenceRepository {}

ThemeData _theme() {
  const color = AppColors.day;
  final styles = AppTextStyles(
    hudLabel: TextStyle(color: color.textPrimary),
    hudValue: TextStyle(color: color.textPrimary),
    hudCaption: TextStyle(color: color.textPrimary),
    hudBadge: TextStyle(color: color.textPrimary),
  );
  return ThemeData(extensions: <ThemeExtension<dynamic>>[color, styles]);
}

void main() {
  testWidgets('tuile ALMANACH affiche la fenêtre couverte', (tester) async {
    final api = _MockApi();
    when(() => api.getCalibrationStatus(any())).thenAnswer(
        (_) async => const CalibrationStatus(sensorId: 'lis3mdl'));
    final refRepo = _MockRefRepo();
    when(() => refRepo.getStatus()).thenAnswer((_) async =>
        const ReferenceStatusDto(
            ready: true,
            generatedAt: '2026-08-01T00:00:00+00:00',
            windowStart: '2026-08-01',
            windowEnd: '2026-09-30'));
    final stream = _MockStream();
    when(() => stream.stream)
        .thenAnswer((_) => const Stream<SystemState>.empty());
    when(() => stream.start()).thenAnswer((_) {});
    when(() => stream.stop()).thenAnswer((_) async {});
    when(() => stream.dispose()).thenAnswer((_) async {});
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(MultiRepositoryProvider(
      providers: [
        RepositoryProvider<ApiService>.value(value: api),
        RepositoryProvider<ReferenceRepository>.value(value: refRepo),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider<AppBloc>(create: (_) => AppBloc(eventStream: stream)),
          BlocProvider<ThemeCubit>(create: (_) => ThemeCubit(prefs: prefs)),
        ],
        child: MaterialApp(theme: _theme(), home: const SetupScreen()),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('ALMANACH'), findsOneWidget);
    expect(find.textContaining('2026-09-30'), findsOneWidget);
  });
}
```

> Si `CalibrationStatus` n'a pas de constructeur `const CalibrationStatus(sensorId: ...)` avec `payload`/`calibratedAt` nullables, adapter l'instanciation du mock au constructeur réel (le lire dans `app/lib/models/calibration.dart`). L'objectif du test est la tuile ALMANACH, pas la carte compass.

- [ ] **Step 6: Tuile Setup Almanach — implémenter**

Dans `setup_screen.dart` :
- passer `itemCount: 5` → `itemCount: 6` dans le `ListView.separated`.
- ajouter un builder de carte Almanach et le brancher dans `_cardForIndex`.

Ajouter la méthode (dans `_SetupScreenState`) :

```dart
  Widget _buildAlmanacCard() {
    return FutureBuilder<ReferenceStatusDto>(
      future: context.read<ReferenceRepository>().getStatus(),
      builder: (ctx, snap) {
        final data = snap.data;
        final ready = data?.ready ?? false;
        final sublabel = data == null
            ? '—'
            : ready
                ? 'Couvre ${data.windowStart ?? '?'} → ${data.windowEnd ?? '?'}'
                : 'Indisponible — resynchroniser';
        final dot = ready ? OverallStatus.green : OverallStatus.gray;
        return SetupCard(
          index: 6,
          icon: PhosphorIconsBold.database,
          label: 'ALMANACH',
          sublabel: sublabel,
          dotStatus: dot,
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const AlmanacScreen()),
          ),
        );
      },
    );
  }
```

Et dans `_cardForIndex`, ajouter le cas `6 => _buildAlmanacCard(),` (avant le
`_ =>`), et corriger le message du `RangeError` en `'index $n hors plage 1–6'`.

> `AlmanacScreen` : écran de détail avec bouton « Resynchroniser ». Créer
> `app/lib/features/setup/reference/almanac_screen.dart` (Stateful) : affiche
> `generatedAt` / fenêtre via un `FutureBuilder<ReferenceStatusDto>` (clé
> incrémentée pour refetch), + un bouton qui appelle
> `context.read<ReferenceRepository>().sync()` puis `setState` pour relire le
> statut, avec un SnackBar du `status` retourné. Suivre le style HUD existant
> (AstroAppBar, `context.colors`, `DesignTokens`, `HudPanel`). Import à ajouter
> dans `setup_screen.dart` : `import 'reference/almanac_screen.dart';` et
> `import 'reference/reference_models.dart';` + `reference_repository.dart`.

Code de `almanac_screen.dart` :

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../theme/app_colors.dart';
import '../../../theme/app_typography.dart';
import '../../../theme/design_tokens.dart';
import '../../../widgets/astro_app_bar.dart';
import 'reference_models.dart';
import 'reference_repository.dart';

/// Détail « Almanach » : fraîcheur + fenêtre couverte + resynchronisation.
class AlmanacScreen extends StatefulWidget {
  const AlmanacScreen({super.key});
  @override
  State<AlmanacScreen> createState() => _AlmanacScreenState();
}

class _AlmanacScreenState extends State<AlmanacScreen> {
  int _refresh = 0;
  bool _syncing = false;

  Future<void> _sync() async {
    setState(() => _syncing = true);
    try {
      final r = await context.read<ReferenceRepository>().sync();
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Sync : ${r.status}')));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Resynchronisation impossible.')));
    } finally {
      if (mounted) setState(() {
        _syncing = false;
        _refresh++;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bgGradientTop, colors.bgGradientBottom],
          ),
        ),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const AstroAppBar(current: AstroScreen.setup),
              Padding(
                padding: const EdgeInsets.all(DesignTokens.spaceLG),
                child: FutureBuilder<ReferenceStatusDto>(
                  key: ValueKey(_refresh),
                  future: context.read<ReferenceRepository>().getStatus(),
                  builder: (ctx, snap) {
                    final d = snap.data;
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ALMANACH', style: text.hudLabel),
                        const SizedBox(height: DesignTokens.spaceMD),
                        Text(
                          d == null
                              ? '—'
                              : d.ready
                                  ? 'Prêt · généré le ${d.generatedAt ?? '?'}\n'
                                      'Couvre ${d.windowStart ?? '?'} → ${d.windowEnd ?? '?'}'
                                  : 'Indisponible',
                          style: text.hudValue
                              .copyWith(color: colors.textPrimary),
                        ),
                        const SizedBox(height: DesignTokens.spaceLG),
                        FilledButton(
                          onPressed: _syncing ? null : _sync,
                          child: Text(_syncing
                              ? 'RESYNCHRONISATION…'
                              : 'RESYNCHRONISER'),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 7: Lancer les tests + analyze → vert**

Run: `cd app && flutter test test/features/catalogue/reference_banner_test.dart test/features/setup/ && flutter analyze`
Expected: PASS. (Vérifier l'icône `PhosphorIconsBold.database` — si absente dans la version du package, prendre une icône proche existante, ex. `PhosphorIconsBold.hardDrives`.)

- [ ] **Step 8: Commit**

```bash
git add app/lib/app.dart app/lib/features/setup app/lib/features/catalogue app/test/features
git commit -m "feat(app): reference status banner + Setup almanac tile & resync"
```

---

### Task 7: Catalogue A-lite+ — filtres famille (`kind`) + Messier + copie

**Files:**
- Modify: `app/lib/features/catalogue/catalogue_repository.dart` (params `kind`, `messier`)
- Modify: `app/lib/features/catalogue/catalogue_event.dart` (`KindFilterChanged`, `MessierToggled`)
- Modify: `app/lib/features/catalogue/catalogue_state.dart` (`CatalogueFilters.kind`, `.messierOnly`)
- Modify: `app/lib/features/catalogue/catalogue_bloc.dart` (handlers + `_query`)
- Modify: `app/lib/features/catalogue/catalogue_screen.dart` (sélecteur famille + chip Messier + copie)
- Test: `app/test/features/catalogue/catalogue_repository_test.dart` (mise à jour)
- Test: `app/test/features/catalogue/catalogue_bloc_test.dart` (mise à jour stubs + ajouts)
- Test: `app/test/features/catalogue/catalogue_screen_test.dart` (mise à jour stub `listObjects`)

**Interfaces:**
- Consumes: contrat `GET /catalog/objects` (query `kind`, `messier`).
- Produces:
  - `CatalogueRepository.listObjects({String? search, double? maxMag, bool visibleNow, String? kind, bool messier})` — ajoute `kind` et `messier` (`messier` envoyé seulement si `true`).
  - `CatalogueFilters` gagne `kind` (`String?`, `null` = toutes familles) + `messierOnly` (`bool`, défaut `false`) ; `copyWith` étendu (`clearKind`).
  - Events `KindFilterChanged(String? kind)`, `MessierToggled(bool enabled)`.
  - `kCatalogKinds` : map ordonnée `kind → libellé FR` (`{'planet':'Planètes', 'moon':'Lune', 'sun':'Soleil', 'comet':'Comètes', 'dso':'Ciel profond', 'star':'Étoiles'}`).

> Cette tâche change la signature de `listObjects` (nouveaux named params) : les **stubs mocktail existants** (`catalogue_bloc_test.dart`, `catalogue_screen_test.dart`) qui ne matchent que `search/maxMag/visibleNow` doivent ajouter `kind: any(named:'kind'), messier: any(named:'messier')`, sinon les appels du bloc (qui passent désormais ces args) ne matchent plus.

- [ ] **Step 1: Repository — mettre à jour le test**

Dans `catalogue_repository_test.dart`, remplacer le test `listObjects passes query params …` pour couvrir `kind`/`messier` :

```dart
  test('listObjects passe kind + messier + params existants', () async {
    when(() => api.getJson(any(), query: any(named: 'query')))
        .thenAnswer((_) async => {'objects': [], 'count': 0, 'limit': 500, 'offset': 0});
    final repo = CatalogueRepository(api: api);
    await repo.listObjects(
        search: 'm', maxMag: 6.0, visibleNow: true, kind: 'dso', messier: true);
    final captured = verify(() => api.getJson(captureAny(),
        query: captureAny(named: 'query'))).captured;
    expect(captured[0], '/catalog/objects');
    final q = captured[1] as Map<String, String>;
    expect(q['kind'], 'dso');
    expect(q['messier'], 'true');
    expect(q['search'], 'm');
    expect(q['limit'], '500');
  });

  test('listObjects sans kind/messier n\'ajoute pas ces clés', () async {
    when(() => api.getJson(any(), query: any(named: 'query')))
        .thenAnswer((_) async => {'objects': [], 'count': 0, 'limit': 500, 'offset': 0});
    final repo = CatalogueRepository(api: api);
    await repo.listObjects();
    final captured = verify(() => api.getJson(captureAny(),
        query: captureAny(named: 'query'))).captured;
    final q = captured[1] as Map<String, String>;
    expect(q.containsKey('kind'), isFalse);
    expect(q.containsKey('messier'), isFalse);
  });
```

- [ ] **Step 2: Lancer → échec**

Run: `cd app && flutter test test/features/catalogue/catalogue_repository_test.dart`
Expected: FAIL (params inexistants).

- [ ] **Step 3: Repository — implémenter**

Dans `catalogue_repository.dart`, remplacer `listObjects` :

```dart
  Future<List<CatalogObjectDto>> listObjects({
    String? search,
    double? maxMag,
    bool visibleNow = false,
    String? kind,
    bool messier = false,
  }) async {
    final params = <String, String>{'limit': '500'};
    if (search != null && search.isNotEmpty) params['search'] = search;
    if (maxMag != null) params['max_mag'] = maxMag.toString();
    if (visibleNow) params['visible_now'] = 'true';
    if (kind != null) params['kind'] = kind;
    if (messier) params['messier'] = 'true';
    final j = await api.getJson('/catalog/objects', query: params);
    return (j['objects'] as List)
        .map((e) => CatalogObjectDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }
```

- [ ] **Step 4: Filters + events — implémenter**

Dans `catalogue_state.dart`, étendre `CatalogueFilters` :

```dart
  const CatalogueFilters({
    this.search = '',
    this.maxMag,
    this.visibleNow = true,
    this.constellation,
    this.kind,
    this.messierOnly = false,
  });

  final String search;
  final double? maxMag;
  final bool visibleNow;
  final String? constellation;
  final String? kind;
  final bool messierOnly;

  CatalogueFilters copyWith({
    String? search,
    double? maxMag,
    bool? visibleNow,
    String? constellation,
    String? kind,
    bool? messierOnly,
    bool clearMaxMag = false,
    bool clearConstellation = false,
    bool clearKind = false,
  }) =>
      CatalogueFilters(
        search: search ?? this.search,
        maxMag: clearMaxMag ? null : (maxMag ?? this.maxMag),
        visibleNow: visibleNow ?? this.visibleNow,
        constellation:
            clearConstellation ? null : (constellation ?? this.constellation),
        kind: clearKind ? null : (kind ?? this.kind),
        messierOnly: messierOnly ?? this.messierOnly,
      );

  @override
  List<Object?> get props =>
      [search, maxMag, visibleNow, constellation, kind, messierOnly];
```

Dans `catalogue_event.dart`, ajouter :

```dart
class KindFilterChanged extends CatalogueEvent {
  const KindFilterChanged(this.kind);
  final String? kind;
  @override
  List<Object?> get props => [kind];
}

class MessierToggled extends CatalogueEvent {
  const MessierToggled(this.enabled);
  final bool enabled;
  @override
  List<Object?> get props => [enabled];
}
```

- [ ] **Step 5: Bloc — implémenter handlers + `_query`**

Dans `catalogue_bloc.dart` :
- enregistrer les handlers dans le constructeur :

```dart
    on<KindFilterChanged>(_onKind);
    on<MessierToggled>(_onMessier);
```

- passer `kind`/`messier` dans `_query` :

```dart
      _fetched = await repo.listObjects(
        search: filters.search,
        maxMag: filters.maxMag,
        visibleNow: filters.visibleNow,
        kind: filters.kind,
        messier: filters.messierOnly,
      );
```

- ajouter les handlers :

```dart
  Future<void> _onKind(KindFilterChanged e, Emitter<CatalogueState> emit) =>
      _query(
          emit,
          e.kind == null
              ? _filters.copyWith(clearKind: true)
              : _filters.copyWith(kind: e.kind));

  Future<void> _onMessier(MessierToggled e, Emitter<CatalogueState> emit) =>
      _query(emit, _filters.copyWith(messierOnly: e.enabled));
```

- [ ] **Step 6: Bloc — mettre à jour les stubs + ajouter un test**

Dans `catalogue_bloc_test.dart`, ajouter `kind: any(named: 'kind'), messier: any(named: 'messier')` à **tous** les stubs `when(() => repo.listObjects(...))` et aux `verify(() => repo.listObjects(...))`. Ajouter :

```dart
  blocTest<CatalogueBloc, CatalogueState>(
    'KindFilterChanged re-query avec kind',
    build: () {
      when(() => repo.listObjects(
              search: any(named: 'search'),
              maxMag: any(named: 'maxMag'),
              visibleNow: any(named: 'visibleNow'),
              kind: any(named: 'kind'),
              messier: any(named: 'messier')))
          .thenAnswer((_) async => [_vega()]);
      return CatalogueBloc(repo: repo);
    },
    act: (b) => b.add(const KindFilterChanged('planet')),
    expect: () => [isA<CatalogueLoading>(), isA<CatalogueLoaded>()],
    verify: (_) => verify(() => repo.listObjects(
        search: any(named: 'search'),
        maxMag: any(named: 'maxMag'),
        visibleNow: any(named: 'visibleNow'),
        kind: 'planet',
        messier: any(named: 'messier'))).called(1),
  );
```

- [ ] **Step 7: UI — sélecteur famille + chip Messier + copie**

Dans `catalogue_screen.dart` :
- ajouter en haut du fichier la map des libellés :

```dart
const Map<String, String> kCatalogKinds = {
  'planet': 'Planètes',
  'moon': 'Lune',
  'sun': 'Soleil',
  'comet': 'Comètes',
  'dso': 'Ciel profond',
  'star': 'Étoiles',
};
```

- changer le `hintText` du `TextField` en `'Rechercher un objet…'`.
- dans le `Wrap` des `FilterChip`, ajouter une chip Messier :

```dart
                      FilterChip(
                        label: const Text('MESSIER'),
                        selected: filters.messierOnly,
                        onSelected: (v) => ctx
                            .read<CatalogueBloc>()
                            .add(MessierToggled(v)),
                      ),
```

- sous le `Wrap`, ajouter un sélecteur de famille (dropdown, `null` = toutes) :

```dart
                  const SizedBox(height: DesignTokens.spaceSM),
                  _KindDropdown(value: filters.kind),
```

- ajouter le widget `_KindDropdown` (calqué sur `_ConstellationDropdown`) :

```dart
class _KindDropdown extends StatelessWidget {
  const _KindDropdown({required this.value});
  final String? value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final text = context.textStyles;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: DesignTokens.spaceMD),
      decoration: BoxDecoration(
        color: colors.bgGradientTop.withValues(alpha: 0.5),
        border: Border.all(color: colors.accent.withValues(alpha: 0.22)),
        borderRadius: BorderRadius.circular(DesignTokens.radiusMD),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String?>(
          value: value,
          isExpanded: true,
          dropdownColor: colors.bgGradientBottom,
          iconEnabledColor: colors.accent,
          style: text.hudValue.copyWith(color: colors.textPrimary),
          items: [
            DropdownMenuItem<String?>(
              value: null,
              child: Text('Toutes les familles',
                  style: text.hudValue.copyWith(color: colors.textMuted)),
            ),
            ...kCatalogKinds.entries.map(
              (e) => DropdownMenuItem<String?>(
                value: e.key,
                child: Text(e.value),
              ),
            ),
          ],
          onChanged: (v) =>
              context.read<CatalogueBloc>().add(KindFilterChanged(v)),
        ),
      ),
    );
  }
}
```

- [ ] **Step 8: Écran test — mettre à jour le stub `listObjects`**

Dans `catalogue_screen_test.dart`, ajouter `kind: any(named: 'kind'), messier: any(named: 'messier')` au stub `when(() => mockRepo.listObjects(...))` du `setUp`.

- [ ] **Step 9: Lancer toute la suite + analyze → vert**

Run: `cd app && flutter test && flutter analyze`
Expected: PASS complet, aucune erreur d'analyse.

- [ ] **Step 10: Commit**

```bash
git add app/lib/features/catalogue app/test/features/catalogue
git commit -m "feat(app): catalogue family (kind) + Messier filters"
```

---

## Self-Review (rempli à l'écriture)

**Spec coverage** (spec §1–7) :
- §1 ApiService detail → Task 1. §2 DTO v2 → Task 2. §3 GoTo id → Task 3.
  §4 feedback non destructif → Task 3. §5 solaire server-driven → Task 4.
  §6 statut/resync référence → Tasks 5+6. §7 catalogue A-lite+ → Task 7.
- Table d'erreurs GoTo → `messageForGotoDetail` (Task 3) + interception solaire (Task 4).
- « À mettre à jour à la livraison » (roadmap/journal/backlog) : hors code, à
  faire dans la session de livraison (rappel dans le journal, pas une tâche de
  code).

**Placeholders** : aucun « TBD/TODO ». Deux notes d'adaptation explicites
(constructeur réel de `CalibrationStatus` en Task 6 Step 5 ; nom d'icône
Phosphor en Task 6 Step 7) — ce sont des vérifications ponctuelles bornées, pas
des trous de conception ; le comportement visé est décrit.

**Type consistency** : `goto(String id, {bool confirmSolar})`,
`GoToRequested(id, {confirmSolar})`, `GotoOutcome`/`GotoError`/`GotoSolarAck`,
`CatalogueLoaded.copyWith(...clearOutcome)`, `messageForGotoDetail`,
`ReferenceStatusDto`/`ReferenceSyncResultDto`, `ReferenceRepository.getStatus/sync`,
`CatalogueFilters.kind/messierOnly`, `KindFilterChanged`/`MessierToggled`,
`kCatalogKinds` — noms cohérents entre tâches de définition et d'usage.

**Scope** : une seule slice (contrat online). Offline/planner/notifs
explicitement hors périmètre (Global Constraints).
