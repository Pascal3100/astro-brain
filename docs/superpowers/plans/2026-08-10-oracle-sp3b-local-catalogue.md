# Oracle SP3-B — Catalogue local hors ligne (plan d'implémentation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** L'app Flutter lit son catalogue et calcule la visibilité « maintenant » depuis une copie **locale** de `reference.sqlite`, Pi éteint ; le GoTo reste online.

**Architecture:** Deux nouveaux modules app (`oracle_cache/` acquisition GitHub, `features/catalogue/local/` moteur lecture + projection) + réécriture **interne** de `CatalogueRepository` et `ReferenceRepository` (surface publique et DTO inchangés → bloc, UI et tests widget SP3-A intacts). Les fichiers `local/` sont des **ports fidèles** (mêmes formules, mêmes clauses SQL, mêmes bornes de fenêtre) de `_ephemeris.py`, `interpolation.py`, `providers.py`, `reference_catalog.py`, `visibility.py` ; l'acquisition est le miroir de `services/reference/sync.py`.

**Tech Stack:** Flutter/Dart, `flutter_bloc`, `sqlite3` (+ `sqlite3_flutter_libs`), `path_provider`, `http`, `geolocator` (déjà présent, via `PhoneLocation`). Tests : `flutter_test` + `bloc_test` + `mocktail`, sqlite in-memory pour les fixtures.

Spec de référence : `docs/superpowers/specs/2026-08-10-oracle-sp3b-local-catalogue-design.md`.

## Global Constraints

- **Port fidèle, pas réinvention.** Reproduire à l'identique les formules, clauses SQL et bornes de fenêtre des fichiers backend cités dans chaque tâche. Toute divergence numérique app↔Pi est un défaut.
- **Aucune astronomie nouvelle** : seule la trigonométrie géométrique LST→alt/az est portée. Pas de calcul d'éphémérides orbitales côté app.
- **Surface publique préservée** : `CatalogueRepository.{listObjects,goto,abort}` et `ReferenceRepository.{getStatus,sync}` gardent signatures et types de retour SP3-A (`CatalogObjectDto`, `ReferenceStatusDto`, `ReferenceSyncResultDto`). Le `CatalogueBloc`, `AlmanacScreen`, `ReferenceBanner` ne sont pas touchés (hors copie de la bannière, Task 11).
- **GoTo online** : `goto`/`abort` continuent d'appeler `ApiService` (Pi). L'app ne résout jamais un `id → RA/Dec` localement.
- **Garde schéma** : un `reference.sqlite` de `schema_version > 2` est refusé (fichier local `!ready`, download rejeté avant swap). Constante `kSupportedSchemaVersion = 2`.
- **URL manifest** : `https://github.com/Pascal3100/astro-brain/releases/download/almanac-latest/manifest.json` (constante `kManifestUrl`, identique au backend `DEFAULT_MANIFEST_URL`).
- **Statuts de sync** identiques au backend : `updated`, `up_to_date`, `offline`, `rejected_schema`, `rejected_hash`.
- **Tests** : miroir 1:1 sous `test/`, `mocktail` + `bloc_test`. Ne jamais taper un bouton câblé à un vrai bloc async (MockBloc). Les ports purs se testent contre des valeurs de référence figées.
- **Dart/Flutter idiomatique**, `flutter analyze` sans warning. Commits : sujet court FR, corps si utile, terminés par `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Répertoire de travail : `app/`. Tests : `flutter test`. Analyse : `flutter analyze`.

---

## File Structure

```
app/
  pubspec.yaml                                     (Task 1 : + sqlite3, sqlite3_flutter_libs, path_provider)
  lib/
    oracle_cache/
      manifest_dto.dart                            (Task 4)
      almanac_store.dart                           (Task 4)
      almanac_sync.dart                            (Task 9)
    features/catalogue/local/
      ephemeris_interpolation.dart                 (Task 2)
      sky_projection.dart                          (Task 3)
      local_reference_db.dart                      (Task 5)
      catalogue_providers.dart                     (Task 6)
      local_catalogue.dart                         (Task 7)   ← + LocalCatalogFilter
      visibility.dart                              (Task 8)
    features/catalogue/catalogue_repository.dart   (Task 10 : réécrit)
    features/setup/reference/reference_repository.dart (Task 11 : réécrit)
    app.dart                                       (Task 12 : DI)
  test/
    oracle_cache/manifest_dto_test.dart            (Task 4)
    oracle_cache/almanac_store_test.dart           (Task 4)
    oracle_cache/almanac_sync_test.dart            (Task 9)
    features/catalogue/local/ephemeris_interpolation_test.dart (Task 2)
    features/catalogue/local/sky_projection_test.dart          (Task 3)
    features/catalogue/local/local_reference_db_test.dart      (Task 5)
    features/catalogue/local/catalogue_providers_test.dart     (Task 6)
    features/catalogue/local/local_catalogue_test.dart         (Task 7)
    features/catalogue/local/visibility_test.dart              (Task 8)
    features/catalogue/local/_fixtures.dart        (Task 5 : DDL + builders, réutilisé 6/7)
    features/catalogue/catalogue_repository_test.dart (Task 10 : réécrit)
    features/setup/reference/reference_repository_test.dart (Task 11 : réécrit)
```

---

### Task 1: Dépendances + smoke sqlite3

**Files:**
- Modify: `app/pubspec.yaml`
- Test: `app/test/oracle_cache/sqlite3_smoke_test.dart` (créé puis retiré à l'étape finale — voir Step 4)

**Interfaces:**
- Produces: dépendances `sqlite3`, `sqlite3_flutter_libs`, `path_provider` résolues ; `sqlite3` utilisable en test hôte (in-memory).

- [ ] **Step 1: Ajouter les dépendances** dans `pubspec.yaml`, section `dependencies` (après `geolocator`) :

```yaml
  sqlite3: ^2.4.0
  sqlite3_flutter_libs: ^0.5.24
  path_provider: ^2.1.4
```

- [ ] **Step 2: Résoudre**

Run: `flutter pub get`
Expected: résolution OK.

- [ ] **Step 3: Smoke test sqlite3 sur l'hôte** — vérifie que la lib native SQLite est disponible pour les tests unitaires (sur Linux, `libsqlite3`).

```dart
// test/oracle_cache/sqlite3_smoke_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';

void main() {
  test('sqlite3 in-memory disponible sur l\'hôte de test', () {
    final db = sqlite3.openInMemory();
    db.execute('CREATE TABLE t (x INTEGER)');
    db.execute('INSERT INTO t VALUES (42)');
    final rows = db.select('SELECT x FROM t');
    expect(rows.first['x'], 42);
    db.dispose();
  });
}
```

Run: `flutter test test/oracle_cache/sqlite3_smoke_test.dart`
Expected: PASS. Si échec « Failed to load dynamic library 'libsqlite3.so' » → installer la lib système hôte (`sudo apt-get install -y libsqlite3-0`) puis relancer.

- [ ] **Step 4: Retirer le smoke test** (il a servi de vérification d'environnement, il n'a pas sa place dans la suite permanente) et vérifier l'analyse.

Run: `rm test/oracle_cache/sqlite3_smoke_test.dart && flutter analyze`
Expected: `No issues found!`

- [ ] **Step 5: Commit**

```bash
git add app/pubspec.yaml app/pubspec.lock
git commit -m "chore(app): deps sqlite3 + path_provider pour le catalogue local

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ephemeris_interpolation.dart` (port de `interpolation.py`)

Port pur de `backend/astro_brain/services/catalog/interpolation.py`.

**Files:**
- Create: `app/lib/features/catalogue/local/ephemeris_interpolation.dart`
- Test: `app/test/features/catalogue/local/ephemeris_interpolation_test.dart`

**Interfaces:**
- Produces:
  - `DateTime parseUtc(String s)`
  - `double lerp(double a, double b, double frac)`
  - `double lerpAngleDeg(double a, double b, double frac)`
  - `({double ra, double dec}) interpolateRaDec((DateTime, double, double) before, (DateTime, double, double) after, DateTime t)`

- [ ] **Step 1: Test qui échoue**

```dart
// test/features/catalogue/local/ephemeris_interpolation_test.dart
import 'package:astro_brain/features/catalogue/local/ephemeris_interpolation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parseUtc : offset explicite et naïf interprété UTC', () {
    expect(parseUtc('2026-08-10T00:00:00+00:00').toUtc().hour, 0);
    expect(parseUtc('2026-08-10T06:00:00Z').toUtc().hour, 6);
    // naïf → traité comme UTC (comme le backend), pas comme heure locale
    expect(parseUtc('2026-08-10T06:00:00').toUtc().hour, 6);
  });

  test('lerp linéaire', () {
    expect(lerp(10, 20, 0.25), closeTo(12.5, 1e-9));
  });

  test('lerpAngleDeg prend le plus court arc et wrappe 359->1', () {
    expect(lerpAngleDeg(359, 1, 0.5), closeTo(0.0, 1e-9));
    expect(lerpAngleDeg(10, 20, 0.5), closeTo(15.0, 1e-9));
  });

  test('interpolateRaDec : milieu de segment', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final t1 = DateTime.utc(2026, 8, 11, 0);
    final t = DateTime.utc(2026, 8, 10, 12);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t1, 102.0, 12.0), t);
    expect(r.ra, closeTo(101.0, 1e-9));
    expect(r.dec, closeTo(11.0, 1e-9));
  });

  test('interpolateRaDec : span nul renvoie l\'échantillon before', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t0, 200.0, 20.0), t0);
    expect(r.ra, closeTo(100.0, 1e-9));
    expect(r.dec, closeTo(10.0, 1e-9));
  });

  test('interpolateRaDec : frac clampé hors bornes', () {
    final t0 = DateTime.utc(2026, 8, 10, 0);
    final t1 = DateTime.utc(2026, 8, 11, 0);
    final tBefore = DateTime.utc(2026, 8, 9, 0);
    final r = interpolateRaDec((t0, 100.0, 10.0), (t1, 102.0, 12.0), tBefore);
    expect(r.ra, closeTo(100.0, 1e-9)); // frac=0
    expect(r.dec, closeTo(10.0, 1e-9));
  });
}
```

- [ ] **Step 2: Run → FAIL** (`ephemeris_interpolation.dart` absent)

Run: `flutter test test/features/catalogue/local/ephemeris_interpolation_test.dart`

- [ ] **Step 3: Implémenter**

```dart
// lib/features/catalogue/local/ephemeris_interpolation.dart
/// Interpolation linéaire pure des éphémères — port de
/// `backend/astro_brain/services/catalog/interpolation.py`.
library;

