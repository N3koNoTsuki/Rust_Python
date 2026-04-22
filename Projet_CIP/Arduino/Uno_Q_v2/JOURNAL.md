# Journal de développement — EtherNet/IP CIP Adapter (Python, from scratch)

**Projet** : Adaptateur EtherNet/IP pour Arduino Uno Q  
**Stack** : Python asyncio  
**Device cible** : MPU Linux (`arduino@NekoNOUnoQ`)  
**PLC** : Rockwell (`192.120.0.206`)  
**Serveur** : `192.120.0.202`

---

## Étape 1 — `eip.py` : header EIP

**Fichier** : `eip.py`

Constantes de commandes EIP :
```python
CMD_REGISTER_SESSION = 0x0065
CMD_LIST_IDENTITY    = 0x0063
CMD_SEND_RR_DATA     = 0x006F
CMD_SEND_UNIT_DATA   = 0x0070 
```

Dataclass `EIPHeader` avec 6 champs : `command`, `length`, `session_handle`, `status`, `sender_context` (bytes), `options`.

- `parse_eip_header(data)` : unpack `'<HHII8sI'` sur les 24 premiers octets → retourne `EIPHeader(*...)` ou `None` si < 24B
- `build_eip_header(...)` : `struct.pack('<HHII8sI', ...)` → 24 octets

**Pièges rencontrés** :
- Format struct : `H`/`I` (unsigned), pas `h`/`i` (signed)
- `sender_context` = `8s` (bytes bruts), pas `q` (int64)
- `struct.unpack` retourne un tuple → passer avec `*` au constructeur du dataclass

---

## Étape 2 — `main.py` : serveur TCP skeleton

**Fichier** : `main.py`

- Coroutine `handle_client(reader, writer)` : boucle `await reader.read(4096)`, casse si `data == b''`
- Coroutine `main()` : `await asyncio.start_server(handle_client, '0.0.0.0', 44818)` + `await server.serve_forever()`
- Point d'entrée : `asyncio.run(main())`

**Pièges rencontrés** :
- `reader.read()` est une coroutine → besoin de `await`
- `asyncio.start_server(...)` est une coroutine → besoin de `await`
- `server.serve_forever()` est une coroutine → besoin de `await`

---

## Étape 3 — `eip.py` : RegisterSession

**Fichier** : `eip.py` + `main.py`

Ajout de `handle_register_session(header, data) -> bytes` dans `eip.py` :
- Fixe `session_handle = 0x12345678` (assigné par le serveur)
- Payload = `struct.pack('<HH', 1, 0)` (version=1, options=0)
- Réponse = `build_eip_header(CMD_REGISTER_SESSION, 4, 0x12345678)` + payload = **28 octets**

Dans `main.py` : `match header.command` avec `case eip.CMD_...` (import nommé `import eip` obligatoire — les noms simples dans `case` sont des captures, pas des comparaisons).

**Pièges rencontrés** :
- `from eip import *` + `case CMD_X:` → Pylance warning "not accessed" + bug silencieux (capture pattern)
- Solution : `import eip` + `case eip.CMD_X:`
- `header.session_handle` dans la requête vaut 0 → ne pas l'écho, générer le sien

**Test réel (trame 1)** : PLC `192.120.0.206` connecté, RegisterSession échangé avec succès, `session_handle=0x12345678` utilisé par le PLC dans les requêtes suivantes ✓

---

## Étape 4 — `cpf.py` : Common Packet Format

**Fichier** : `cpf.py`

Constantes :
```python
CPF_NULL_ADDR        = 0x0000
CPF_UNCONNECTED_DATA = 0x00B2
CPF_CONNECTED_ADDR   = 0x8002
CPF_CONNECTED_DATA   = 0x8001
CPF_IO_DATA          = 0x00B1
```

- `parse_cpf(data)` : lit `item_count` (2B LE), boucle avec `offset=2`, par item : `type_id`(2B) + `length`(2B) + `data`(length B), avance de `4 + length`, retourne `list[(type_id, data)]`
- `build_cpf(items)` : encode `item_count` + pour chaque item : `type`(2B) + `len(data)`(2B) + `data`

