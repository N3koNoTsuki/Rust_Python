# Fiche résumé — EtherNet/IP CIP Adapter (Arduino Uno Q)

---

## Contexte

Le PLC Rockwell parle le protocole **EtherNet/IP**. L'Arduino ne sait pas parler ce protocole. Ce programme tourne sur le MPU Linux et joue le rôle d'intermédiaire : il se fait passer pour un vrai adaptateur I/O aux yeux du PLC, et traduit les ordres reçus en appels simples vers l'Arduino via la liaison série.

```
PLC Rockwell  ←──EtherNet/IP──→  MPU Linux (ce programme)  ←──UART──→  Arduino
```

---

## La pile de protocoles

EtherNet/IP est construit en couches, chacune enveloppant la suivante :

**EIP** (EtherNet/IP) est la couche transport. Elle circule sur TCP pour les échanges de configuration et sur UDP pour les données I/O temps réel. Elle définit un en-tête fixe de 24 octets qui précède chaque message.

**CIP** (Common Industrial Protocol) est la couche applicative. C'est ici que se trouvent les vrais services : ouvrir une connexion, lire des attributs, etc. Les messages CIP sont transportés à l'intérieur des paquets EIP.

**CPF** (Common Packet Format) est l'enveloppe intermédiaire. Elle encadre les données CIP et indique au destinataire comment interpréter le contenu (requête explicite, données I/O connectées, etc.).

---

## La connexion se déroule en deux phases

### Phase 1 — Identification (TCP)

Avant tout échange de données, le PLC doit identifier l'appareil et ouvrir une session. Tout cela passe par TCP sur le port 44818.

**Étape 1 — Enregistrement de session**

Le PLC ouvre une connexion TCP et demande un handle de session. On lui en attribue un. Tous les messages suivants sur cette connexion porteront ce handle.

```
PLC  →  RegisterSession (payload : version du protocole)
PLC  ←  session_handle (un entier 32 bits qu'on a choisi)
```

**Étape 2 — Découverte de l'appareil**

Le PLC demande qui on est. On lui répond avec les informations déclarées dans le fichier EDS : fabricant, type de produit, nom, révision, etc.

```
PLC  →  ListIdentity
PLC  ←  VendorID=0xFFFF, DeviceType=12, ProductName="Arduino Uno Q", ...
```

**Étape 3 — Ouverture de la connexion I/O (Forward Open)**

C'est l'étape clé. Le PLC dit : "je veux échanger des données I/O avec toi, voici les paramètres". Il envoie notamment :
- deux identifiants de connexion (un pour chaque sens)
- la fréquence à laquelle il va envoyer des données (RPI, en microsecondes)

On doit retenir tout ça, car on s'en servira pour envoyer les données en retour.

```
PLC  →  ForwardOpen (conn_id_ot, conn_id_to, rpi_ot, rpi_to, ...)
PLC  ←  confirmation avec les mêmes IDs + les intervalles retenus
```

À partir de ce moment, la connexion est considérée comme active.

---

### Phase 2 — Échange I/O cyclique (UDP)

Une fois la connexion ouverte, les données I/O circulent en continu sur UDP, port 2222. Les deux sens sont indépendants.

**O→T : le PLC envoie les sorties (ce qu'on doit appliquer sur l'Arduino)**

Le PLC envoie un paquet UDP à chaque RPI. Ce paquet contient un octet de données représentant l'état des 5 sorties (bits 0 à 4, pour les pins D2-D6). Il contient aussi un compteur de séquence et parfois un "Run/Idle header" qui indique si le PLC est en mode RUN ou IDLE.

Si le PLC est en IDLE, on doit mettre les sorties à 0 même si l'octet de données contient des valeurs.

```
PLC  →  [seq=42] [run=1] [outputs=0b00110]  →  on applique 0b00110 sur D2-D6
PLC  →  [seq=43] [run=0] [outputs=0b00110]  →  PLC en IDLE, on applique 0b00000
```

**T→O : on envoie les entrées (ce qu'on lit sur l'Arduino)**

En parallèle, on lit l'état des 5 entrées (pins D7-D11) et on envoie un paquet UDP au PLC au même rythme que le RPI T→O négocié. Le paquet contient un identifiant de connexion (pour que le PLC sache à quelle connexion appartient ce paquet), un compteur de séquence, et l'octet d'entrées.

```
Nous  →  [conn_id_to] [encap_seq=7] [cip_seq=12] [inputs=0b10100]
```

---

## Ce qu'on doit gérer en permanence

**Le watchdog** : si on ne reçoit plus de paquet O→T depuis plus de 500 ms (PLC déconnecté, réseau coupé...), on remet immédiatement les sorties à 0 pour des raisons de sécurité.

**Les deux compteurs** : chaque paquet T→O incrémente deux compteurs distincts — un compteur 32 bits pour l'adresse du paquet (encapsulation), et un compteur 16 bits pour les données CIP. Le PLC les utilise pour détecter les pertes de paquets.

**L'adresse UDP du PLC** : on ne connaît pas à l'avance où envoyer les paquets T→O. On l'apprend en regardant l'IP source des paquets O→T reçus ou l'IP de la connexion TCP.

---

## Interrogations sur l'identité réseau (Get Attribute)

Entre l'identification et le Forward Open, le PLC peut interroger des objets CIP pour valider la configuration réseau de l'appareil. Il vérifie notamment l'objet TCP/IP (classe 0xC0) pour s'assurer que l'appareil a une adresse IP cohérente. Une réponse incorrecte à ces interrogations peut faire échouer la connexion côté PLC.

---

## Fermeture propre

Le PLC peut fermer la connexion explicitement via un Forward Close. On doit alors remettre les sorties à 0 et marquer la connexion comme inactive.