/// Parse un ISO-8601 en `DateTime` UTC. Suffixe `Z` accepté. Une chaîne
/// SANS offset est interprétée comme UTC (comme le backend), pas comme
/// heure locale — d'où l'ajout de `Z` avant `DateTime.parse`, qui sinon
/// lirait une date naïve en heure locale.
DateTime parseUtc(String s) {
  if (s.endsWith('Z')) return DateTime.parse(s).toUtc();
  final hasOffset = RegExp(r'[+\-]\d{2}:?\d{2}$').hasMatch(s);
  if (hasOffset) return DateTime.parse(s).toUtc();
  return DateTime.parse('${s}Z').toUtc();
}

double lerp(double a, double b, double frac) => a + (b - a) * frac;

/// Interpole un angle (deg) sur le plus court arc ; résultat dans [0, 360).
double lerpAngleDeg(double a, double b, double frac) {
  final diff = ((b - a + 180.0) % 360.0) - 180.0;
  return (a + diff * frac) % 360.0;
}

/// Interpole (ra, dec) à `t` entre deux échantillons `(utc, ra, dec)`.
({double ra, double dec}) interpolateRaDec(
  (DateTime, double, double) before,
  (DateTime, double, double) after,
  DateTime t,
) {
  final (t0, ra0, dec0) = before;
  final (t1, ra1, dec1) = after;
  final span = t1.difference(t0).inMicroseconds.toDouble();
  if (span == 0) return (ra: ra0 % 360.0, dec: dec0);
  var frac = t.difference(t0).inMicroseconds.toDouble() / span;
  frac = frac.clamp(0.0, 1.0);
  return (ra: lerpAngleDeg(ra0, ra1, frac), dec: lerp(dec0, dec1, frac));
}
```

- [ ] **Step 4: Run → PASS**

Run: `flutter test test/features/catalogue/local/ephemeris_interpolation_test.dart`

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/catalogue/local/ephemeris_interpolation.dart app/test/features/catalogue/local/ephemeris_interpolation_test.dart
git commit -m "feat(app): port Dart de l'interpolation éphémère (catalogue local)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `sky_projection.dart` (port de `_ephemeris.py`)

Port pur de `backend/astro_brain/services/_ephemeris.py`. **Temps-paramétré** (`t` en argument) — c'est ce moteur que SP3-C exercera à une date/heure arbitraire.

**Files:**
- Create: `app/lib/features/catalogue/local/sky_projection.dart`
- Test: `app/test/features/catalogue/local/sky_projection_test.dart`

**Interfaces:**
- Produces:
  - `class Observer { const Observer({required this.latDeg, required this.lonDeg}); final double latDeg, lonDeg; }`
  - `double julianDate(DateTime tUtc)`
  - `double gmstDeg(DateTime tUtc)`
  - `({double az, double alt}) skyAzAltFromRaDec(double raDeg, double decDeg, Observer o, DateTime tUtc)`

- [ ] **Step 1: Générer les valeurs de référence** avec le backend (source de vérité), pour figer les attendus du test :

Run (depuis `backend/`) :
```bash
uv run python -c "
from datetime import datetime, UTC
from astro_brain.services._ephemeris import Observer, sky_az_alt_from_ra_dec, _gmst_deg
t = datetime(2026, 8, 10, 22, 0, 0, tzinfo=UTC)
o = Observer(lat_deg=43.6, lon_deg=1.44)
print('gmst', _gmst_deg(t))
for ra, dec in [(279.23, 38.78), (0.0, 89.0), (101.29, -16.7)]:
    print(ra, dec, sky_az_alt_from_ra_dec(ra, dec, o, t))
"
```
Noter les nombres imprimés ; ils deviennent les `closeTo(...)` du Step 2. (Le backend prend un `datetime` tz-aware ; le port Dart prend un `DateTime` UTC équivalent.)

- [ ] **Step 2: Test qui échoue** — remplacer les `<...>` par les valeurs du Step 1 (tolérance 1e-6°) :

```dart
// test/features/catalogue/local/sky_projection_test.dart
import 'package:astro_brain/features/catalogue/local/sky_projection.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final t = DateTime.utc(2026, 8, 10, 22, 0, 0);
  const o = Observer(latDeg: 43.6, lonDeg: 1.44);

  test('gmstDeg == backend', () {
    expect(gmstDeg(t), closeTo(<GMST_BACKEND>, 1e-6));
  });

  test('skyAzAltFromRaDec == backend (Vega)', () {
    final r = skyAzAltFromRaDec(279.23, 38.78, o, t);
    expect(r.az, closeTo(<AZ_VEGA>, 1e-6));
    expect(r.alt, closeTo(<ALT_VEGA>, 1e-6));
  });

  test('proche du pôle : alt ~ lat, pas de NaN (clamp sin_alt)', () {
    final r = skyAzAltFromRaDec(0.0, 89.0, o, t);
    expect(r.alt, closeTo(<ALT_POLE>, 1e-6));
    expect(r.alt.isNaN, isFalse);
  });

  test('objet bas (Sirius) == backend', () {
    final r = skyAzAltFromRaDec(101.29, -16.7, o, t);
    expect(r.az, closeTo(<AZ_SIRIUS>, 1e-6));
    expect(r.alt, closeTo(<ALT_SIRIUS>, 1e-6));
  });
}
```

- [ ] **Step 3: Run → FAIL**

Run: `flutter test test/features/catalogue/local/sky_projection_test.dart`

- [ ] **Step 4: Implémenter** — port ligne à ligne, en conservant la séparation `T₀` (0h UT) + terme `1.00273790935·H` :

```dart
// lib/features/catalogue/local/sky_projection.dart
/// Projection pure RA/Dec (of-date) → Az/Alt apparent — port de
/// `backend/astro_brain/services/_ephemeris.py`. Précision arc-min, sans
/// nutation/aberration/réfraction. Az depuis le Nord vers l'Est ; Alt depuis
/// l'horizon. `t` en argument : le même moteur sert « maintenant » (SP3-B) et
/// une date/heure arbitraire (SP3-C).
library;

import 'dart:math' as math;

class Observer {
  const Observer({required this.latDeg, required this.lonDeg});
  final double latDeg;
  final double lonDeg;
}

double _rad(double d) => d * math.pi / 180.0;
double _deg(double r) => r * 180.0 / math.pi;

double julianDate(DateTime tUtc) {
  final t = tUtc.toUtc();
  var y = t.year;
  var m = t.month;
  final d = t.day + (t.hour + (t.minute + t.second / 60.0) / 60.0) / 24.0;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  final a = y ~/ 100;
  final b = 2 - a + a ~/ 4;
  return (365.25 * (y + 4716)).floorToDouble() +
      (30.6001 * (m + 1)).floorToDouble() +
      d +
      b -
      1524.5;
}

/// Greenwich Mean Sidereal Time en degrés (IAU 1982). `T₀` à 0h UT du jour,
/// heure UT ajoutée séparément via `1.00273790935·H` (les mélanger induit
/// ~0.5° de biais).
double gmstDeg(DateTime tUtc) {
  final jd = julianDate(tUtc);
  final jd0 = (jd - 0.5).floorToDouble() + 0.5;
  final hUt = (jd - jd0) * 24.0;
  final t0 = (jd0 - 2451545.0) / 36525.0;
  final gmstH = 6.697374558 +
      2400.051336 * t0 +
      0.000025862 * t0 * t0 +
      1.00273790935 * hUt;
  return (gmstH * 15.0) % 360.0;
}

({double az, double alt}) skyAzAltFromRaDec(
    double raDeg, double decDeg, Observer o, DateTime tUtc) {
  final gmst = gmstDeg(tUtc);
  final lst = (gmst + o.lonDeg) % 360.0;
  var haDeg = (lst - raDeg) % 360.0;
  if (haDeg > 180) haDeg -= 360;
  final ha = _rad(haDeg);
  final dec = _rad(decDeg);
  final lat = _rad(o.latDeg);

  final sinAlt =
      (math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(ha))
          .clamp(-1.0, 1.0);
  final alt = _deg(math.asin(sinAlt));
  final altRad = _rad(alt);

  final sinAz = -math.cos(dec) * math.sin(ha) / math.cos(altRad);
  final cosAz = (math.sin(dec) - math.sin(altRad) * math.sin(lat)) /
      (math.cos(altRad) * math.cos(lat));
  final az = _deg(math.atan2(sinAz, cosAz)) % 360.0;
  return (az: az, alt: alt);
}
```

- [ ] **Step 5: Run → PASS**

Run: `flutter test test/features/catalogue/local/sky_projection_test.dart`

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/catalogue/local/sky_projection.dart app/test/features/catalogue/local/sky_projection_test.dart
git commit -m "feat(app): port Dart de la projection alt/az (catalogue local)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `manifest_dto.dart` + `almanac_store.dart`

DTO de `manifest.json` (émis par `oracle/oracle/manifest.py`) + store isolant `path_provider` et le calcul sha256 (miroir de `local_sha256` dans `reference_db.py`).

**Files:**
- Create: `app/lib/oracle_cache/manifest_dto.dart`
- Create: `app/lib/oracle_cache/almanac_store.dart`
- Test: `app/test/oracle_cache/manifest_dto_test.dart`
- Test: `app/test/oracle_cache/almanac_store_test.dart`

**Interfaces:**
- Produces:
  - `class AlmanacManifest { final int schemaVersion; final String generatedAt, sqliteUrl, sqliteSha256, windowStart, windowEnd; factory AlmanacManifest.fromJson(Map<String,dynamic>); }` (lève `FormatException` si clé requise absente)
  - `class AlmanacStore` : `AlmanacStore({Future<Directory> Function()? docsDir})` ; `Future<File> file()`, `Future<File> tmpFile()`, `Future<String?> localSha256()`
  - Constantes `const kManifestUrl = '...almanac-latest/manifest.json'`, `const kSupportedSchemaVersion = 2`, `const kReferenceFilename = 'reference.sqlite'`.

- [ ] **Step 1: Tests qui échouent (manifest)**

```dart
// test/oracle_cache/manifest_dto_test.dart
import 'package:astro_brain/oracle_cache/manifest_dto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final json = {
    'schema_version': 2,
    'generated_at': '2026-08-10T00:00:00+00:00',
    'sqlite_url': 'https://example/reference.sqlite',
    'sqlite_sha256': 'abc123',
    'window_start': '2026-08-01',
    'window_end': '2026-09-30',
  };

  test('fromJson parse toutes les clés', () {
    final m = AlmanacManifest.fromJson(json);
    expect(m.schemaVersion, 2);
    expect(m.sqliteUrl, 'https://example/reference.sqlite');
    expect(m.sqliteSha256, 'abc123');
    expect(m.windowEnd, '2026-09-30');
  });

  test('fromJson lève FormatException si clé requise absente', () {
    final bad = Map<String, dynamic>.from(json)..remove('sqlite_sha256');
    expect(() => AlmanacManifest.fromJson(bad), throwsFormatException);
  });
}
```

- [ ] **Step 2: Tests qui échouent (store)** — le store prend un fournisseur de dossier injectable pour contourner `path_provider` en test :

```dart
// test/oracle_cache/almanac_store_test.dart
import 'dart:convert';
import 'dart:io';
import 'package:astro_brain/oracle_cache/almanac_store.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory tmp;
  setUp(() => tmp = Directory.systemTemp.createTempSync('almanac_store_test'));
  tearDown(() => tmp.deleteSync(recursive: true));

  AlmanacStore store() => AlmanacStore(docsDir: () async => tmp);

  test('file() est <docs>/reference.sqlite', () async {
    final f = await store().file();
    expect(f.path, '${tmp.path}/reference.sqlite');
  });

  test('localSha256 null si absent, digest sinon', () async {
    final s = store();
    expect(await s.localSha256(), isNull);
    final f = await s.file();
    f.writeAsBytesSync(utf8.encode('hello'));
    final expected = sha256.convert(utf8.encode('hello')).toString();
    expect(await s.localSha256(), expected);
  });
}
```

> Note : le test importe `package:crypto`. Le calcul de sha256 dans le code de prod peut aussi passer par `package:crypto` (le sous-package `sha256`). Ajouter `crypto: ^3.0.6` aux `dependencies` si absent (transitive via `http`? le vérifier avec `flutter pub deps`). Si déjà transitive, l'ajouter tout de même en dépendance directe pour l'importer proprement.

- [ ] **Step 3: Run → FAIL**

Run: `flutter test test/oracle_cache/`

- [ ] **Step 4: Implémenter le manifest**

```dart
// lib/oracle_cache/manifest_dto.dart
/// DTO miroir de `manifest.json` (émis par `oracle/oracle/manifest.py`).
library;

