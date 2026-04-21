# Backend v0.1 — Manual Integration Checklist

À dérouler sur le Pi une fois `astro-brain.service` déployé avec `ASTRO_BRAIN_HARDWARE=1`. Cocher chaque case et noter les surprises dans la section **Findings** en bas.

Hostname utilisé ici : `astro-brain` (DNS local). Si ça ne résout pas, tomber sur l'IP directe (`192.168.1.36` au dernier check).

---

## 0. Prérequis Pi-level (one-shot)

Ces réglages OS ne sont pas gérés par `install.sh` — à faire manuellement la première fois.

### GPS UART + compass I2C

- [x] Câblage physique conforme à `docs/hardware_wiring.md` (GPS sur UART0, compass sur I2C1)
- [x] Dans `/boot/firmware/config.txt` :
  - [x] `enable_uart=1`
  - [x] `dtoverlay=disable-bt` (libère le PL011 du Bluetooth pour un UART plus stable)
  - [x] `dtparam=i2c_arm=on`
- [x] Dans `/boot/firmware/cmdline.txt` : retirer `console=serial0,115200` (sinon le kernel log sur la série et pollue les NMEA, + compete le port avec gpsd)
- [x] `sudo systemctl disable --now serial-getty@ttyAMA0.service` (par défaut Pi OS fait tourner une console de login sur ttyAMA0 qui squatte le port et bloque gpsd avec un `SER: already opened by another process`)
- [x] `sudo systemctl disable --now hciuart` (le service BT n'utilise plus l'UART) — _n'existe pas forcément sur Pi OS récent, `disable-bt` suffit_
- [x] Reboot puis `ls -l /dev/serial0` → lien symbolique vers `ttyAMA0`
- [x] `sudo apt install gpsd gpsd-clients i2c-tools` (si pas déjà fait)
- [x] Charger le module userspace I2C : `sudo modprobe i2c-dev` + `echo 'i2c-dev' | sudo tee /etc/modules-load.d/i2c-dev.conf` (sans ça, `dtparam=i2c_arm=on` active le bus hardware mais `/dev/i2c-1` n'apparaît pas)
- [x] Dans `/etc/default/gpsd` : `DEVICES="/dev/serial0"`, `GPSD_OPTIONS="-n"` (démarrage permanent), `START_DAEMON="true"`
- [x] `sudo systemctl enable --now gpsd.socket gpsd.service`
- [x] `gpspipe -w -n 5` affiche un paquet `DEVICES` non-vide (`driver:"u-blox"`) suivi d'au moins un `TPV` avec `mode:3` et un `SKY` avec `uSat>0`
- [x] `i2cdetect -y 1` → adresse du compass détectée (typ. `0x1e` ou `0x0d`)

### Monture USB-série

- [ ] Câble USB-série branché entre Pi et port HC de la monture
- [ ] `ls -l /dev/ttyUSB0` existe quand la monture est sous tension
- [ ] `pascal3100` est dans le groupe `dialout` (`groups pascal3100` contient `dialout`, sinon `sudo usermod -aG dialout pascal3100` + re-login)

---

## 1. Service health

- [x] `sudo systemctl --no-pager status astro-brain.service` → `active (running)`
- [x] `sudo journalctl -u astro-brain.service -n 50 --no-pager` → pas de traceback récurrent

## 2. Endpoints de base

- [x] `curl -s http://astro-brain:8000/state | python3 -m json.tool` → 200, 5 subsystems présents (mount, gps, network, system, tracking)
- [ ] `curl -N http://astro-brain:8000/events` (Ctrl+C pour sortir) → émet `event: snapshot` immédiatement, puis au moins un `event: update` dans les 15 s (ping keep-alive ou publish réel)

## 3. Mount — smoke test

Prérequis : monture sous tension, câble USB branché.

- [ ] Au démarrage, `mount.state` atteint `ready` avec `details.firmware_version` non-null
- [ ] `tracking.state` apparaît à `off` (publish initial dans `NexStarMountAdapter.start()`)
- [ ] `POST /slew` avec `{"axis":"alt","direction":"+","rate":1}` → slew lent visible sur la monture ; `mount.state=moving` avec `details.active_slews` peuplé
- [ ] `POST /stop` avec `{}` → slew arrêté ; `mount.state=ready`
- [ ] `POST /tracking` avec `{"enabled":true}` → drive RA s'engage ; `tracking.state=sidereal`
- [ ] `POST /tracking` avec `{"enabled":false}` → tracking coupé ; `tracking.state=off`
- [ ] Débrancher l'USB brièvement → `mount.state=error` dans ≤ 2 s (watchdog) ; rebranchement + `sudo systemctl restart astro-brain` → `mount.state=ready`

**Si le tracking sidéral ne s'engage pas** : la constante `TRACKING_MODE_SIDEREAL = 1` dans `backend/astro_brain/adapters/nexstar_adapter.py` ne correspond pas au firmware. Essayer 2, puis 3, et mettre à jour une fois identifié.

## 4. GPS — smoke test

Prérequis : section 0 faite, `gpsd` tourne, antenne avec vue dégagée (fenêtre/extérieur).

- [x] `gps.state` atteint au moins `searching` dans les 5 s après startup
- [x] Sous ciel dégagé, `gps.state` atteint `fix_3d` en quelques minutes
- [x] `gps.details` contient `lat`, `lon`, `satellites`, `hdop` (et `altitude_m` sur fix_3d) — `satellites` remonté via sticky-count (voir commit `57e7553`)
- [ ] Quand `mount.ready` ET `gps.fix_3d` tiennent simultanément, l'orchestrateur déclenche une seule sync : `sudo journalctl -u astro-brain.service | grep -E "(set_time|set_location)"` (ajouter un `logging.info` dans `orchestrator._maybe_sync` si absent) — _à valider quand la monture sera branchée_

## 5. Network — smoke test

- [x] Connecté au Wi-Fi domestique : `network.state=client`, `details.ssid` = SSID home, `details.ip` correspond à `ip -4 -o addr show wlan0`
- [ ] `sudo ip link set wlan0 down` → `network.state=offline` dans les 5 s (attention, ça coupe le SSH aussi — console ou re-up auto)

## 6. System — smoke test

- [x] `system.state=ok` à l'idle (CPU < 70 °C, load < 1.5) — observé ~56 °C / load 0.05
- [ ] `stress-ng --cpu 4 --timeout 60` fait passer `system.state` à `warning` et propage `overall=orange` dans les 5 s (installer `stress-ng` via apt si besoin)

## 7. Overall state — matrice finale

- [ ] Tout nominal : `overall=green`
- [ ] Monture débranchée : `overall=red`
- [ ] GPS en `searching` seul : `overall=blue`
- [ ] CPU stressé seul : `overall=orange`

---

## Findings

Noter ici toute divergence, comportement surprenant, ou ajustement fait en cours de route.

### Passe du 2026-04-21 — GPS + I2C + network + system (sans monture)

- **Section 0 incomplète à l'origine** — trois étapes manquaient et ont été ajoutées cette passe :
    1. Charger `i2c-dev` (`dtparam=i2c_arm=on` active le bus hardware mais `/dev/i2c-1` ne s'expose pas sans ce module userspace).
    2. Désactiver `serial-getty@ttyAMA0.service` (une console de login squatte le port série et bloque gpsd avec `SER: already opened by another process`).
    3. Retirer `console=serial0,115200` de `/boot/firmware/cmdline.txt` (le kernel y pousse ses logs et interfère avec les NMEA).
- **Service `hciuart`** n'existe plus sur Pi OS 64-bit Lite récent ; `dtoverlay=disable-bt` suffit.
- **GPS** : u-blox NEO-M8N détecté par gpsd, fix_3d atteint en ~30 s à Toulouse (43.5023 N, 1.5194 E), 14 satellites utilisés, HDOP 0.83. 4 constellations actives (GPS + GLONASS + Galileo + BeiDou).
- **Bug adapter GPS** → fixé commit `57e7553` : `gpsd-py3.get_current()` renvoie le dernier paquet (TPV ou SKY) au lieu d'un état agrégé. Résultat : `details.satellites = 0` la plupart du temps. Fix : cacher la dernière valeur `sats_valid > 0` vue dans une trame SKY.
- **Bug app/adapter mount** → fixé commit `57e7553` : le subsystem `tracking` n'apparaissait dans `/state` que si `NexStarMountAdapter.start()` aboutissait (5 subsystems attendus mais 4 visibles avec monture débranchée). Fix : publier `tracking=off` avant la tentative de connexion.
- **Compass I2C** : c'est un **LIS3MDL** (ST Microelectronics), pas un HMC5883L comme laissait penser la doc `hardware_wiring.md` initiale. Identifié par `WHO_AM_I=0x3D` à l'adresse `0x1E`. Power-down par défaut, activé via `CTRL_REG1=0x1C`/`CTRL_REG3=0x00`/`CTRL_REG4=0x0C` → mesures X/Y/Z live confirmées (magnitude ~0.3-0.9 G qui varie quand on tourne le module). Non utilisé par la v0.1 backend, prêt pour v0.2.
- **Mount** non testée : câble USB pas branché cette passe. La section 3 reste à dérouler lors d'une passe dédiée avec la monture sous tension.
