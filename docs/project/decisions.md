# Décisions d'architecture (ADRs)

Décisions structurantes du projet, sous forme de notes courtes. Une décision = un titre + contexte + choix + rationale. Pas un journal — uniquement les décisions qui méritent d'être retrouvables.

---

## 2026-04-15 — Pas d'Arduino dans la chaîne

**Contexte** : design initial prévoyait un Arduino comme intermédiaire entre Pi et monture pour temps-réel.

**Décision** : Pi communique directement avec la monture via USB-série (port HC, protocole NexStar 9600 baud, lib `nexstarpy`).

**Rationale** : la monture Celestron a déjà son micro-contrôleur interne pour le temps-réel moteur. Un Arduino ajouterait une couche série de plus, sans valeur. Le Pi reste réactif via `asyncio.to_thread` pour les appels série bloquants.

---

## 2026-04-15 — REST + SSE, pas de WebSocket

**Décision** : commandes via REST (`/slew`, `/stop`, `/tracking`, `/goto`), état via SSE (`/events`).

**Rationale** : simple à implémenter en FastAPI, simple à consommer en Flutter, compatible HTTP/1.1 partout. Le D-Pad fonctionne en start/stop (pas besoin de bidirectionnel temps-réel). SSE supporte la reconnexion auto.

---

## 2026-04-21 — Capteurs hardware via GPIO uniquement

**Contexte** : le Pi 3 B+ a 4 ports USB. Le projet final aura 3 caméras + monture (USB), ce qui sature.

**Décision** : tous les capteurs (GPS DroTek, compass LIS3MDL, ADXL345 ×2) passent par les GPIO (UART0 + I2C1), pas via USB.

**Rationale** : préserve les ports USB pour la monture et les caméras. Les bus GPIO ont la bande passante nécessaire (NMEA en UART à 9600/38400 bauds, I2C à 400 kHz).

---

## 2026-04-24 — Accéléromètres simples (ADXL345 ×2) plutôt que IMU 9DOF

**Contexte** : besoin de mesurer l'inclinaison du tube (zéro ALT, butées) et la planéité de la monture (mise à niveau).

**Décision** : 2 × ADXL345 (I2C, ~3 € pièce). Pas d'IMU 9DOF (MPU6050/BNO055).

**Rationale** : usage statique pur, la gravité suffit (`atan2(ay, az)`). Pas de fusion de capteurs ni cap tilt-compensé nécessaires (le plate solve v0.5 prendra le relais pour le pointage précis). Les 2 ADXL345 cohabitent sur I2C1 grâce à la pin SDO (`0x53` tube, `0x1D` monture). Précision < 0.5° brute, < 0.1° après calibration.

---

## 2026-04-24 — App Flutter native (pas PWA)

**Décision** : app Flutter native compilée pour Android (et iOS plus tard), pas une PWA servie par le Pi.

**Rationale** : performance et sensation native, accès USB-debug pour smoke test, pas besoin d'un serveur web servant l'app sur le Pi (la complexité d'un setup PWA n'apporte rien de plus qu'un APK installé).

---

## 2026-04-24 — Pattern BLoC pour Flutter

**Décision** : `flutter_bloc` (pattern BLoC, MVVM-like) avec `equatable` pour les états.

**Rationale** : pattern le plus idiomatique pour une app Flutter à état partagé entre écrans (status système global, thème, alignement). Documentation officielle dense (`docs.flutter.dev`), testable via `bloc_test`. Alternatives écartées : Provider seul (pas assez structuré), Riverpod (overkill ici, communauté plus jeune), Redux (verbeux pour le besoin).

---

## 2026-04-29 — Catalogue + calculs astro côté backend

**Décision** : Pi sert le catalogue (Messier, planètes, étoiles brillantes) via REST. Calculs astro (Alt/Az, éphémérides) faits en Python avec `skyfield` / `astropy`. App = client de présentation.

**Rationale** : le Pi a déjà l'heure GPS exacte + la position. Les libs Python d'astro sont matures et précises. Centraliser la logique astro dès maintenant prépare le night planner et le filtrage par visibilité (v0.4+). Inconvénient identifié pour le night planner offline : traité plus tard via pattern snapshot/cache (cf. backlog).

---

## 2026-04-29 — Hub central comme nouveau landing post-Splash

**Décision** : à partir de v0.3, l'app n'arrive plus directement sur le HomeScreen manuel. Splash → Hub agrégateur → écran feature.

**Rationale** : permet d'agréger Manuel / GoTo / Catalogues / Status / Setup / Night planner au fur et à mesure, sans charger un écran feature avec des boutons d'autres modes. Le hub n'affiche que les entrées actives — les autres apparaissent quand elles ont un contenu.

---

## 2026-04-29 — AppBar partagée sur tous les écrans

**Décision** : convention de template — tous les écrans Flutter affichent une AppBar commune contenant pastille de status global + toggle jour/nuit + bouton reconnect conditionnel.

**Rationale** : l'utilisateur veut garder l'état système et le toggle thème accessibles en permanence (utilisation terrain de nuit). Évite la duplication par écran et garantit la cohérence visuelle HUD.

---

## 2026-04-30 — Setup devient v0.2 (avant l'alignement)

**Contexte** : le brainstorm initial visait v0.2 = mise en station 3 étoiles + GoTo + catalogue minimal. En détaillant les prérequis, il est apparu qu'on ne peut pas faire un alignement sérieux sans : compass calibré, ADXL345 calibré, courses définies, backlash compensé.

**Décision** : Setup devient le milestone v0.2. La mise en station + GoTo passe en v0.3. Le décalage propage sur tout le reste.

**Rationale** : shipper un alignement sans calibration capteurs serait shipper une feature qui ne marche pas en pratique. Mieux vaut un Setup robuste qui débloque l'alignement, que l'inverse.

---

## 2026-04-30 — Arborescence de docs en 3 vues

**Décision** : `docs/INDEX.md` référence trois vues — `technical/`, `project/`, `product/`. Chaque vue a un `README.md` index, et regroupe des docs courts et ciblés (1 sujet = 1 fichier).

**Rationale** : faciliter la navigation et minimiser le contexte chargé à chaque session. Un long document monolithique est dur à maintenir et oblige à charger trop de contexte. Trois angles de lecture (technique / projet / produit) couvrent les besoins du dev hybride humain + IA.
