# EtherNet/IP CIP Adapter — Arduino Uno Q

Adaptateur EtherNet/IP implémenté en Python (`asyncio`) pour permettre à un PLC Rockwell de communiquer avec un MPU Linux embarqué sur une carte Arduino Uno Q.

**Device** : `arduino@NekoNOUnoQ` — `192.120.0.202`  
**PLC** : Rockwell GuardLogix 1769-L36ERMS — `192.120.0.206`

---

## Vue d'ensemble

EtherNet/IP est un protocole industriel qui transporte CIP (Common Industrial Protocol) sur TCP/IP et UDP/IP. La communication se déroule en deux phases distinctes :

```
PLC                                     Arduino (ce programme)
 |                                              |
 |──── TCP 44818 ── RegisterSession ───────────>|  Phase 1 : Session
 |<─── RegisterSession Response ─────────────── |
 |                                              |
 |──── TCP 44818 ── ForwardOpen ───────────────>|  Phase 1 : Connexion I/O
 |<─── ForwardOpen Response ────────────────────|
 |                                              |
 |~~── UDP 2222 ─── O→T (outputs PLC) ─────────>|  Phase 2 : Échange cyclique
 |<~~─ UDP 2222 ─── T→O (inputs Arduino) ───────|
```

### Phase 1 — TCP port 44818

Établissement de la session et de la connexion I/O via des échanges CIP non-connectés (requête/réponse). Le PLC interroge le device pour vérifier son identité, puis envoie un **ForwardOpen** pour ouvrir un canal I/O cyclique.

### Phase 2 — UDP port 2222

Échange de données I/O à cadence fixe (RPI, Requested Packet Interval). Le PLC envoie les sorties (O→T) et l'adaptateur répond avec les entrées (T→O). Ces paquets UDP sont du **CPF brut** — pas de header EIP.

---

## Structure du projet

```
Uno_Q_v2/
├── main.py         Point d'entrée, serveur TCP, dispatcher EIP/CIP
├── eip.py          Header EIP 24 octets (parsing + construction)
├── cpf.py          Common Packet Format (enveloppe des données CIP)
├── cip.py          Services CIP : Identity, TCP/IP Object, ForwardOpen/Close
├── io_server.py    Serveur UDP port 2222, réception O→T, envoi T→O, watchdog
├── JOURNAL.md      Journal de développement (bugs rencontrés, corrections)
└── README.md       Ce fichier
```

---

## Protocole en détail

### 1. EIP Header (eip.py)

Chaque paquet TCP commence par un header de **24 octets** (little-endian) :

```
Offset  Taille  Champ
0       2B      command         (0x0065 RegisterSession, 0x006F SendRRData...)
2       2B      length          (taille du payload qui suit)
4       4B      session_handle  (assigné par l'adaptateur au RegisterSession)
8       4B      status          (0 = succès)
12      8B      sender_context  (opaque, renvoyé en miroir dans la réponse)
20      4B      options         (toujours 0)
```

Le `session_handle` est assigné par **l'adaptateur** (pas le PLC) lors du RegisterSession. Le PLC le réutilise dans tous les paquets suivants.

### 2. CPF — Common Packet Format (cpf.py)

Le CPF enveloppe les données CIP dans les commandes SendRRData (TCP) et dans tous les paquets UDP I/O :

```
item_count (2B LE)
item[]:
    type_id (2B LE)
    length  (2B LE)
    data    (length octets)
```

Types d'items utilisés :

| Type   | Nom                  | Usage |
|--------|----------------------|-------|
| 0x0000 | Null Address         | Item d'adresse vide pour les échanges non-connectés |
| 0x00B2 | Unconnected Data     | Données CIP sur TCP (requêtes/réponses) |
| 0x8002 | Connected Address    | Adresse de connexion I/O (8B : conn_id + encap_seq) |
| 0x00B1 | Connected I/O Data   | Données I/O cycliques sur UDP |
| 0x8000 | O→T Socket Address   | Indique au PLC l'adresse UDP de destination O→T |
| 0x8001 | T→O Socket Address   | Indique au PLC l'adresse UDP de destination T→O |

> **Pourquoi 0x00B1 et pas 0x8001 ?**  
> `0x8001` est le type "Connected Data" pour TCP. Pour UDP I/O, le type correct est `0x00B1` (Connected I/O Data). Utiliser `0x8001` provoque des erreurs "malformed" côté Wireshark et le PLC ignore les paquets.

### 3. Services CIP (cip.py)

Le dispatcher dans `main.py` lit le service CIP (premier octet du payload CIP) et appelle le handler correspondant.

#### GetAttributeSingle (0x0E)

Le PLC interroge plusieurs objets CIP avant d'envoyer le ForwardOpen :

| Classe | Objet       | Attributs interrogés |
|--------|-------------|----------------------|
| 0x01   | Identity    | 1 (VendorID) à 8 (State) |
| 0xC0   | TCP/IP      | 1 (Status), 2 (Config Cap.), 3 (Config Ctrl), 5 (Interface Config), **0x12** (Encapsulation Inactivity Timeout — extension Rockwell) |
| 0xF4   | Port        | 7 (Port Type), 8 (Port Number) |

