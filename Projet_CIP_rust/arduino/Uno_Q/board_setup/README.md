# board_setup — CIP UDP Forward

## Pourquoi ce dossier existe

App Lab tourne le code Python dans un **conteneur Docker** isolé. Docker expose uniquement les ports TCP définis dans `app.yaml`. Le protocole EtherNet/IP CIP utilise :

- **TCP 44818** — session EIP (ForwardOpen, RegisterSession) → exposé par App Lab ✓
- **UDP 2222** — échange I/O cyclique O→T / T→O → **non exposé** ✗

Les paquets O→T (données du PLC vers l'Arduino) arrivent bien sur la board, mais ne sont jamais transmis au conteneur. Ce service corrige ça avec une règle `iptables DNAT`.

---

## Fonctionnement

`cip-udp-forward.sh` écoute les événements Docker en permanence. Dès qu'un conteneur dont le nom contient `cip` démarre, il :

1. Récupère l'IP du conteneur dynamiquement
2. Supprime l'ancienne règle DNAT si elle existe
3. Insère une nouvelle règle en tête de `PREROUTING` :

```
UDP wlan0:2222 → 172.23.x.x:2222 (conteneur)
```

Si App Lab recrée le conteneur (nouvelle IP), la règle est mise à jour automatiquement.

---

## Installation

Copier le dossier `board_setup/` sur la board, puis :

```bash
bash install.sh
```

Ce script :
- Copie `cip-udp-forward.sh` dans `/usr/local/bin/`
- Installe `cip-udp-forward.service` dans systemd
- Active et démarre le service au boot

---

## Vérification

**Le service tourne :**
```bash
sudo systemctl status cip-udp-forward.service
```
Doit afficher `active (running)`.

**La règle a bien été appliquée (après démarrage de l'app) :**
```bash
sudo journalctl -u cip-udp-forward.service -f
```
Doit afficher une ligne `Rule applied: UDP wlan0:2222 -> 172.23.x.x:2222`.

**Les paquets O→T sont bien reçus par Python :**
```bash
arduino-app-cli app logs user:cip
```
Doit afficher des lignes `UDP RX` et `O->T: CIP Seq=...`.

**La règle iptables est présente :**
```bash
sudo iptables -t nat -L PREROUTING -n -v | grep udp
```

---

## Test de bout en bout

1. Redémarrer la board complètement
2. Lancer l'app depuis App Lab
3. Vérifier `journalctl` → `Rule applied:`
4. Vérifier les logs Python → `UDP RX`
5. Vérifier que `send_cip_data` retourne autre chose que `0x00`

---

## Désinstallation

```bash
bash uninstall.sh
```

Supprime le service systemd, le script, et retire la règle iptables.