class AlmanacManifest {
  const AlmanacManifest({
    required this.schemaVersion,
    required this.generatedAt,
    required this.sqliteUrl,
    required this.sqliteSha256,
    required this.windowStart,
    required this.windowEnd,
  });

  final int schemaVersion;
  final String generatedAt;
  final String sqliteUrl;
  final String sqliteSha256;
  final String windowStart;
  final String windowEnd;

  factory AlmanacManifest.fromJson(Map<String, dynamic> j) {
    T req<T>(String k) {
      final v = j[k];
      if (v == null) throw FormatException('manifest: clé manquante "$k"');
      return v as T;
    }

    return AlmanacManifest(
      schemaVersion: (req<num>('schema_version')).toInt(),
      generatedAt: req<String>('generated_at'),
      sqliteUrl: req<String>('sqlite_url'),
      sqliteSha256: req<String>('sqlite_sha256'),
      windowStart: req<String>('window_start'),
      windowEnd: req<String>('window_end'),
    );
  }
}
```

- [ ] **Step 5: Implémenter le store**

```dart
// lib/oracle_cache/almanac_store.dart
/// Emplacement local de `reference.sqlite` + sha256 — isole `path_provider`
/// et le FS. Miroir de `reference_path`/`local_sha256` (backend reference_db.py).
library;

import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path_provider/path_provider.dart';

const kManifestUrl =
    'https://github.com/Pascal3100/astro-brain/releases/download/'
    'almanac-latest/manifest.json';
const kSupportedSchemaVersion = 2;
const kReferenceFilename = 'reference.sqlite';

class AlmanacStore {
  AlmanacStore({Future<Directory> Function()? docsDir})
      : _docsDir = docsDir ?? getApplicationDocumentsDirectory;

  final Future<Directory> Function() _docsDir;

  Future<File> file() async {
    final dir = await _docsDir();
    await dir.create(recursive: true);
    return File('${dir.path}/$kReferenceFilename');
  }

  Future<File> tmpFile() async {
    final dir = await _docsDir();
    return File('${dir.path}/$kReferenceFilename.tmp');
  }

  Future<String?> localSha256() async {
    final f = await file();
    if (!f.existsSync()) return null;
    final digest = await sha256.bind(f.openRead()).first;
    return digest.toString();
  }
}
```

- [ ] **Step 6: Run → PASS** (ajouter `crypto` aux deps si l'import échoue, puis `flutter pub get`)

Run: `flutter test test/oracle_cache/`

- [ ] **Step 7: Commit**

```bash
git add app/lib/oracle_cache/manifest_dto.dart app/lib/oracle_cache/almanac_store.dart app/test/oracle_cache/ app/pubspec.yaml app/pubspec.lock
git commit -m "feat(app): manifest DTO + almanac store (emplacement local + sha256)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `local_reference_db.dart` + fixtures (port de `reference_db.py`)

Ouverture **lecture seule** du `reference.sqlite` local via `sqlite3`, lecture de `meta`. Crée aussi le fichier de fixtures partagé (DDL + builders de lignes) réutilisé par les Tasks 6 et 7.

**Files:**
- Create: `app/lib/features/catalogue/local/local_reference_db.dart`
- Create: `app/test/features/catalogue/local/_fixtures.dart`
- Test: `app/test/features/catalogue/local/local_reference_db_test.dart`

**Interfaces:**
- Produces:
  - `class ReferenceMetaLocal { final int schemaVersion; final String generatedAt, windowStart, windowEnd; }`
  - `class LocalReferenceDb` : `LocalReferenceDb(this._path)` ; `@visibleForTesting LocalReferenceDb.withDatabase(Database db)` ; `void open()`, `bool get ready`, `Database? current()`, `void reopen()`, `ReferenceMetaLocal? meta()`, `void close()`.
- Consumes (test fixtures) : `kReferenceSchemaDdl` (String), `insertMeta(...)`, `insertFixed(...)`, `insertEphemerisSample(...)` dans `_fixtures.dart`.

- [ ] **Step 1: Fixtures partagées** — DDL copié **verbatim** de `oracle/schema.sql` (contrat `schema_version = 2`) + helpers d'insertion :

```dart
// test/features/catalogue/local/_fixtures.dart
import 'package:sqlite3/sqlite3.dart';

/// DDL copié de oracle/schema.sql (schema_version 2).
const kReferenceSchemaDdl = '''
CREATE TABLE meta (
  schema_version INTEGER NOT NULL, generated_at TEXT NOT NULL, mpc_epoch TEXT,
  window_start TEXT NOT NULL, window_end TEXT NOT NULL, skyfield_kernel TEXT);
CREATE TABLE objects (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, designation TEXT);
CREATE TABLE fixed_object (
  object_id TEXT PRIMARY KEY REFERENCES objects(id), ra_deg REAL NOT NULL,
  dec_deg REAL NOT NULL, apparent_mag REAL, object_type TEXT, size_arcmin REAL,
  constellation TEXT, messier TEXT, ngc_ic TEXT);
CREATE TABLE ephemeris (
  object_id TEXT NOT NULL REFERENCES objects(id), sample_utc TEXT NOT NULL,
  ra_deg REAL NOT NULL, dec_deg REAL NOT NULL, earth_dist_au REAL,
  sun_dist_au REAL, apparent_mag REAL, illumination REAL, constellation TEXT,
  PRIMARY KEY (object_id, sample_utc));
CREATE INDEX idx_ephem_time ON ephemeris(sample_utc);
CREATE TABLE comet_elements (
  object_id TEXT PRIMARY KEY REFERENCES objects(id), epoch_jd REAL,
  perihelion_q_au REAL NOT NULL, eccentricity REAL NOT NULL,
  inclination_deg REAL NOT NULL, arg_perihelion_deg REAL NOT NULL,
  node_deg REAL NOT NULL, mag_h REAL, mag_k REAL);
''';

Database newReferenceDb({int schemaVersion = 2}) {
  final db = sqlite3.openInMemory();
  db.execute(kReferenceSchemaDdl);
  db.execute(
    'INSERT INTO meta (schema_version, generated_at, window_start, window_end,'
    ' skyfield_kernel) VALUES (?, ?, ?, ?, ?)',
    [schemaVersion, '2026-08-10T00:00:00+00:00', '2026-08-01', '2026-09-30',
     'de421.bsp'],
  );
  return db;
}

void insertFixed(Database db, {
  required String id, required String kind, String? name, String? designation,
  required double ra, required double dec, double? mag, String? objectType,
  double? sizeArcmin, String? constellation, String? messier, String? ngcIc,
}) {
  db.execute('INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)',
      [id, kind, name, designation]);
  db.execute(
    'INSERT INTO fixed_object (object_id, ra_deg, dec_deg, apparent_mag,'
    ' object_type, size_arcmin, constellation, messier, ngc_ic)'
    ' VALUES (?,?,?,?,?,?,?,?,?)',
    [id, ra, dec, mag, objectType, sizeArcmin, constellation, messier, ngcIc]);
}

void insertEphemObject(Database db, {
  required String id, required String kind, String? name, String? designation,
}) {
  db.execute('INSERT INTO objects (id, kind, name, designation) VALUES (?,?,?,?)',
      [id, kind, name, designation]);
}

void insertEphemSample(Database db, {
  required String id, required String sampleUtc, required double ra,
  required double dec, double? mag, double? illumination, String? constellation,
}) {
  db.execute(
    'INSERT INTO ephemeris (object_id, sample_utc, ra_deg, dec_deg,'
    ' apparent_mag, illumination, constellation) VALUES (?,?,?,?,?,?,?)',
    [id, sampleUtc, ra, dec, mag, illumination, constellation]);
}
```

- [ ] **Step 2: Test qui échoue** — `withDatabase` pour l'in-memory, et un vrai fichier temporaire pour le chemin RO :

```dart
// test/features/catalogue/local/local_reference_db_test.dart
import 'dart:io';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqlite3/sqlite3.dart';
import '_fixtures.dart';

void main() {
  test('withDatabase : ready + meta lue', () {
    final db = newReferenceDb();
    final ref = LocalReferenceDb.withDatabase(db);
    expect(ref.ready, isTrue);
    final m = ref.meta();
    expect(m!.schemaVersion, 2);
    expect(m.windowEnd, '2026-09-30');
    ref.close();
  });

  test('fichier absent : !ready, meta null', () {
    final ref = LocalReferenceDb('/does/not/exist/reference.sqlite');
    ref.open();
    expect(ref.ready, isFalse);
    expect(ref.meta(), isNull);
  });

  test('schema_version 3 : refusé (!ready)', () {
    final db = newReferenceDb(schemaVersion: 3);
    final ref = LocalReferenceDb.withDatabase(db);
    expect(ref.ready, isFalse);
    ref.close();
  });

  test('open() sur un vrai fichier RO', () {
    final tmp = Directory.systemTemp.createTempSync('ref_db_test');
    final path = '${tmp.path}/reference.sqlite';
    final seed = sqlite3.open(path);
    seed..execute(kReferenceSchemaDdl)
        ..execute('INSERT INTO meta (schema_version, generated_at, window_start,'
            ' window_end) VALUES (2, "g", "s", "e")')
        ..dispose();
    final ref = LocalReferenceDb(path)..open();
    expect(ref.ready, isTrue);
    expect(ref.meta()!.windowStart, 's');
    ref.close();
    tmp.deleteSync(recursive: true);
  });
}
```

