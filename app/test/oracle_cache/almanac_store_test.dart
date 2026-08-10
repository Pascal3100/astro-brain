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