**Pièges rencontrés** :
- `ind` non initialisé → `NameError`
- Offset `2 + ind` avec `ind += 6 + length` → décalage de 2 après le 1er item
- Correct : `offset = 2`, avance de `4 + length` (type=2B + length_field=2B, pas 6)
- Typos : `CPF_NULL_ADRR`, `CPD_CONNECTED_ADDR`

---

## Étape 5 — `cip.py` : Identity Object

**Fichier** : `cip.py`

Constantes identité (issues du fichier EDS `Arduino.eds`) :
```python
VENDOR_ID     = 0xFFFF
DEVICE_TYPE   = 12
PRODUCT_CODE  = 1
REVISION      = (1, 1)
SERIAL_NUMBER = 0x00000001
PRODUCT_NAME  = "Arduino Uno Q"
```

- `build_list_identity_payload()` : construit le payload CPF pour répondre à ListIdentity. Structure : `item_count=1` + `item_type=0x000C` + `item_length` (dynamique) + contenu de l'item (protocol_version + sockaddr 16B + champs identité + state)
- `handle_get_attribute_all_identity()` : retourne les attributs CIP bruts de l'Identity Object

**Pièges rencontrés** :
- `item_length` hardcodé et faux → calculer dynamiquement en construisant le contenu séparé d'abord
- Sockaddr `sin_family` et `sin_port` en **big-endian** (network byte order), pas little-endian
- `REVISION[0]` et `REVISION[1]` = chacun **1 octet**, pas 2
- `PRODUCT_NAME` encodé en short string CIP : 1B de longueur + N octets ASCII (sans null terminator)

---

## Étape 6 — `cip.py` : objets TCP/IP (0xC0) et Port (0xF4)

**Fichier** : `cip.py`

Ajout de `handle_get_attribute_single(class_id, instance, attribute) -> bytes`.

Format de réponse CIP : `[service|0x80, 0x00, status, 0x00] + data`

| Class | Attribut            | Valeur             | Taille |
|-------|---------------------|--------------------|--------|
| 0xC0  | 1 Status            | `0x00000001`       | 4B     |
| 0xC0  | 2 Config Capability | `0x00000010`       | 4B     |
| 0xC0  | 3 Config Control    | `0x00000000`       | 4B     |
| 0xC0  | 5 Interface Config  | 20B zéros + `\x00` | 21B    |
| 0xF4  | 7 Port Type         | `0x0004`           | 2B     |
| 0xF4  | 8 Port Number       | `0x0001`           | 2B     |

Réponse succès : `bytes([0x8E, 0x00, 0x00, 0x00]) + data`  
Réponse erreur : `bytes([0x8E, 0x00, 0x08, 0x00])`

**Pièges rencontrés** :
- Noms de `case` dans `match` = captures Python si noms simples → utiliser les valeurs littérales hex directement
- Oublier le header CIP 4B devant les données

---

## Étape 7 — `cip.py` : ForwardOpen

**Fichier** : `cip.py`

Ajout du dataclass `ConnectionParameters` et de `handle_forward_open(payload, conn_state) -> bytes`.

Format struct : `'<BBIIHHIB3sIHIHB'` → 35 octets, 14 champs :

| Champ              | Type | Octets |
|--------------------|------|--------|
| priority_time_tick | B    | 1      |
| timeout_ticks      | B    | 1      |
| o_t_conn_id        | I    | 4      |
| t_o_conn_id        | I    | 4      |
| conn_serial        | H    | 2      |
| vendor_id          | H    | 2      |
| originator_serial  | I    | 4      |
| timeout_multiplier | B    | 1      |
| reserved           | 3s   | 3      |
| rpi_o_t            | I    | 4      |
| o_t_conn_params    | H    | 2      |
| rpi_t_o            | I    | 4      |
| t_o_conn_params    | H    | 2      |
| transport_type     | B    | 1      |

