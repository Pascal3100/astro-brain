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