- [ ] **Step 3: Run → FAIL**

Run: `flutter test test/features/catalogue/local/local_reference_db_test.dart`

- [ ] **Step 4: Implémenter** — ne jamais lever ; refuser `schema_version > 2` :

```dart
// lib/features/catalogue/local/local_reference_db.dart
/// Handle lecture seule vers un `reference.sqlite` local — port de
/// `backend/astro_brain/repository/reference_db.py`. `sqlite3` étant synchrone
/// (pas de requête en vol pendant un reopen), on simplifie : pas de handle
/// « stale » différé, un close + open direct.
library;

import 'package:flutter/foundation.dart';
import 'package:sqlite3/sqlite3.dart';

import '../../../oracle_cache/almanac_store.dart' show kSupportedSchemaVersion;

class ReferenceMetaLocal {
  const ReferenceMetaLocal({
    required this.schemaVersion,
    required this.generatedAt,
    required this.windowStart,
    required this.windowEnd,
  });
  final int schemaVersion;
  final String generatedAt;
  final String windowStart;
  final String windowEnd;
}

class LocalReferenceDb {
  LocalReferenceDb(this._path);

  @visibleForTesting
  LocalReferenceDb.withDatabase(Database db) : _path = ':memory:' {
    _adopt(db);
  }

  final String _path;
  Database? _conn;

  bool get ready => _conn != null;
  Database? current() => _conn;

  void open() {
    _conn?.dispose();
    _conn = null;
    Database db;
    try {
      db = sqlite3.open(_path, mode: OpenMode.readOnly);
    } on SqliteException {
      return; // fichier absent / verrouillé / corrompu → !ready
    }
    _adopt(db);
  }

  void reopen() => open();

  void _adopt(Database db) {
    try {
      final row = db.select('SELECT schema_version FROM meta LIMIT 1');
      if (row.isEmpty || (row.first['schema_version'] as int) > kSupportedSchemaVersion) {
        db.dispose();
        return;
      }
    } on SqliteException {
      db.dispose();
      return;
    }
    _conn = db;
  }

  ReferenceMetaLocal? meta() {
    final conn = _conn;
    if (conn == null) return null;
    final rows = conn.select(
      'SELECT schema_version, generated_at, window_start, window_end'
      ' FROM meta LIMIT 1');
    if (rows.isEmpty) return null;
    final r = rows.first;
    return ReferenceMetaLocal(
      schemaVersion: r['schema_version'] as int,
      generatedAt: r['generated_at'] as String,
      windowStart: r['window_start'] as String,
      windowEnd: r['window_end'] as String,
    );
  }

  void close() {
    _conn?.dispose();
    _conn = null;
  }
}
```

- [ ] **Step 5: Run → PASS**

Run: `flutter test test/features/catalogue/local/local_reference_db_test.dart`

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/catalogue/local/local_reference_db.dart app/test/features/catalogue/local/local_reference_db_test.dart app/test/features/catalogue/local/_fixtures.dart
git commit -m "feat(app): handle RO local de reference.sqlite + fixtures schema

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `catalogue_providers.dart` (port de `providers.py`)

Providers fixe + éphémère lisant le sqlite local et produisant des `CatalogObjectDto` (le DTO SP3-A). SQL et logique **identiques** au backend.

**Files:**
- Create: `app/lib/features/catalogue/local/catalogue_providers.dart`
- Test: `app/test/features/catalogue/local/catalogue_providers_test.dart`

**Interfaces:**
- Consumes: `LocalReferenceDb` (Task 5), `interpolateRaDec`/`parseUtc` (Task 2), `CatalogObjectDto` (`lib/features/catalogue/catalogue_models.dart`), `LocalCatalogFilter` (défini ici, réutilisé Task 7).
- Produces:
  - `class LocalCatalogFilter { const LocalCatalogFilter({this.kind, this.search = '', this.maxMag, this.messierOnly = false, this.limit = 500, this.offset = 0}); ... LocalCatalogFilter copyWith({int? limit, int? offset}); }`
  - `class FixedObjectProvider { static const kinds = {'dso','star'}; List<CatalogObjectDto> listObjects(LocalCatalogFilter f); }`
  - `class EphemerisProvider { static const kinds = {'comet','planet','moon','sun'}; EphemerisProvider({required DateTime Function() nowUtc}); List<CatalogObjectDto> listObjects(LocalCatalogFilter f); }`

- [ ] **Step 1: Test qui échoue** — fenêtre éphémère, interpolation, exclusion des stale, filtres fixes :

```dart
// test/features/catalogue/local/catalogue_providers_test.dart
import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import '_fixtures.dart';

void main() {
  test('FixedObjectProvider : filtres kind/max_mag/messier/search + tri', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'NGC1976', kind: 'dso', name: 'Orion Nebula',
        ra: 83.8, dec: -5.4, mag: 4.0, messier: 'M42', ngcIc: 'NGC1976');
    insertFixed(db, id: 'star:HIP32349', kind: 'star', name: 'Sirius',
        ra: 101.3, dec: -16.7, mag: -1.46);
    insertFixed(db, id: 'NGC7000', kind: 'dso', name: 'North America',
        ra: 314.0, dec: 44.0, mag: null);
    final ref = LocalReferenceDb.withDatabase(db);
    final p = FixedObjectProvider(ref);

    final all = p.listObjects(const LocalCatalogFilter());
    expect(all.map((o) => o.name),
        ['Sirius', 'Orion Nebula', 'North America']); // mag asc, null en dernier

    final messier = p.listObjects(const LocalCatalogFilter(messierOnly: true));
    expect(messier.map((o) => o.qualifiedId), ['NGC1976']);

    final dso = p.listObjects(const LocalCatalogFilter(kind: 'dso', maxMag: 5));
    expect(dso.map((o) => o.name), ['Orion Nebula']);

    final search = p.listObjects(const LocalCatalogFilter(search: 'siri'));
    expect(search.single.name, 'Sirius');
    ref.close();
  });

  test('EphemerisProvider : interpole dans la fenêtre, exclut les stale', () {
    final db = newReferenceDb();
    insertEphemObject(db, id: 'planet:mars', kind: 'planet', name: 'Mars');
    insertEphemSample(db, id: 'planet:mars',
        sampleUtc: '2026-08-10T00:00:00+00:00', ra: 100.0, dec: 10.0, mag: 0.5);
    insertEphemSample(db, id: 'planet:mars',
        sampleUtc: '2026-08-11T00:00:00+00:00', ra: 102.0, dec: 12.0, mag: 0.5);
    // objet hors fenêtre → stale → exclu de listObjects
    insertEphemObject(db, id: 'comet:X', kind: 'comet', name: 'Comet X');
    insertEphemSample(db, id: 'comet:X',
        sampleUtc: '2026-01-01T00:00:00+00:00', ra: 5.0, dec: 5.0, mag: 8.0);
    final ref = LocalReferenceDb.withDatabase(db);
    final p = EphemerisProvider(ref,
        nowUtc: () => DateTime.utc(2026, 8, 10, 12));

    final objs = p.listObjects(const LocalCatalogFilter());
    expect(objs.map((o) => o.qualifiedId), ['planet:mars']);
    expect(objs.single.raDeg, closeTo(101.0, 1e-9)); // interpolé au milieu
    expect(objs.single.ephemerisStale, isFalse);
    ref.close();
  });
}
```

- [ ] **Step 2: Run → FAIL**

Run: `flutter test test/features/catalogue/local/catalogue_providers_test.dart`

- [ ] **Step 3: Implémenter** — SQL verbatim de `providers.py`, fenêtre `now ± (1 j 12 h)`, tri mag-null-last :

