# Backend v0.1 — Manual Integration Checklist

À dérouler sur le Pi une fois `astro-brain.service` déployé avec `ASTRO_BRAIN_HARDWARE=1`. Cocher chaque case et noter les surprises dans la section **Findings** en bas.

Hostname utilisé ici : `astro-brain` (DNS local). Si ça ne résout pas, tomber sur l'IP directe (`192.168.1.36` au dernier check).

---

## 0. Prérequis Pi-level (one-shot)

Ces réglages OS ne sont pas gérés par `install.sh` — à faire manuellement la première fois.

### GPS UART + compass I2C

- [ ] Câblage physique conforme à `docs/hardware_wiring.md` (GPS sur UART0, compass sur I2C1)
- [ ] Dans `/boot/firmware/config.txt` :
  - [ ] `enable_uart=1`
  - [ ] `dtoverlay=disable-bt` (libère le PL011 du Bluetooth pour un UART plus stable)
  - [ ] `dtparam=i2c_arm=on`
- [ ] `sudo systemctl disable --now hciuart` (le service BT n'utilise plus l'UART)
- [ ] Reboot puis `ls -l /dev/serial0` → lien symbolique vers `ttyAMA0`
- [ ] `sudo apt install gpsd gpsd-clients i2c-tools` (si pas déjà fait)
- [ ] Dans `/etc/default/gpsd` : `DEVICES="/dev/serial0"`, `GPSD_OPTIONS="-n"` (démarrage permanent), `START_DAEMON="true"`
- [ ] `sudo systemctl enable --now gpsd.socket gpsd.service`
- [ ] `gpsmon /dev/serial0` affiche des trames NMEA valides (sats visibles, fix ou pas selon ciel)
- [ ] `i2cdetect -y 1` → adresse du compass détectée (typ. `0x1e` ou `0x0d`)

### Monture USB-série

- [ ] Câble USB-série branché entre Pi et port HC de la monture
- [ ] `ls -l /dev/ttyUSB0` existe quand la monture est sous tension
- [ ] `pascal3100` est dans le groupe `dialout` (`groups pascal3100` contient `dialout`, sinon `sudo usermod -aG dialout pascal3100` + re-login)

---

## 1. Service health

- [ ] `sudo systemctl --no-pager status astro-brain.service` → `active (running)`
- [ ] `sudo journalctl -u astro-brain.service -n 50 --no-pager` → pas de traceback récurrent

## 2. Endpoints de base

- [ ] `curl -s http://astro-brain:8000/state | python3 -m json.tool` → 200, 5 subsystems présents (mount, gps, network, system, tracking)
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

- [ ] `gps.state` atteint au moins `searching` dans les 5 s après startup
- [ ] Sous ciel dégagé, `gps.state` atteint `fix_3d` en quelques minutes
- [ ] `gps.details` contient `lat`, `lon`, `satellites`, `hdop` (et `altitude_m` sur fix_3d)
- [ ] Quand `mount.ready` ET `gps.fix_3d` tiennent simultanément, l'orchestrateur déclenche une seule sync : `sudo journalctl -u astro-brain.service | grep -E "(set_time|set_location)"` (ajouter un `logging.info` dans `orchestrator._maybe_sync` si absent)

## 5. Network — smoke test

- [ ] Connecté au Wi-Fi domestique : `network.state=client`, `details.ssid` = SSID home, `details.ip` correspond à `ip -4 -o addr show wlan0`
- [ ] `sudo ip link set wlan0 down` → `network.state=offline` dans les 5 s (attention, ça coupe le SSH aussi — console ou re-up auto)

## 6. System — smoke test

- [ ] `system.state=ok` à l'idle (CPU < 70 °C, load < 1.5)
- [ ] `stress-ng --cpu 4 --timeout 60` fait passer `system.state` à `warning` et propage `overall=orange` dans les 5 s (installer `stress-ng` via apt si besoin)

## 7. Overall state — matrice finale

- [ ] Tout nominal : `overall=green`
- [ ] Monture débranchée : `overall=red`
- [ ] GPS en `searching` seul : `overall=blue`
- [ ] CPU stressé seul : `overall=orange`

---

## Findings

Noter ici toute divergence, comportement surprenant, ou ajustement fait en cours de route.

- _(à remplir pendant la passe)_