Réponse : `bytes([0xD4, 0x00, 0x00, 0x00])` + `struct.pack('<IIHHIII', o_t, t_o, conn_serial, vendor_id, orig_serial, rpi_ot, rpi_to)` + `b'\x00\x00'`

`conn_state` mis à jour : `o_t_conn_id`, `t_o_conn_id`, `rpi_o_t`, `rpi_t_o`, `conn_serial`, `vendor_id`, `originator_serial`, `active=True`

**Pièges rencontrés** :
- Format `'<BBIIHHIBb3sIHIHB'` (avec `b` en trop) → 15 valeurs, 14 champs → `TypeError`
- `reserved` = `bytes` (issu de `3s`), pas `int`
- `o_t_conn_id = 0` dans la requête PLC = "assigne toi-même un ID" → patch : `if o_t_conn_id == 0: 0xDEAD0001`
- Réponse = repacker le contenu de la requête → faux ; construire une structure spécifique plus courte

---

## Étape 8 — `main.py` : dispatcher SendRRData

**Fichier** : `main.py`

Ajout du traitement complet dans `case eip.CMD_SEND_RR_DATA` :

```
data[24:30]  →  interface_handle(4B) + timeout(2B)  — ignorés
data[30:]    →  début du CPF
```

Extraction du message CIP :
```python
items    = cpf.parse_cpf(data[30:])
cip_data = items[1][1]                    # Unconnected Data item
service     = cip_data[0]
path_size   = cip_data[1]
path        = cip_data[2 : 2+path_size*2]
extra       = cip_data[2+path_size*2:]
class_id    = path[1]                     # path[0] = 0x20 (type segment)
instance_id = path[3]                     # path[2] = 0x24 (type segment)
attribute_id = path[5] if len(path) >= 6 else 0
```

Dispatch :
- `0x0E` → `cip.handle_get_attribute_single(...)`
- `0x01` → `cip.handle_get_attribute_all_identity()`
- `0x54` → `cip.handle_forward_open(extra, conn_state)`
- `0x4E` → `cip.handle_forward_close(extra, conn_state)`

Construction de la réponse :
```python
cpf_response     = cpf.build_cpf([(0x0000, b''), (0x00B2, cip_response)])
payload_response = b'\x00\x00\x00\x00' + b'\x00\x00' + cpf_response
eip_response     = eip.build_eip_header(CMD_SEND_RR_DATA, len(payload_response), session_handle) + payload_response
```

**Pièges rencontrés** :
- CPF items réponse : `(0x0000, b'')` + `(0x00B2, cip_response)` — pas `0x00B2`+`0x8001`
- `path[1]` (class_id) ≠ `path[0] + path[1]` — `path[0]` est le type de segment, pas l'ID
- Double header EIP → construire payload d'abord, envelopper une seule fois
- Paquets TCP de 6 octets zéro envoyés par le PLC avant les vrais paquets EIP → `parse_eip_header` retourne `None` → crash sans message → fix : `if header is None: continue`
- Exception silencieuse dans asyncio → ajout `try/except Exception as e: print(f"[ERROR]: {e}")`

**Test réel (trame 2)** : ForwardOpen reçu et traité avec succès ✓
```
[INFO] ForwardOpen: o_t=0xdead0001, t_o=0x5e74e1, active=True
```

---

## Étape 9 — `io_server.py` : serveur UDP + échange I/O

**Fichier** : `io_server.py`

Classe `EIPUDPProtocol(asyncio.DatagramProtocol)` :
- `__init__` : stocke `conn_state`, initialise `last_ot_time = time.monotonic()`, `encap_seq = 0`, `plc_addr = None`, `transport = None`
- `connection_made` : stocke le transport
- `datagram_received` : parse EIP header + CPF, extrait `run_idle_header` et `output_byte`, log, met à jour `last_ot_time` et `plc_addr`

Structure O→T reçu (UDP payload = CPF brut, pas de header EIP) :
```
CPF item 0 : type=0x8002, 8B → conn_id (4B LE) + seq_count (4B LE)
CPF item 1 : type=0x00B1, NB → Connected Data :
    [0:2]  CIP Sequence Count (2B LE)
    [2]    output_byte (1B)
```