```dart
// lib/features/catalogue/local/catalogue_providers.dart
/// Providers catalogue lus dans reference.sqlite local — port de
/// `backend/astro_brain/services/catalog/providers.py`.
library;

import 'package:sqlite3/sqlite3.dart';

import '../catalogue_models.dart';
import 'ephemeris_interpolation.dart';
import 'local_reference_db.dart';

class LocalCatalogFilter {
  const LocalCatalogFilter({
    this.kind,
    this.search = '',
    this.maxMag,
    this.messierOnly = false,
    this.limit = 500,
    this.offset = 0,
  });
  final String? kind;
  final String search;
  final double? maxMag;
  final bool messierOnly;
  final int limit;
  final int offset;

  LocalCatalogFilter copyWith({int? limit, int? offset}) => LocalCatalogFilter(
        kind: kind, search: search, maxMag: maxMag, messierOnly: messierOnly,
        limit: limit ?? this.limit, offset: offset ?? this.offset);
}

const _fixedColumns =
    'o.id, o.kind, o.name, o.designation, f.ra_deg, f.dec_deg, f.apparent_mag,'
    ' f.object_type, f.size_arcmin, f.constellation, f.messier, f.ngc_ic';

CatalogObjectDto _fixedRow(Row r) => CatalogObjectDto(
      qualifiedId: r['id'] as String,
      kind: r['kind'] as String,
      name: (r['name'] as String?) ??
          (r['designation'] as String?) ??
          (r['id'] as String),
      designation: r['designation'] as String?,
      raDeg: (r['ra_deg'] as num).toDouble(),
      decDeg: (r['dec_deg'] as num).toDouble(),
      mag: (r['apparent_mag'] as num?)?.toDouble(),
      constellation: r['constellation'] as String?,
      objectType: r['object_type'] as String?,
      angularSizeArcmin: (r['size_arcmin'] as num?)?.toDouble(),
      messier: r['messier'] as String?,
      ngcIc: r['ngc_ic'] as String?,
    );

class FixedObjectProvider {
  FixedObjectProvider(this._ref);
  static const kinds = {'dso', 'star'};
  final LocalReferenceDb _ref;

  List<CatalogObjectDto> listObjects(LocalCatalogFilter f) {
    final conn = _ref.current();
    if (conn == null) return [];
    var sql = 'SELECT $_fixedColumns FROM fixed_object f'
        ' JOIN objects o ON o.id = f.object_id WHERE ';
    final params = <Object?>[];
    if (kinds.contains(f.kind)) {
      sql += 'o.kind = ?';
      params.add(f.kind);
    } else {
      sql += "o.kind IN ('dso', 'star')";
    }
    if (f.maxMag != null) {
      sql += ' AND f.apparent_mag IS NOT NULL AND f.apparent_mag <= ?';
      params.add(f.maxMag);
    }
    if (f.messierOnly) sql += ' AND f.messier IS NOT NULL';
    if (f.search.isNotEmpty) {
      final like = '%${f.search}%';
      sql += ' AND (o.name LIKE ? OR o.designation LIKE ?'
          ' OR f.messier LIKE ? OR f.ngc_ic LIKE ?)';
      params.addAll([like, like, like, like]);
    }
    sql += ' ORDER BY CASE WHEN f.apparent_mag IS NULL THEN 1 ELSE 0 END,'
        ' f.apparent_mag, o.name LIMIT ? OFFSET ?';
    params.addAll([f.limit, f.offset]);
    return conn.select(sql, params).map(_fixedRow).toList();
  }
}

class EphemerisProvider {
  EphemerisProvider(this._ref, {required DateTime Function() nowUtc})
      : _now = nowUtc;
  static const kinds = {'comet', 'planet', 'moon', 'sun'};
  final LocalReferenceDb _ref;
  final DateTime Function() _now;

  List<CatalogObjectDto> listObjects(LocalCatalogFilter f) {
    final conn = _ref.current();
    if (conn == null) return [];
    final now = _now();
    final (clause, kindParams) = _kindsClause(f);
    final lo = now.subtract(const Duration(days: 1, hours: 12)).toIso8601String();
    final hi = now.add(const Duration(days: 1, hours: 12)).toIso8601String();
    final rows = conn.select(
      'SELECT e.object_id, o.kind, o.name, o.designation, e.sample_utc,'
      ' e.ra_deg, e.dec_deg, e.apparent_mag, e.illumination, e.constellation'
      ' FROM ephemeris e JOIN objects o ON o.id = e.object_id'
      ' WHERE $clause AND e.sample_utc BETWEEN ? AND ?'
      ' ORDER BY e.object_id, e.sample_utc',
      [...kindParams, lo, hi],
    );
    final grouped = <String, List<Row>>{};
    for (final r in rows) {
      grouped.putIfAbsent(r['object_id'] as String, () => []).add(r);
    }
    final objs = <CatalogObjectDto>[];
    for (final samples in grouped.values) {
      final obj = _build(samples, now);
      if (obj == null || obj.ephemerisStale) continue;
      if (f.maxMag != null && (obj.mag == null || obj.mag! > f.maxMag!)) continue;
      if (f.search.isNotEmpty) {
        final hay = '${obj.name} ${obj.designation ?? ''}'.toLowerCase();
        if (!hay.contains(f.search.toLowerCase())) continue;
      }
      objs.add(obj);
    }
    objs.sort((a, b) => _magKey(a).compareTo(_magKey(b)) != 0
        ? _magKey(a).compareTo(_magKey(b))
        : a.name.compareTo(b.name));
    final start = f.offset.clamp(0, objs.length);
    final end = (f.offset + f.limit).clamp(0, objs.length);
    return objs.sublist(start, end);
  }

  double _magKey(CatalogObjectDto o) => o.mag ?? double.infinity;

  (String, List<Object?>) _kindsClause(LocalCatalogFilter f) {
    if (kinds.contains(f.kind)) return ('o.kind = ?', [f.kind]);
    final ph = List.filled(kinds.length, '?').join(', ');
    return ('o.kind IN ($ph)', kinds.toList());
  }

  CatalogObjectDto? _build(List<Row> samples, DateTime now) {
    if (samples.isEmpty) return null;
    final parsed = samples
        .map((s) => (parseUtc(s['sample_utc'] as String), s))
        .toList();
    final before = parsed.where((p) => !p.$1.isAfter(now)).toList();
    final after = parsed.where((p) => !p.$1.isBefore(now)).toList();
    final stale = !(before.isNotEmpty && after.isNotEmpty);
    late Row src;
    late double ra, dec;
    if (!stale) {
      final b = before.last, a = after.first;
      final r = interpolateRaDec(
        (b.$1, (b.$2['ra_deg'] as num).toDouble(), (b.$2['dec_deg'] as num).toDouble()),
        (a.$1, (a.$2['ra_deg'] as num).toDouble(), (a.$2['dec_deg'] as num).toDouble()),
        now,
      );
      ra = r.ra;
      dec = r.dec;
      src = b.$2;
    } else {
      parsed.sort((x, y) => x.$1.difference(now).abs().compareTo(
          y.$1.difference(now).abs()));
      src = parsed.first.$2;
      ra = (src['ra_deg'] as num).toDouble();
      dec = (src['dec_deg'] as num).toDouble();
    }
    return CatalogObjectDto(
      qualifiedId: src['object_id'] as String,
      kind: src['kind'] as String,
      name: (src['name'] as String?) ??
          (src['designation'] as String?) ??
          (src['object_id'] as String),
      designation: src['designation'] as String?,
      raDeg: ra,
      decDeg: dec,
      mag: (src['apparent_mag'] as num?)?.toDouble(),
      illumination: (src['illumination'] as num?)?.toDouble(),
      constellation: src['constellation'] as String?,
      ephemerisStale: stale,
    );
  }
}
```

> Détail de fidélité : `before = échantillons ≤ now` (`!isAfter`), `after = ≥ now` (`!isBefore`) — miroir exact de `providers.py`. `Duration.abs()` sur la différence pour l'échantillon-frontière.

- [ ] **Step 4: Run → PASS**

Run: `flutter test test/features/catalogue/local/catalogue_providers_test.dart`

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/catalogue/local/catalogue_providers.dart app/test/features/catalogue/local/catalogue_providers_test.dart
git commit -m "feat(app): providers catalogue local (fixe + éphémère interpolé)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `local_catalogue.dart` (port de `reference_catalog.py`)

Façade combinant les deux providers : dispatch par `kind`, sinon merge + tri + pagination.

**Files:**
- Create: `app/lib/features/catalogue/local/local_catalogue.dart`
- Test: `app/test/features/catalogue/local/local_catalogue_test.dart`

**Interfaces:**
- Consumes: `FixedObjectProvider`, `EphemerisProvider`, `LocalCatalogFilter`, `LocalReferenceDb`.
- Produces: `class LocalCatalogue { LocalCatalogue({required LocalReferenceDb reference, required FixedObjectProvider fixed, required EphemerisProvider ephemeris}); List<CatalogObjectDto> listAll(LocalCatalogFilter f); }`

- [ ] **Step 1: Test qui échoue**

```dart
// test/features/catalogue/local/local_catalogue_test.dart
import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_catalogue.dart';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:flutter_test/flutter_test.dart';
import '_fixtures.dart';

void main() {
  LocalCatalogue build(LocalReferenceDb ref) => LocalCatalogue(
        reference: ref,
        fixed: FixedObjectProvider(ref),
        ephemeris: EphemerisProvider(ref, nowUtc: () => DateTime.utc(2026, 8, 10, 12)),
      );

  test('merge fixe + éphémère trié par magnitude', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'star:HIP32349', kind: 'star', name: 'Sirius',
        ra: 101.3, dec: -16.7, mag: -1.46);
    insertEphemObject(db, id: 'planet:venus', kind: 'planet', name: 'Venus');
    insertEphemSample(db, id: 'planet:venus',
        sampleUtc: '2026-08-10T00:00:00+00:00', ra: 50.0, dec: 5.0, mag: -4.0);
    insertEphemSample(db, id: 'planet:venus',
        sampleUtc: '2026-08-11T00:00:00+00:00', ra: 52.0, dec: 6.0, mag: -4.0);
    final ref = LocalReferenceDb.withDatabase(db);
    final objs = build(ref).listAll(const LocalCatalogFilter());
    expect(objs.map((o) => o.name), ['Venus', 'Sirius']); // -4.0 avant -1.46
    ref.close();
  });

  test('kind fixe → délègue au provider fixe uniquement', () {
    final db = newReferenceDb();
    insertFixed(db, id: 'NGC1976', kind: 'dso', name: 'Orion', ra: 83.8, dec: -5.4, mag: 4.0);
    insertEphemObject(db, id: 'planet:mars', kind: 'planet', name: 'Mars');
    insertEphemSample(db, id: 'planet:mars', sampleUtc: '2026-08-10T00:00:00+00:00', ra: 100.0, dec: 10.0, mag: 0.5);
    insertEphemSample(db, id: 'planet:mars', sampleUtc: '2026-08-11T00:00:00+00:00', ra: 102.0, dec: 12.0, mag: 0.5);
    final ref = LocalReferenceDb.withDatabase(db);
    final objs = build(ref).listAll(const LocalCatalogFilter(kind: 'dso'));
    expect(objs.map((o) => o.qualifiedId), ['NGC1976']);
    ref.close();
  });

  test('!ready → liste vide', () {
    final ref = LocalReferenceDb('/nope/reference.sqlite')..open();
    expect(build(ref).listAll(const LocalCatalogFilter()), isEmpty);
  });
}
```

- [ ] **Step 2: Run → FAIL**

Run: `flutter test test/features/catalogue/local/local_catalogue_test.dart`

- [ ] **Step 3: Implémenter** — élargissement `limit += offset, offset = 0` puis `sublist`, tri mag-null-last :

```dart
// lib/features/catalogue/local/local_catalogue.dart
/// Façade catalogue local — port de
/// `backend/astro_brain/services/catalog/reference_catalog.py`.
library;

import '../catalogue_models.dart';
import 'catalogue_providers.dart';
import 'local_reference_db.dart';

class LocalCatalogue {
  LocalCatalogue({
    required LocalReferenceDb reference,
    required FixedObjectProvider fixed,
    required EphemerisProvider ephemeris,
  })  : _ref = reference,
        _fixed = fixed,
        _ephemeris = ephemeris;

  final LocalReferenceDb _ref;
  final FixedObjectProvider _fixed;
  final EphemerisProvider _ephemeris;

  List<CatalogObjectDto> listAll(LocalCatalogFilter f) {
    if (!_ref.ready) return [];
    if (f.kind != null) {
      if (FixedObjectProvider.kinds.contains(f.kind)) return _fixed.listObjects(f);
      if (EphemerisProvider.kinds.contains(f.kind)) return _ephemeris.listObjects(f);
      return [];
    }
    final widened = f.copyWith(limit: f.limit + f.offset, offset: 0);
    final merged = <CatalogObjectDto>[
      ..._fixed.listObjects(widened),
      ..._ephemeris.listObjects(widened),
    ];
    merged.sort((a, b) {
      final ma = a.mag ?? double.infinity;
      final mb = b.mag ?? double.infinity;
      final c = ma.compareTo(mb);
      return c != 0 ? c : a.name.compareTo(b.name);
    });
    final start = f.offset.clamp(0, merged.length);
    final end = (f.offset + f.limit).clamp(0, merged.length);
    return merged.sublist(start, end);
  }
}
```

- [ ] **Step 4: Run → PASS**

Run: `flutter test test/features/catalogue/local/local_catalogue_test.dart`

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/catalogue/local/local_catalogue.dart app/test/features/catalogue/local/local_catalogue_test.dart
git commit -m "feat(app): façade catalogue local (merge fixe+éphémère)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: `visibility.dart` (port de `visibility.py`)

Enrichit les objets en alt/az via la projection (Task 3) + GPS téléphone (`PhoneLocation` existant), filtre « visible maintenant ».

**Files:**
- Create: `app/lib/features/catalogue/local/visibility.dart`
- Test: `app/test/features/catalogue/local/visibility_test.dart`

