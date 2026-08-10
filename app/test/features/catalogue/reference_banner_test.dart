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