Coroutine `task_send_inputs(protocol, conn_state)` :
- Skip si `active=False` ou `plc_ip` absent
- Au premier passage actif : reset `last_ot_time = time.monotonic()` (flag `was_active`)
- Construit T→O : CPF brut (pas de header EIP) avec :
  - `CPF_CONNECTED_ADDR` (0x8002) : t_o_conn_id (4B) + encap_seq (4B) = 8B
  - `CPF_IO_DATA` (0x00B1) : cip_seq (2B LE) + inputs (1B)
- Envoie vers `protocol.plc_addr or (conn_state['plc_ip'], 2222)`
- Incrémente `encap_seq` (mod 2³²) et `cip_seq` (mod 2¹⁶)
- Sleep `rpi_t_o / 1_000_000` secondes

**Pièges rencontrés** :
- `asyncio.DatagramProtocol` : pas de `@dataclass`, pas de `__init__` sans hériter
- Variable `cpf` locale écrasait le module `cpf` importé → renommer en `items`
- `last_ot_time = 0.0` → watchdog tirait immédiatement après ForwardOpen → fix : `time.monotonic()`
- Race condition : protocole créé au démarrage, `last_ot_time` déjà vieux au moment du ForwardOpen → fix : reset dans `task_send_inputs` au premier cycle actif (`was_active` flag)
- T→O enveloppé dans un header EIP (cmd=0x0070) → le PLC ignorait, Wireshark "malformed" → fix : UDP I/O = CPF brut seulement, PAS de header EIP
- Item type 0x8001 (TCP connected data) utilisé → faux pour UDP I/O → fix : item type 0x00B1 (CPF I/O data)
- Connected Address 4B (conn_id seulement) → faux → fix : 8B = conn_id + seq_count
- PLC ne démarrait pas l'O→T : `plc_addr=None` empêchait tout envoi T→O → cercle vicieux → fix : stocker `conn_state['plc_ip']` lors du ForwardOpen (TCP), l'utiliser comme destination par défaut
- Source des formats corrects : analyse de captures réelles Rockwell PointIO (2015) présentes dans `test/Trame/`

---

## Étape 10 — `io_server.py` : watchdog

**Fichier** : `io_server.py`

Coroutine `task_watchdog(protocol, conn_state)` :
- Poll toutes les 100ms (`await asyncio.sleep(0.1)`)
- Si `active=True` et `time.monotonic() - last_ot_time > 5.0` :
  - `conn_state['active'] = False`
  - `protocol.plc_addr = None`
  - Log `[WATCHDOG]`

**Pièges rencontrés** :
- `sleep(1.0)` au lieu de `sleep(0.1)` → délai de détection jusqu'à 1.5s au lieu de 0.5s
- Timeout 0.5s trop court (PLC encore en "Validating") → porté à 5.0s

---

## Étape 11 — `cip.py` + `main.py` : ForwardClose + intégration finale

**Fichier** : `cip.py`

`handle_forward_close(payload, conn_state)` :
- `conn_state['active'] = False`
- Réponse : `bytes([0xCE, 0x00, 0x00, 0x00]) + struct.pack('<HHI', conn_serial, vendor_id, 0) + b'\x00\x00'`

**Pièges rencontrés** :
- Service reply ForwardClose = `0x4E | 0x80 = 0xCE` (pas `0xD5`)
- ForwardOpen response manquait 1 byte final : `b'\x00'` → `b'\x00\x00'` (app_reply_size + reserved = 2 octets selon spec ODVA)

**Fichier** : `main.py`

Intégration dans `main()` :
```python
loop = asyncio.get_event_loop()
transport, protocol = await loop.create_datagram_endpoint(
    lambda: io_server.EIPUDPProtocol(conn_state),
    local_addr=('0.0.0.0', 2222)
)
asyncio.create_task(io_server.task_send_inputs(protocol, conn_state))
asyncio.create_task(io_server.task_watchdog(protocol, conn_state))
await server.serve_forever()
```