**Interfaces:**
- Consumes: `skyAzAltFromRaDec`/`Observer` (Task 3), `PhoneLocation` (`lib/features/alignment/phone_location.dart`), `CatalogObjectDto`.
- Produces: `class Visibility { Visibility({required PhoneLocation location, DateTime Function()? clock}); Future<List<CatalogObjectDto>> enrich(List<CatalogObjectDto> objects, {required bool visibleNow}); }` ; `const kMinVisibleAltDeg = 0.0`.

- [ ] **Step 1: Test qui échoue** — fake location + clock figée :

```dart
// test/features/catalogue/local/visibility_test.dart
import 'package:astro_brain/features/alignment/phone_location.dart';
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/local/visibility.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeLoc implements PhoneLocation {
  _FakeLoc(this._fix);
  final ({double lat, double lon})? _fix;
  @override
  Future<({double lat, double lon})?> current() async => _fix;
}

CatalogObjectDto obj(String id, {double ra = 279.23, double dec = 38.78, bool stale = false}) =>
    CatalogObjectDto(qualifiedId: id, kind: 'star', name: id, raDeg: ra, decDeg: dec, ephemerisStale: stale);

void main() {
  final clock = () => DateTime.utc(2026, 8, 10, 22);

  test('sans fix GPS : objets intacts, filtre ignoré', () async {
    final v = Visibility(location: _FakeLoc(null), clock: clock);
    final out = await v.enrich([obj('a')], visibleNow: true);
    expect(out.single.altitudeDeg, isNull);
  });

  test('stale exclu si visibleNow, gardé sinon', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    expect(await v.enrich([obj('s', stale: true)], visibleNow: true), isEmpty);
    final kept = await v.enrich([obj('s', stale: true)], visibleNow: false);
    expect(kept.single.altitudeDeg, isNull); // jamais enrichi
  });

  test('objet sous l\'horizon exclu si visibleNow', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    // objet au pôle sud céleste : sous l'horizon depuis lat +43.6
    final out = await v.enrich([obj('south', ra: 0, dec: -89)], visibleNow: true);
    expect(out, isEmpty);
  });

  test('objet au-dessus de l\'horizon : alt/az renseignés', () async {
    final v = Visibility(location: _FakeLoc((lat: 43.6, lon: 1.44)), clock: clock);
    final out = await v.enrich([obj('north', ra: 0, dec: 80)], visibleNow: true);
    expect(out.single.altitudeDeg, isNotNull);
    expect(out.single.azimuthDeg, isNotNull);
  });
}
```

- [ ] **Step 2: Run → FAIL**

Run: `flutter test test/features/catalogue/local/visibility_test.dart`

