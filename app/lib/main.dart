import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'oracle_cache/wiring.dart';
import 'services/pi_host.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final host = PiHost.fromPrefs(prefs);
  final oracle = await buildOracleWiring();
  unawaited(oracle.almanacSync.sync()); // sync almanach non bloquant au lancement
  runApp(AstroBrainApp(prefs: prefs, host: host, oracle: oracle));
}