**Pièges rencontrés** :
- Code après `serve_forever()` = code mort → démarrer UDP et tâches AVANT
- `asyncio.get_running_loop()` ≠ serveur — juste le loop courant
- Import `io_server as io` → utiliser `io.EIPUDPProtocol`, pas `eip.EIPUDPProtocol`

---

## Phase 2 — Débogage échange I/O UDP (suite)

### Problème : PLC boucle Connecting → Fault

Après l'intégration de l'étape 11, le PLC acceptait le ForwardOpen mais bouclait sans jamais atteindre "Connected". Plusieurs bugs ont été identifiés et corrigés par analyse des captures Wireshark.

#### Fix 1 — Code d'erreur CIP : `0x08` → `0x14`

Dans `cip.py`, les `case _:` renvoyaient `0x08` (Service Not Supported), ce qui indiquait au PLC que `GetAttributeSingle` n'était pas du tout supporté → il abandonnait.

Correct : `0x14` (Attribute Not Supported) pour un attribut inconnu d'un service supporté.

```python
# Avant
return bytes([0x8E, 0x00, 0x08, 0x00])
# Après
return bytes([0x8E, 0x00, 0x14, 0x00])
```

#### Fix 2 — Attribut TCP/IP 0x12 manquant

Le PLC interrogeait `class=0xC0, attr=0x12` (Encapsulation Inactivity Timeout, extension Rockwell) en boucle. Non géré → erreur → retry infini.

Ajout dans le `case 0xC0` :
```python
case 0x12:  # Encapsulation Inactivity Timeout
    data = 0x0000.to_bytes(2, 'little')
```

#### Fix 3 — ForwardOpen response : items socket address manquants

La réponse ForwardOpen n'avait que 2 items CPF (`Null + UnconnectedData`). Rockwell exige **4 items** incluant les adresses socket O→T et T→O pour savoir où envoyer les paquets UDP.

```python
# Avant : 2 items
cpf.build_cpf([(0x0000, b''), (0x00B2, cip_response)])

# Après : 4 items
sock_ot = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8  # port 2222, IP 0.0.0.0
sock_to = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8  # port 2222, IP 0.0.0.0
cpf.build_cpf([
    (0x0000, b''),
    (0x00B2, cip_response),
    (0x8000, sock_ot),   # O→T Socket Address
    (0x8001, sock_to)    # T→O Socket Address
])
```

Structure sockaddr (16B) : `sin_family(2B LE)` + `sin_port(2B BE)` + `sin_addr(4B BE)` + `padding(8B)`.

#### Fix 4 — Format T→O : 1B → 3B

Le PLC demandait une taille de 3B dans ses paramètres de connexion (`0x4803` = fixed, 3B). On n'envoyait qu'1B (les inputs bruts).

Format correct du T→O Connected Data :
```
[0:2]  CIP Sequence Count (2B LE, incrémenté par paquet)
[2]    Input data (1B)
```

Ajout du compteur `cip_seq` dans `EIPUDPProtocol` et passage à `struct.pack('<H', cip_seq) + bytes([inputs])`.

#### Fix 5 — Watchdog : race condition

Race condition possible entre `task_send_inputs` et `task_watchdog` au moment où `active` passe à `True` (les deux lisent/écrivent `last_ot_time`).

Fix : ajout du flag `was_active` dans `task_watchdog` (symétrique à `task_send_inputs`) pour garantir que `last_ot_time` est reset à l'activation quelle que soit l'ordre d'exécution des coroutines :

```python
async def task_watchdog(protocol, conn_state):
    was_active = False
    while True:
        active = conn_state.get('active', False)
        if active and not was_active:
            protocol.last_ot_time = time.monotonic()
            was_active = True
        elif not active:
            was_active = False
        if active and (time.monotonic() - protocol.last_ot_time) > 5.0:
            ...
```

#### Fix 6 — Parsing O→T : format simplifié

Le format O→T réel de ce PLC n'a pas de `run_idle_header` (4B) — il envoie directement :
```
[0:2]  CIP Sequence Count (2B LE)
[2]    Output data (1B)
```