> **Pourquoi l'attribut 0x12 ?**  
> C'est une extension propriétaire Rockwell. Si l'adaptateur répond `0x08` (Service Not Supported) ou `0x14` (Attribute Not Supported), le PLC le tolère mais boucle en retry. Renvoyer `0x0000` (timeout = 0, désactivé) stoppe les retries.

#### ForwardOpen (0x54)

Le ForwardOpen est le cœur de la phase 1. Il transmet :
- Les IDs de connexion (`o_t_conn_id`, `t_o_conn_id`)
- Les intervalles RPI (`rpi_o_t`, `rpi_t_o`) en microsecondes
- Les paramètres de connexion (taille des paquets I/O, type de transport)

La réponse doit inclure **4 items CPF** (pas 2) :

```
(0x0000, b'')                 — Null Address
(0x00B2, cip_response)        — ForwardOpen Success (0xD4 + paramètres)
(0x8000, sock_ot)             — Socket Address O→T : port 2222, IP 0.0.0.0
(0x8001, sock_to)             — Socket Address T→O : port 2222, IP du PLC
```

> **Pourquoi les items 0x8000/0x8001 ?**  
> Sans ces items, le PLC ne sait pas quelle adresse UDP utiliser pour ses paquets O→T. Il passe en état "Connecting" → "Fault" immédiatement. Ces items sockaddr (16B au format BSD) sont obligatoires pour les adaptateurs Rockwell.

Structure d'un sockaddr CPF (16B) :
```
sin_family (2B LE) — toujours 0x0002 (AF_INET)
sin_port   (2B BE) — port UDP en big-endian (0x08AE = 2222)
sin_addr   (4B BE) — IP en big-endian (socket.inet_aton)
padding    (8B)    — zéros
```

#### ForwardClose (0x4E)

Ferme la connexion I/O. L'adaptateur remet `conn_state['active']` à `False` et répond avec `0xCE` (0x4E | 0x80) + conn_serial + vendor_id + originator_serial.

### 4. Échange I/O UDP (io_server.py)

#### Format des paquets O→T (PLC → Arduino)

```
CPF item 0 : type=0x8002, 8B
    conn_id   (4B LE) — o_t_conn_id assigné lors du ForwardOpen
    encap_seq (4B LE) — compteur 32 bits incrémenté par le PLC

CPF item 1 : type=0x00B1, 3B
    cip_seq    (2B LE) — compteur 16 bits, détection de doublons
    output_byte (1B)  — état des sorties PLC (bits 0-4 utilisés)
```

#### Format des paquets T→O (Arduino → PLC)

Même structure, avec `t_o_conn_id` comme conn_id et `encap_seq`/`cip_seq` locaux :

```
CPF item 0 : type=0x8002, 8B
    t_o_conn_id (4B LE)
    encap_seq   (4B LE) — compteur 32 bits local, incrémenté à chaque envoi

CPF item 1 : type=0x00B1, 3B
    cip_seq    (2B LE) — compteur 16 bits local
    input_byte  (1B)  — état des entrées Arduino
```

> **Pourquoi 3B et pas 1B dans les données I/O ?**  
> Le champ `t_o_conn_params = 0x4803` dans le ForwardOpen spécifie une connexion de taille fixe 3B. Si l'adaptateur envoie 1B, le PLC considère la taille incorrecte et rejette la connexion ("Validating" → "Fault").

#### Watchdog

La coroutine `task_watchdog` surveille `last_ot_time` (mis à jour à chaque O→T reçu). Si aucun O→T n'arrive pendant 5 secondes, la connexion est fermée côté adaptateur.

> **Pourquoi 5s et pas 0.5s ?**  
> Le PLC passe par un état "Validating" après le ForwardOpen avant de commencer à envoyer des O→T. Avec 0.5s de timeout, le watchdog coupait la connexion pendant cette phase de validation. 5s laisse le temps au PLC de terminer sa validation.

> **Race condition watchdog/task_send_inputs**  
> Les deux coroutines accèdent à `last_ot_time`. Pour éviter que le watchdog se déclenche immédiatement après l'activation (avant que `task_send_inputs` ait réinitialisé `last_ot_time`), les deux coroutines utilisent un flag `was_active` pour détecter le passage `False → True` de `conn_state['active']` et réinitialiser `last_ot_time` à ce moment.

---

## Lancer l'adaptateur

```bash
# Niveau INFO (normal)
python3 main.py

# Niveau DEBUG (trames hex complètes)
python3 main.py -v
```

Le programme démarre sur `0.0.0.0:44818` (TCP) et `0.0.0.0:2222` (UDP).  
Côté PLC Studio 5000 : ajouter un Generic EtherNet/IP Adapter avec le fichier `Arduino.eds`.

---

## Codes d'erreur CIP

| Code | Signification | Quand l'utiliser |
|------|---------------|------------------|
| 0x08 | Service Not Supported | Le service (0x0E, 0x54...) n'existe pas sur cet objet |
| 0x14 | Attribute Not Supported | Le service existe mais pas cet attribut précis |

> Renvoyer `0x08` pour un attribut inconnu au lieu de `0x14` conduit le PLC à considérer que `GetAttributeSingle` n'est pas supporté du tout — il abandonne la séquence de connexion.
