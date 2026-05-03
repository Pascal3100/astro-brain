import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'services/pi_host.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final host = PiHost.fromPrefs(prefs);
  runApp(AstroBrainApp(prefs: prefs, host: host));
}