Suppression de la logique run/idle, parsing direct :
```python
cip_seq = struct.unpack('<H', connected_data[0:2])[0]
output_byte = connected_data[2]
```

Ajout d'une vérification du type de l'item 1 (`CPF_IO_DATA = 0x00B1`) avant parsing.

### Améliorations qualité

- **Logging structuré** : ajout de `import logging` dans tous les fichiers, remplacement de tous les `print()` par `log.info/debug/warning/error`
- **argparse** dans `main.py` : flag `-v/--verbose` pour activer le niveau DEBUG
- **Meilleure gestion des erreurs UDP** : vérification du nombre d'items CPF, du type de l'item I/O, de la longueur des données avant parsing

---

## Étape 12 — `io_server.py` : remplacement asyncio DatagramProtocol → socket bloquant

**Fichier** : `io_server.py`

`asyncio.DatagramProtocol` posait des problèmes de réception UDP dans le contexte multi-thread de l'Arduino Uno Q (conflit entre le thread asyncio et le thread principal `App.run()`).

Remplacement par `EIPUDPHandler` : socket Python bloquant (`SOCK_DGRAM`) avec thread dédié pour la réception :

```python
class EIPUDPHandler:
    def __init__(self, conn_state):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.bind(('0.0.0.0', 2222))
        self.sock.settimeout(1.0)

    def recv_loop(self):  # lancé dans threading.Thread(daemon=True)
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            # ... parsing CPF, mise à jour conn_state ...

def start_udp_handler(conn_state):
    handler = EIPUDPHandler(conn_state)
    threading.Thread(target=handler.recv_loop, daemon=True, name="udp-recv").start()
    return handler
```

Dans `main.py` : `loop.create_datagram_endpoint(...)` remplacé par `io.start_udp_handler(conn_state)`.

**Avantages** :
- Découplage complet entre asyncio et la réception UDP
- `SO_REUSEPORT` permet la cohabitation avec d'autres sockets sur le port 2222
- `settimeout(1.0)` évite de bloquer indéfiniment si aucun paquet ne vient

---

## Étape 13 — `main.py` + `sketch.ino` : intégration Bridge/App Arduino Uno Q

**Fichiers** : `main.py`, `sketch.ino`

Le programme Python tourne sur le **MPU Linux** de l'Arduino Uno Q. Le sketch tourne sur le **MCU** (ARM Cortex-M4). Ils communiquent via Bridge (UART interne).

### Architecture du démarrage

```python
# Thread daemon : boucle asyncio (TCP + tâches I/O)
threading.Thread(target=lambda: asyncio.run(main()), daemon=True).start()

# Thread principal : framework Arduino Uno Q
App.run(user_loop=loop)
```

`serve_forever()` bloque le thread asyncio indéfiniment ; `App.run()` bloque le thread principal → les deux coexistent sans `asyncio.run()` bloquant le main thread.

### Bridge : fonctions exposées

```python
Bridge.provide("linux_started",    linux_started)     # → MCU attend ce signal
Bridge.provide("receive_cip_data", receive_cip_data)  # MCU → Linux : entrées pins
Bridge.provide("send_cip_data",    send_cip_data)     # Linux → MCU : sorties PLC
```

`conn_state` est étendu avec `input_data` et `output_data` pour transporter les données entre le Bridge et l'adaptateur EIP :

```python
conn_state = {'active': False, 'input_data': 0, 'output_data': 0}

def receive_cip_data(data):
    conn_state['input_data'] = int(data) & 0xFF   # lu par task_send_inputs → T→O

def send_cip_data() -> int:
    return conn_state['output_data'] & 0xFF        # écrit par recv_loop ← O→T
```

### Sketch MCU (`sketch.ino`)

Le sketch attend `linux_started` avant de démarrer (avec 5s de délai post-`Monitor.begin()`), puis entre dans la boucle principale :

- **T→O** : lit l'état binaire des pins 2-6 (`ind` compteur 5 bits) → `Bridge.notify("receive_cip_data", input)` → reçu par `receive_cip_data()` côté Linux
- **O→T** : `Bridge.call("send_cip_data").result(outputData)` → retourné par `send_cip_data()` → affiché sur la matrice LED (8 colonnes, 1 colonne/bit)

