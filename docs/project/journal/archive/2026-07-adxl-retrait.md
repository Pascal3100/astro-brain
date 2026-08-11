# Archive journal — Retrait ADXL345 + Courses ALT (Session 42)

Milestone **de simplification** : retrait des 2× accéléromètres ADXL345 (tube `0x53`, monture `0x1D`) et de la feature Courses ALT — capteurs jamais installés physiquement, hors du chemin de pointage depuis l'ADR 2026-05-10 (modèle SVD/sync natif), garde-fou ALT jamais enforcé. Le compass LIS3MDL (`0x1E`) et le GPS sont conservés. Session 42, 2026-07-17. Précède le fil transverse Oracle (Sessions 43→47), archivé dans [`2026-08-oracle.md`](2026-08-oracle.md).

### Session 42 — Retrait ADXL345 + Courses ALT (2026-07-17)

**Décision** : retirer les 2× ADXL345 (`0x53` tube, `0x1D` monture) et la feature Courses ALT — code, endpoints, écrans Flutter, câblage, docs. Garder le compass LIS3MDL (`0x1E`) et le GPS. Cf. **ADR 2026-07-17** dans [`decisions.md`](../../decisions.md) (supersède l'ADR 2026-04-24).

**Contexte de la décision** : l'installation physique du tube sur la monture n'a jamais été faite. La faire maintenant imposerait de concevoir/imprimer 2 boîtiers 3D pour des capteurs dont la valeur s'est effritée : le modèle SVD/sync natif (ADR 2026-05-10) a mis les ADXL hors du chemin de pointage depuis mai, et un audit de code mené pendant ce retrait a confirmé que la feature Courses ALT n'a **jamais gardé** un slew réel (aucun code de commande n'était conditionné par une lecture tilt) — retrait doc-only sur ce point, pas une régression de sécurité active.

**Périmètre** : backend (services + routes + adapters ADXL), app Flutter (écrans calibration ADXL ×2, courses ALT, bulle virtuelle), schémas de câblage (Task 6, hors scope de cette session docs), et cette passe de documentation (ADR, hardware, roadmap, backlog, CLAUDE.md, README, api/state-model/architecture).

**Conséquence principale** : le compass LIS3MDL passe en heading **non tilt-compensé** (plus d'ADXL co-localisé pour fusionner l'inclinaison) ; la mise à niveau redevient **bulle physique** trépied ; l'anti-collision ALT est repoussée en **Macro 3** via la position monture rapportée par le driver.

**Backlog** : 5 pistes prospectives capturées dans [`backlog.md`](../../backlog.md#reprise--résilience--aide-au-pré-pointage-post-retrait-adxl-macro-3) (résilience reboot Pi en priorité, home/parking + seed-sync, set-zéro ALT à la bulle, compass déporté + déclinaison, coupure totale non gérée).