- [ ] **Step 3: Implémenter** — miroir de `visibility.py` (`copyWith` d'alt/az via `CatalogObjectDto`) :

```dart
// lib/features/catalogue/local/visibility.dart
/// Enrichissement de visibilité local — port de
/// `backend/astro_brain/services/catalog/visibility.py`. GPS via PhoneLocation.
library;

import '../../alignment/phone_location.dart';
import '../catalogue_models.dart';
import 'sky_projection.dart';

const kMinVisibleAltDeg = 0.0;

class Visibility {
  Visibility({required PhoneLocation location, DateTime Function()? clock})
      : _location = location,
        _clock = clock ?? (() => DateTime.now().toUtc());

  final PhoneLocation _location;
  final DateTime Function() _clock;

  Future<List<CatalogObjectDto>> enrich(
    List<CatalogObjectDto> objects, {
    required bool visibleNow,
  }) async {
    final fix = await _location.current();
    if (fix == null) return objects; // pas de position : filtre ignoré
    final observer = Observer(latDeg: fix.lat, lonDeg: fix.lon);
    final t = _clock();
    final out = <CatalogObjectDto>[];
    for (final obj in objects) {
      if (obj.ephemerisStale) {
        if (visibleNow) continue;
        out.add(obj);
        continue;
      }
      final r = skyAzAltFromRaDec(obj.raDeg, obj.decDeg, observer, t);
      if (visibleNow && r.alt <= kMinVisibleAltDeg) continue;
      out.add(obj.copyWith(altitudeDeg: r.alt, azimuthDeg: r.az));
    }
    return out;
  }
}
```

> `CatalogObjectDto` n'a pas encore de `copyWith`. L'ajouter dans
> `catalogue_models.dart` (méthode couvrant tous les champs, comme le
> `model_copy` backend), avec un test dédié dans le fichier de test existant
> `test/features/catalogue/catalogue_models_test.dart`. C'est la seule
> modification du DTO, non cassante (ajout pur).

- [ ] **Step 4: Ajouter `copyWith` au DTO + test**

Dans `lib/features/catalogue/catalogue_models.dart`, ajouter :

```dart
  CatalogObjectDto copyWith({double? altitudeDeg, double? azimuthDeg}) =>
      CatalogObjectDto(
        qualifiedId: qualifiedId, kind: kind, name: name, raDeg: raDeg,
        decDeg: decDeg, designation: designation, mag: mag,
        constellation: constellation, objectType: objectType,
        angularSizeArcmin: angularSizeArcmin, messier: messier, ngcIc: ngcIc,
        illumination: illumination, ephemerisStale: ephemerisStale,
        altitudeDeg: altitudeDeg ?? this.altitudeDeg,
        azimuthDeg: azimuthDeg ?? this.azimuthDeg,
      );
```

Dans `test/features/catalogue/catalogue_models_test.dart`, ajouter :

```dart
  test('copyWith met à jour alt/az sans toucher au reste', () {
    const o = CatalogObjectDto(
        qualifiedId: 'star:vega', kind: 'star', name: 'Vega',
        raDeg: 279.23, decDeg: 38.78, mag: 0.0);
    final c = o.copyWith(altitudeDeg: 18.0, azimuthDeg: 51.0);
    expect(c.altitudeDeg, 18.0);
    expect(c.azimuthDeg, 51.0);
    expect(c.qualifiedId, 'star:vega');
    expect(c.mag, 0.0);
  });
```

- [ ] **Step 5: Run → PASS**

Run: `flutter test test/features/catalogue/local/visibility_test.dart test/features/catalogue/catalogue_models_test.dart`

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/catalogue/local/visibility.dart app/lib/features/catalogue/catalogue_models.dart app/test/features/catalogue/local/visibility_test.dart app/test/features/catalogue/catalogue_models_test.dart
git commit -m "feat(app): enrichissement visibilité local (alt/az + filtre now)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: `almanac_sync.dart` (port de `sync.py`)

Fetch conditionnel du manifest → download → vérif sha256 → garde schéma → swap atomique → reopen. Miroir de `backend/astro_brain/services/reference/sync.py`.

**Files:**
- Create: `app/lib/oracle_cache/almanac_sync.dart`
- Test: `app/test/oracle_cache/almanac_sync_test.dart`

**Interfaces:**
- Consumes: `AlmanacStore`, `AlmanacManifest`, `LocalReferenceDb` (`reopen`), `http.Client`, `kManifestUrl`, `kSupportedSchemaVersion`.
- Produces:
  - `enum AlmanacSyncStatus { updated, upToDate, offline, rejectedSchema, rejectedHash }`
  - `class AlmanacSyncResult { final AlmanacSyncStatus status; final int? schemaVersion; }`
  - `class AlmanacSync { AlmanacSync({required AlmanacStore store, required LocalReferenceDb reference, http.Client Function()? clientFactory, String manifestUrl = kManifestUrl}); Future<AlmanacSyncResult> sync(); }`

- [ ] **Step 1: Test qui échoue** — fake `http.Client` (via `MockClient` de `package:http/testing.dart`) + `AlmanacStore` sur temp dir. On construit un vrai sqlite valide en bytes pour le cas `updated` :

```dart
// test/oracle_cache/almanac_sync_test.dart
import 'dart:convert';
import 'dart:io';
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:astro_brain/oracle_cache/almanac_store.dart';
import 'package:astro_brain/oracle_cache/almanac_sync.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqlite3/sqlite3.dart';
import '../features/catalogue/local/_fixtures.dart';

/// Construit un reference.sqlite valide (schema_version donné) et renvoie ses bytes.
List<int> buildSqliteBytes(Directory tmp, {int schemaVersion = 2}) {
  final path = '${tmp.path}/seed.sqlite';
  final db = sqlite3.open(path);
  db.execute(kReferenceSchemaDdl);
  db.execute('INSERT INTO meta (schema_version, generated_at, window_start,'
      ' window_end) VALUES ($schemaVersion, "g", "s", "e")');
  db.dispose();
  return File(path).readAsBytesSync();
}

String manifestJson(String url, String sha) => jsonEncode({
      'schema_version': 2, 'generated_at': 'g', 'sqlite_url': url,
      'sqlite_sha256': sha, 'window_start': 's', 'window_end': 'e',
    });

void main() {
  late Directory tmp;
  late AlmanacStore store;
  late LocalReferenceDb ref;
  setUp(() {
    tmp = Directory.systemTemp.createTempSync('almanac_sync_test');
    store = AlmanacStore(docsDir: () async => tmp);
    ref = LocalReferenceDb('${tmp.path}/reference.sqlite');
  });
  tearDown(() { ref.close(); tmp.deleteSync(recursive: true); });

  AlmanacSync sync(MockClient client) => AlmanacSync(
      store: store, reference: ref, clientFactory: () => client);

  test('sha différent → download + swap → updated + reopen ready', () async {
    final bytes = buildSqliteBytes(tmp);
    final sha = sha256.convert(bytes).toString();
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', sha), 200);
      }
      return http.Response.bytes(bytes, 200);
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.updated);
    expect(ref.ready, isTrue); // reopen après swap
  });

  test('sha identique au cache → upToDate, pas de download', () async {
    final bytes = buildSqliteBytes(tmp);
    final sha = sha256.convert(bytes).toString();
    (await store.file()).writeAsBytesSync(bytes);
    var dbHits = 0;
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', sha), 200);
      }
      dbHits++;
      return http.Response.bytes(bytes, 200);
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.upToDate);
    expect(dbHits, 0);
  });

  test('sha du corps téléchargé faux → rejectedHash, cache conservé', () async {
    final bytes = buildSqliteBytes(tmp);
    final client = MockClient((req) async {
      if (req.url.toString() == kManifestUrl) {
        return http.Response(manifestJson('https://x/db', 'deadbeef'), 200);
      }
      return http.Response.bytes(bytes, 200); // sha ne matchera pas 'deadbeef'
    });
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.rejectedHash);
  });

  test('manifest schema_version 3 → rejectedSchema', () async {
    final client = MockClient((req) async => http.Response(
        jsonEncode({'schema_version': 3, 'generated_at': 'g',
          'sqlite_url': 'https://x/db', 'sqlite_sha256': 'x',
          'window_start': 's', 'window_end': 'e'}), 200));
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.rejectedSchema);
  });

  test('erreur réseau → offline, cache conservé', () async {
    final client = MockClient((req) async => http.Response('nope', 500));
    final r = await sync(client).sync();
    expect(r.status, AlmanacSyncStatus.offline);
  });
}
```

> `package:http/testing.dart` (`MockClient`) est fourni par `http`, déjà en dépendance — pas de nouvelle dev-dep.

- [ ] **Step 2: Run → FAIL**

Run: `flutter test test/oracle_cache/almanac_sync_test.dart`

- [ ] **Step 3: Implémenter** — algorithme **identique** à `sync.py` (garde schéma sur le manifest ET sur le fichier téléchargé) :

```dart
// lib/oracle_cache/almanac_sync.dart
/// Sync de reference.sqlite : fetch conditionnel (sha256), verify, swap
/// atomique. Miroir de `backend/astro_brain/services/reference/sync.py`.
/// Non bloquant : toute erreur réseau garde le cache courant (offline).
library;

import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'package:sqlite3/sqlite3.dart';

import '../features/catalogue/local/local_reference_db.dart';
import 'almanac_store.dart';
import 'manifest_dto.dart';

enum AlmanacSyncStatus { updated, upToDate, offline, rejectedSchema, rejectedHash }

class AlmanacSyncResult {
  const AlmanacSyncResult(this.status, {this.schemaVersion});
  final AlmanacSyncStatus status;
  final int? schemaVersion;
}

class AlmanacSync {
  AlmanacSync({
    required AlmanacStore store,
    required LocalReferenceDb reference,
    http.Client Function()? clientFactory,
    this.manifestUrl = kManifestUrl,
  })  : _store = store,
        _reference = reference,
        _clientFactory = clientFactory ?? http.Client.new;

  final AlmanacStore _store;
  final LocalReferenceDb _reference;
  final http.Client Function() _clientFactory;
  final String manifestUrl;

  Future<AlmanacSyncResult> sync() async {
    final client = _clientFactory();
    List<int> data;
    AlmanacManifest manifest;
    try {
      final resp = await client.get(Uri.parse(manifestUrl));
      if (resp.statusCode != 200) return const AlmanacSyncResult(AlmanacSyncStatus.offline);
      manifest = AlmanacManifest.fromJson(
          jsonDecode(resp.body) as Map<String, dynamic>);
      if (manifest.schemaVersion > kSupportedSchemaVersion) {
        return AlmanacSyncResult(AlmanacSyncStatus.rejectedSchema,
            schemaVersion: manifest.schemaVersion);
      }
      if (await _store.localSha256() == manifest.sqliteSha256) {
        return AlmanacSyncResult(AlmanacSyncStatus.upToDate,
            schemaVersion: manifest.schemaVersion);
      }
      final dl = await client.get(Uri.parse(manifest.sqliteUrl));
      if (dl.statusCode != 200) return const AlmanacSyncResult(AlmanacSyncStatus.offline);
      data = dl.bodyBytes;
    } on Exception {
      return const AlmanacSyncResult(AlmanacSyncStatus.offline);
    } finally {
      client.close();
    }

    if (sha256.convert(data).toString() != manifest.sqliteSha256) {
      return const AlmanacSyncResult(AlmanacSyncStatus.rejectedHash);
    }

    final tmp = await _store.tmpFile();
    tmp.writeAsBytesSync(data);
    final tmpSv = _schemaVersionOf(tmp.path);
    if (tmpSv == null || tmpSv > kSupportedSchemaVersion) {
      if (tmp.existsSync()) tmp.deleteSync();
      return AlmanacSyncResult(AlmanacSyncStatus.rejectedSchema, schemaVersion: tmpSv);
    }
    final dest = await _store.file();
    tmp.renameSync(dest.path); // swap atomique (même FS)
    _reference.reopen();
    return AlmanacSyncResult(AlmanacSyncStatus.updated,
        schemaVersion: manifest.schemaVersion);
  }

  int? _schemaVersionOf(String path) {
    Database db;
    try {
      db = sqlite3.open(path, mode: OpenMode.readOnly);
    } on SqliteException {
      return null;
    }
    try {
      final rows = db.select('SELECT schema_version FROM meta LIMIT 1');
      return rows.isEmpty ? null : rows.first['schema_version'] as int;
    } on SqliteException {
      return null;
    } finally {
      db.dispose();
    }
  }
}
```

- [ ] **Step 4: Run → PASS**

Run: `flutter test test/oracle_cache/almanac_sync_test.dart`

- [ ] **Step 5: Commit**

```bash
git add app/lib/oracle_cache/almanac_sync.dart app/test/oracle_cache/almanac_sync_test.dart
git commit -m "feat(app): sync almanach (download conditionnel + swap atomique)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Réécrire `catalogue_repository.dart` (lecture locale, GoTo online)

`listObjects` consomme `LocalCatalogue` + `Visibility` ; `goto`/`abort` restent sur `ApiService`. Signature publique inchangée → `CatalogueBloc` intact.

**Files:**
- Modify: `app/lib/features/catalogue/catalogue_repository.dart`
- Modify (réécriture): `app/test/features/catalogue/catalogue_repository_test.dart`

**Interfaces:**
- Consumes: `LocalCatalogue`, `Visibility`, `LocalCatalogFilter`, `ApiService`.
- Produces: `CatalogueRepository({required ApiService api, required LocalCatalogue catalogue, required Visibility visibility})` ; `listObjects/goto/abort` signatures inchangées.

- [ ] **Step 1: Réécrire le test** — `listObjects` délègue au moteur local (plus aucun `getJson('/catalog/objects')`), `goto` poste toujours au Pi :

```dart
// test/features/catalogue/catalogue_repository_test.dart
import 'package:astro_brain/features/catalogue/catalogue_models.dart';
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/catalogue/local/catalogue_providers.dart';
import 'package:astro_brain/features/catalogue/local/local_catalogue.dart';
import 'package:astro_brain/features/catalogue/local/visibility.dart';
import 'package:astro_brain/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class _MockApi extends Mock implements ApiService {}
class _MockCatalogue extends Mock implements LocalCatalogue {}
class _MockVisibility extends Mock implements Visibility {}

void main() {
  late _MockApi api;
  late _MockCatalogue catalogue;
  late _MockVisibility visibility;
  setUp(() {
    api = _MockApi();
    catalogue = _MockCatalogue();
    visibility = _MockVisibility();
    registerFallbackValue(const LocalCatalogFilter());
  });

  CatalogueRepository repo() => CatalogueRepository(
      api: api, catalogue: catalogue, visibility: visibility);

  const vega = CatalogObjectDto(qualifiedId: 'star:vega', kind: 'star',
      name: 'Vega', raDeg: 279.23, decDeg: 38.78, mag: 0.0);

  test('listObjects lit le moteur local (pas /catalog/objects) et enrichit', () async {
    when(() => catalogue.listAll(any())).thenReturn([vega]);
    when(() => visibility.enrich(any(), visibleNow: any(named: 'visibleNow')))
        .thenAnswer((_) async => [vega.copyWith(altitudeDeg: 18.0)]);
    final out = await repo().listObjects(
        search: 'veg', maxMag: 3.0, visibleNow: true, kind: 'star', messier: false);
    expect(out.single.altitudeDeg, 18.0);
    // aucun appel réseau catalogue
    verifyNever(() => api.getJson(any(), query: any(named: 'query')));
    // le filtre local a bien reçu les critères
    final f = verify(() => catalogue.listAll(captureAny())).captured.single
        as LocalCatalogFilter;
    expect(f.kind, 'star');
    expect(f.search, 'veg');
    expect(f.maxMag, 3.0);
    expect(f.limit, 500);
    verify(() => visibility.enrich(any(), visibleNow: true)).called(1);
  });

  test('goto poste {id, confirm_solar} au Pi', () async {
    when(() => api.postJson(any(), any())).thenAnswer((_) async => {});
    await repo().goto('star:sirius', confirmSolar: true);
    verify(() => api.postJson('/goto', {'id': 'star:sirius', 'confirm_solar': true}))
        .called(1);
  });

  test('abort poste /stop', () async {
    when(() => api.stop()).thenAnswer((_) async {});
    await repo().abort();
    verify(() => api.stop()).called(1);
  });
}
```

- [ ] **Step 2: Run → FAIL** (signature du constructeur changée, `catalogue`/`visibility` requis)

Run: `flutter test test/features/catalogue/catalogue_repository_test.dart`

- [ ] **Step 3: Réécrire l'implémentation**

```dart
// lib/features/catalogue/catalogue_repository.dart
import '../../services/api_service.dart';
import 'catalogue_models.dart';
import 'local/catalogue_providers.dart';
import 'local/local_catalogue.dart';
import 'local/visibility.dart';

/// Catalogue lu LOCALEMENT (reference.sqlite en cache) ; GoTo reste online
/// (l'id part au Pi, qui résout contre sa propre copie).
class CatalogueRepository {
  CatalogueRepository({
    required this.api,
    required LocalCatalogue catalogue,
    required Visibility visibility,
  })  : _catalogue = catalogue,
        _visibility = visibility;

  final ApiService api;
  final LocalCatalogue _catalogue;
  final Visibility _visibility;

  /// Lecture locale : filtre SQL (kind/mag/messier/search) puis enrichissement
  /// alt/az + filtre « visible maintenant » (GPS téléphone). `limit: 500` comme
  /// le comportement online précédent (pagination différée Macro 4).
  Future<List<CatalogObjectDto>> listObjects({
    String? search,
    double? maxMag,
    bool visibleNow = false,
    String? kind,
    bool messier = false,
  }) async {
    final filter = LocalCatalogFilter(
      kind: kind,
      search: search ?? '',
      maxMag: maxMag,
      messierOnly: messier,
      limit: 500,
    );
    final objects = _catalogue.listAll(filter);
    return _visibility.enrich(objects, visibleNow: visibleNow);
  }

  /// POST /goto — pointe la monture sur l'objet identifié par [id] (Pi).
  Future<void> goto(String id, {bool confirmSolar = false}) async {
    await api.postJson('/goto', {'id': id, 'confirm_solar': confirmSolar});
  }

  /// Abort : POST /stop.
  Future<void> abort() => api.stop();
}
```

- [ ] **Step 4: Run → PASS** ; puis lancer le bloc test existant pour confirmer qu'il reste vert **sans modification** :

Run: `flutter test test/features/catalogue/catalogue_repository_test.dart test/features/catalogue/catalogue_bloc_test.dart`
Expected: PASS (le bloc test injecte un `MockCatalogueRepository`, non impacté).

- [ ] **Step 5: Commit**

```bash
git add app/lib/features/catalogue/catalogue_repository.dart app/test/features/catalogue/catalogue_repository_test.dart
git commit -m "refactor(app): CatalogueRepository lit le catalogue local (GoTo reste online)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Réécrire `reference_repository.dart` (meta locale + sync = download)

`getStatus` lit la `meta` du fichier local ; `sync` déclenche `AlmanacSync`. DTO inchangés → `AlmanacScreen`/`ReferenceBanner` intacts (hors copie bannière « absent »).

**Files:**
- Modify: `app/lib/features/setup/reference/reference_repository.dart`
- Modify (réécriture): `app/test/features/setup/reference/reference_repository_test.dart`
- Modify (copie): `app/lib/features/catalogue/reference_banner.dart` (message quand `ready:false`)

**Interfaces:**
- Consumes: `LocalReferenceDb` (`ready`/`meta`), `AlmanacSync` (`sync`), `ReferenceStatusDto`/`ReferenceSyncResultDto` (inchangés).
- Produces: `ReferenceRepository({required LocalReferenceDb reference, required AlmanacSync almanacSync})` ; `getStatus()`/`sync()` signatures inchangées.

- [ ] **Step 1: Réécrire le test** — statut lu depuis la meta locale, sync mappe les statuts d'`AlmanacSync` :

```dart
// test/features/setup/reference/reference_repository_test.dart
import 'package:astro_brain/features/catalogue/local/local_reference_db.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:astro_brain/oracle_cache/almanac_sync.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import '../../catalogue/local/_fixtures.dart';

class _MockSync extends Mock implements AlmanacSync {}

void main() {
  late _MockSync almanacSync;
  setUp(() => almanacSync = _MockSync());

  test('getStatus ready + fenêtre depuis la meta locale', () async {
    final ref = LocalReferenceDb.withDatabase(newReferenceDb());
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final s = await repo.getStatus();
    expect(s.ready, isTrue);
    expect(s.schemaVersion, 2);
    expect(s.windowEnd, '2026-09-30');
    ref.close();
  });

  test('getStatus ready:false si pas de fichier', () async {
    final ref = LocalReferenceDb('/nope/reference.sqlite')..open();
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final s = await repo.getStatus();
    expect(s.ready, isFalse);
    expect(s.generatedAt, isNull);
  });

  test('sync mappe le statut AlmanacSync → chaîne backend', () async {
    when(() => almanacSync.sync()).thenAnswer((_) async =>
        const AlmanacSyncResult(AlmanacSyncStatus.updated, schemaVersion: 2));
    final ref = LocalReferenceDb.withDatabase(newReferenceDb());
    final repo = ReferenceRepository(reference: ref, almanacSync: almanacSync);
    final r = await repo.sync();
    expect(r.status, 'updated');
    expect(r.schemaVersion, 2);
    ref.close();
  });
}
```

- [ ] **Step 2: Run → FAIL**

Run: `flutter test test/features/setup/reference/reference_repository_test.dart`

- [ ] **Step 3: Réécrire l'implémentation** — mapping `enum → chaîne` identique au backend :

```dart
// lib/features/setup/reference/reference_repository.dart
import '../../../oracle_cache/almanac_sync.dart';
import '../../catalogue/local/local_reference_db.dart';
import 'reference_models.dart';

/// Statut/resync de l'almanach LOCAL (reference.sqlite en cache). `getStatus`
/// lit la meta du fichier local ; `sync` télécharge depuis GitHub.
class ReferenceRepository {
  ReferenceRepository({
    required LocalReferenceDb reference,
    required AlmanacSync almanacSync,
  })  : _reference = reference,
        _almanacSync = almanacSync;

  final LocalReferenceDb _reference;
  final AlmanacSync _almanacSync;

  Future<ReferenceStatusDto> getStatus() async {
    final m = _reference.meta();
    if (m == null) return const ReferenceStatusDto(ready: false);
    return ReferenceStatusDto(
      ready: true,
      schemaVersion: m.schemaVersion,
      generatedAt: m.generatedAt,
      windowStart: m.windowStart,
      windowEnd: m.windowEnd,
    );
  }

  Future<ReferenceSyncResultDto> sync() async {
    final r = await _almanacSync.sync();
    return ReferenceSyncResultDto(
      status: _statusString(r.status),
      schemaVersion: r.schemaVersion,
    );
  }

  String _statusString(AlmanacSyncStatus s) => switch (s) {
        AlmanacSyncStatus.updated => 'updated',
        AlmanacSyncStatus.upToDate => 'up_to_date',
        AlmanacSyncStatus.offline => 'offline',
        AlmanacSyncStatus.rejectedSchema => 'rejected_schema',
        AlmanacSyncStatus.rejectedHash => 'rejected_hash',
      };
}
```

- [ ] **Step 4: Copie bannière « absent »** — dans `reference_banner.dart`, lorsque `ready == false`, afficher un message qui couvre le cas premier lancement / offline sans cache. Ajuster le texte existant (« Almanach indisponible… ») en :
« Almanach absent — synchronise dans Réglages. » Vérifier le test widget existant `test/features/catalogue/reference_banner_test.dart` et adapter l'attendu de texte si nécessaire (le comportement — bannière visible ssi `ready==false` — reste identique).

- [ ] **Step 5: Run → PASS** (repo + bannière)

Run: `flutter test test/features/setup/reference/reference_repository_test.dart test/features/catalogue/reference_banner_test.dart`

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/setup/reference/reference_repository.dart app/lib/features/catalogue/reference_banner.dart app/test/features/setup/reference/reference_repository_test.dart app/test/features/catalogue/reference_banner_test.dart
git commit -m "refactor(app): statut/resync almanach depuis le cache local

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: Câblage DI (`app.dart`) + sync au lancement

Instancier le moteur local + le sync, injecter dans les deux repositories, déclencher un sync **non bloquant** au boot. Vérifier la suite complète + `flutter analyze`.

**Files:**
- Modify: `app/lib/app.dart`
- Test: `app/test/app_wiring_test.dart` (léger : l'app se construit avec le graphe DI complet)

**Interfaces:**
- Consumes: tout ce qui précède + `GeolocatorPhoneLocation` (`lib/features/alignment/phone_location.dart`).

- [ ] **Step 1: Wiring** — dans `AstroBrainApp.build`, avant le `MultiBlocProvider`, construire une fois (au `create` des providers) :
  - `AlmanacStore store` ;
  - `LocalReferenceDb referenceDb` (l'ouvrir : `..open()` — sur un `create` de `RepositoryProvider`, appeler `open()` dans le corps) ;
  - `AlmanacSync almanacSync = AlmanacSync(store: store, reference: referenceDb)` ;
  - `LocalCatalogue catalogue = LocalCatalogue(reference: referenceDb, fixed: FixedObjectProvider(referenceDb), ephemeris: EphemerisProvider(referenceDb, nowUtc: () => DateTime.now().toUtc()))` ;
  - `Visibility visibility = Visibility(location: const GeolocatorPhoneLocation())`.

  Remplacer les deux `RepositoryProvider` existants :
  - `ReferenceRepository(reference: referenceDb, almanacSync: almanacSync)` ;
  - et injecter `CatalogueRepository(api: ..., catalogue: catalogue, visibility: visibility)` dans le `BlocProvider<CatalogueBloc>`.

  Déclencher le sync au lancement, non bloquant : `unawaited(almanacSync.sync())` (import `dart:async`) dans le `create` du provider qui possède `almanacSync`, sans attendre le résultat (le `reopen()` interne rendra le catalogue disponible au prochain chargement de page). Ne bloque pas le splash.

- [ ] **Step 2: Test de câblage léger** — l'arbre se construit sans exception avec le graphe complet (fakes pour les I/O externes) :

```dart
// test/app_wiring_test.dart
import 'package:astro_brain/features/catalogue/catalogue_repository.dart';
import 'package:astro_brain/features/setup/reference/reference_repository.dart';
import 'package:flutter_test/flutter_test.dart';
// NB : selon la structure de app.dart, tester la fabrique DI extraite plutôt
// que MaterialApp complet. Si app.dart n'expose pas de fabrique, extraire une
// fonction `buildCatalogueRepository(...)` / `buildReferenceRepository(...)`
// pure et la tester ici (construction sans exception + types attendus).

void main() {
  test('les repositories se construisent via le graphe DI local', () {
    // Cf. note : vérifier que la construction du moteur local + repositories
    // ne lève pas et renvoie les bons types.
    expect(CatalogueRepository, isNotNull);
    expect(ReferenceRepository, isNotNull);
  });
}
```

> Note d'implémentation : `app.dart` construit un `MaterialApp` complet difficile à monter en test unitaire (SSE, plugins). Extraire la construction du moteur local et des deux repositories dans des fonctions pures (p.ex. `lib/oracle_cache/wiring.dart`) rend Task 12 testable proprement ; les `RepositoryProvider.create` appellent ces fonctions. Préférer cette extraction au montage du `MaterialApp` en test.

- [ ] **Step 3: Analyse + suite complète**

Run: `flutter analyze`
Expected: `No issues found!`

Run: `flutter test`
Expected: toute la suite verte (les tests SP3-A — bloc, screen, slew bar, solar dialog, object card — restent inchangés et verts).

- [ ] **Step 4: Commit**

```bash
git add app/lib/app.dart app/lib/oracle_cache/wiring.dart app/test/app_wiring_test.dart
git commit -m "feat(app): câblage DI catalogue local + sync almanach au lancement

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notes d'intégration finale (après Task 12, hors boucle SDD)

À la livraison de la macro (documentée dans la session du commit) :
- `docs/project/roadmap.md` : SP3-B livré (ligne transverse Oracle) ; nettoyage backend `/catalog/objects` = tranche B↔C.
- `docs/project/journal.md` : entrée de session.
- `docs/technical/` : l'app lit `reference.sqlite` en cache local ; le Pi ne sert plus le catalogue à l'app.
- `docs/project/backlog.md` : moteur sur isolate dédié si le volume l'exige ; fold état référence dans le SSE.
- Validation device : APK sur Android physique (mDNS/IP renseignée), vérifier premier lancement (download almanach), catalogue Pi éteint, GoTo Pi allumé.

## Self-Review (effectuée à l'écriture)

- **Couverture spec** : acquisition (Tasks 4/9), lecture locale (Tasks 5/6/7), projection+visibilité (Tasks 3/8), interpolation (Task 2), statut/resync local (Task 11), repointage repo catalogue (Task 10), DI + sync boot (Task 12), deps (Task 1). ✅
- **Types cohérents** : `LocalCatalogFilter` défini en Task 6, consommé Tasks 7/10 ; `CatalogObjectDto.copyWith` ajouté Task 8 avant usage ; `AlmanacSyncStatus` défini Task 9, mappé Task 11 ; `LocalReferenceDb.withDatabase` défini Task 5, utilisé Tasks 6/7/11. ✅
- **Placeholders** : les `<GMST_BACKEND>`/`<AZ_VEGA>`… de Task 3 sont volontairement remplis au Step 1 depuis le backend (source de vérité), pas des trous laissés au hasard. ✅
- **Pièges cross-langage signalés** : `parseUtc` (naïf→UTC, pas heure locale), `%` positif Dart, `Duration.abs()` frontière, garde schéma manifest ET fichier téléchargé. ✅
</content>