**Pièges rencontrés** :
- `asyncio.run(main())` en thread daemon → si le thread principal se termine, tout s'arrête → `App.run()` maintient le thread principal vivant
- `Bridge.call().result()` est bloquant → ne pas appeler depuis le thread asyncio ; seul le sketch MCU l'appelle

---

## Étape 14 — `board_setup/` : forwarding UDP pour App Lab

**Fichiers** : `board_setup/cip-udp-forward.sh`, `cip-udp-forward.service`, `install.sh`, `uninstall.sh`

### Problème

App Lab déploie le code Python dans un **conteneur Docker**. Docker n'expose que les ports TCP déclarés dans `app.yaml`. Le port **UDP 2222** (échange O→T / T→O) n'est jamais transmis au conteneur : les paquets du PLC arrivent sur la board mais sont silencieusement ignorés.

### Solution : iptables DNAT dynamique

Un script shell surveille les événements Docker (`docker events --filter 'event=start'`). Dès qu'un conteneur dont le nom contient `cip` démarre, il :

1. Récupère l'IP du conteneur dynamiquement via `docker inspect`
2. Supprime l'ancienne règle DNAT si elle existe (évite les doublons en cas de restart)
3. Insère une nouvelle règle en tête de `PREROUTING` :

```bash
iptables -t nat -I PREROUTING 1 -i wlan0 -p udp --dport 2222 \
    -j DNAT --to-destination <IP_conteneur>:2222
```

Le `sleep 1` avant `docker inspect` laisse le temps au réseau Docker de s'initialiser (l'IP n'est pas immédiatement disponible au moment de l'événement `start`).

### Déploiement systemd

Le script est encapsulé dans un service systemd (`After=docker.service`) pour démarrer automatiquement au boot :

```
cip-udp-forward.service
  ExecStart=/usr/local/bin/cip-udp-forward.sh
  Restart=on-failure / RestartSec=5
```

`install.sh` copie le script dans `/usr/local/bin/`, installe le service et l'active. `uninstall.sh` fait l'inverse et nettoie la règle iptables.

**Pièges rencontrés** :
- L'IP du conteneur change à chaque recréation par App Lab → la règle doit être mise à jour dynamiquement, pas fixée une seule fois
- Sans `sleep 1`, `docker inspect` retourne une IP vide car le réseau n'est pas encore attaché au moment de l'événement `start`
- L'ancienne règle DNAT doit être supprimée avant d'en insérer une nouvelle, sinon deux règles coexistent et seule la première (possiblement obsolète) s'applique

---

## État actuel

| Fichier        | Contenu                                                                                       |
|----------------|-----------------------------------------------------------------------------------------------|
| `eip.py`       | Header EIP, RegisterSession                                                                   |
| `cpf.py`       | Common Packet Format                                                                          |
| `cip.py`       | Identity Object, TCP/IP Object (attr 1-3/5/0x12), Port Object, ForwardOpen, ForwardClose     |
| `main.py`      | Serveur TCP, dispatcher EIP/CIP, intégration UDP, Bridge/App, logging, argparse               |
| `io_server.py` | Socket UDP bloquant (thread dédié), réception O→T, envoi T→O (3B), watchdog (5s, race-free)  |
| `sketch.ino`   | Sketch MCU : init Bridge/Monitor/Matrix, compteur binaire pins 2-6, Bridge notify/call, LED  |
| `board_setup/` | Service systemd + iptables DNAT pour exposer UDP 2222 au conteneur Docker App Lab            |

**Phase 1 TCP complète ✓** — RegisterSession + GetAttribute + ForwardOpen + ForwardClose fonctionnels.

**Phase 2 UDP complète ✓** — Échange I/O cyclique opérationnel. PLC atteint l'état "Connected".

**Bridge complète ✓** — Communication MCU ↔ Linux via Bridge : données T→O et O→T échangées en temps réel.
