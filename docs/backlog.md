# Backlog — Astro-Brain

Réflexions transverses et idées à creuser pour les versions post-v0.1. Rien ici n'est figé en spec ; l'objectif est de capturer les pistes pour ne pas les perdre et pouvoir les arbitrer plus tard.

Quand un sujet devient prêt à être conçu, il migre vers un spec dans `docs/superpowers/specs/`.

## Page "Réglages techniques monture" (v0.2+)

Paramétrage persistant côté Pi, exposé par l'app :

- **Courses min/max ALT/AZ** — safety pour éviter collision tube/trépied
- **Caractéristiques du tube** (focale, diamètre, obstruction) — prérequis pour filtrage catalogue (v0.4) et calculs FOV astrophoto (v0.5)
- **Compensation de backlash** — améliore tracking et futur GoTo (v0.3)
- Capteurs à réfléchir : nature, nombre, protocole (fin de course mécaniques ? encodeurs ? Hall ?)
- **TODO : auditer la raquette Celestron** — passer en revue tous les menus/réglages techniques exposés par le hand controller (backlash, anti-backlash, cone error, PEC, filter limits, custom slew rates, etc.) pour identifier ce qu'il faut exposer/récupérer côté app et/ou lire/écrire via NexStar

## Configuration des caméras (v0.2+)

Trois caméras dans le setup final, chacune avec ses paramètres propres :

- **Imageur principal** (T7C) : taille pixel, résolution, gain/offset, binning, temps d'expo par défaut
- **Caméra de guidage** (Orion StarShoot Autoguider) : taille pixel, résolution, agressivité/min-move du guidage
- **Plate solving** (même caméra que le guidage en pratique, sur la SV165) : résolution, échelle attendue (arcsec/pixel)
- **Lunette guide** (SV165) : focale — combinée au pixel size de la caméra guide → échelle d'image, indispensable pour calibrer le plate solver (v0.2) et le guideur (v0.5)

Ces réglages sont un prérequis direct du plate solving v0.2 — à spécifier dans le spec v0.2.

## Position persistante + retour à l'origine (v0.2+)

- "Home position" définie physiquement par capteurs (distincte de l'alignement logique Celestron)
- Utilité : reprise après coupure, commande "retour à l'origine"
- À clarifier : peut-on lire directement la position depuis la monture via NexStar (`get_position`) une fois alignée, ou faut-il des encodeurs/capteurs externes indépendants ? Lien avec le plate solving v0.2 qui donnera aussi une position absolue.
- **Piste IMU plutôt que capteurs mécaniques** : le DroTek M8N n'a qu'un magnétomètre (LIS3MDL/HMC5883L), pas d'accéléromètre — il donne le cap seulement à plat, pas l'inclinaison. Ajouter un IMU (MPU6050 accel+gyro ~4€, ICM-20948 9DOF ~10€, ou BNO055 avec fusion intégrée ~20€) fournirait **inclinaison + cap tilt-compensé** en I2C, sans fin de course mécaniques ni encodeurs externes. Option à évaluer quand on creusera ce sujet.

## Safety & robustesse (v0.2+)

- **Arrêt d'urgence** — bouton soft dans l'app (et/ou hardware GPIO) qui force un `stop` sur tous les axes, indépendamment du reste du système. Complément naturel des courses min/max. À concevoir comme un chemin de commande prioritaire, contournant la logique métier.
- **Logs persistants côté Pi** — journalisation structurée des commandes monture, transitions d'état, erreurs série/GPS, événements orchestrateur. Rotation (journald ou logrotate). Permet le post-mortem d'une session ("pourquoi le tracking a décroché à 22h13 ?"). À prévoir dès qu'on aura des sessions réelles.

## Ops & déploiement (à automatiser post-v0.1)

- **Service systemd** pour le backend — aujourd'hui `uv run uvicorn` est lancé à la main sur le Pi. Passer à une unit systemd (start au boot, restart on-failure, logs vers journald).
- **Déploiement backend** — script `deploy.sh` ou cible Make (SSH → `git pull && systemctl restart astro-brain`). Évite le workflow manuel actuel.
- **Mise à jour app Flutter** — pipeline build APK (+ TestFlight/iOS si concerné). À traiter séparément, pas via le Pi.

## Mode "Mise en station" (important — v0.2+)

Assistant guidé dans l'app pour la phase d'installation sur le terrain :

- **Niveau** — mise à niveau du trépied avec retour visuel (accéléromètre de l'IMU évoqué plus haut)
- **Cap nord** — alignement azimut avec le compass (magnétomètre DroTek ou IMU)
- **Alignement étoiles** — procédure 2-star / 3-star NexStar, ou plate solving (v0.2)
- UX critique : cet écran est utilisé dans le noir, avec lampe rouge, parfois à l'aveugle → ergonomie soignée, instructions courtes, pas de couleurs vives en mode nuit
- Lien fort avec l'IMU, le compass, et le plate solving v0.2
