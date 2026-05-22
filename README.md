# RckwllXUnoQ — EtherNet/IP CIP Adapter

Projet de recherche et développement visant à faire communiquer un **PLC Rockwell GuardLogix** avec une carte **Arduino Uno Q** (MPU Linux embarqué) via le protocole industriel **EtherNet/IP / CIP**, sans passer par du matériel industriel dédié.

## Démonstration

https://github.com/user-attachments/assets/cb7c719e-1355-4eb0-8761-37f6fca83785

> *Version HD : [`Showcase.mp4`](Showcase.mp4)*

---

## Vue d'ensemble

Le PLC Rockwell voit l'Arduino Uno Q comme un adaptateur I/O standard sur le réseau industriel. L'Arduino répond aux requêtes CIP (Common Industrial Protocol) du PLC, ouvre une connexion I/O cyclique, et échange des données d'entrées/sorties en temps réel via UDP.

```
PLC Rockwell                        Arduino Uno Q
    |                                     |
    |──── TCP 44818 ── Session + I/O ────>|   Handshake EtherNet/IP
    |<─── Réponses CIP ────────────────── |
    |                                     |
    |~~── UDP 2222 ──── Sorties PLC ─────>|   Échange cyclique
    |<~~─ UDP 2222 ──── Entrées Arduino ──|   (données I/O en temps réel)
```

---

## Structure du projet

Le projet est organisé en plusieurs étapes d'évolution :

| Dossier | Description |
|---|---|
| `Projet_first_exeperiment/` | Premières expérimentations (C, Rust, Arduino) |
| `Projet_modbus/` | Tentative initiale avec le protocole Modbus |
| `Projet_TCP/` | Développement d'un protocole TCP maison (`NKP1`) pour analyser la communication |
| `Projet_CIP/` | Implémentation Python de l'adaptateur EtherNet/IP (versions successives) |
| `Projet_CIP_rust/` | Version finale : parsing EIP/CPF/CIP délégué à un module natif **Rust** compilé en extension Python |
| `Projet_rust/` | Outils Rust annexes développés en parallèle (grep, cat, lib graphique, Jeu de la Vie...) |

Le fichier `Graphe_Etat_Routine_SFC.L5X` est le programme PLC Rockwell (Studio 5000) utilisé pour les tests.

---

## Version finale

La version finale (`Projet_CIP_rust/`) combine :
- Un serveur **Python asyncio** qui gère la logique de session et les échanges I/O
- Un module **Rust** (extension Python via PyO3) qui prend en charge le parsing et la construction des trames EIP, CPF et CIP à bas niveau

Cette architecture permet d'atteindre les performances nécessaires pour le protocole temps-réel tout en gardant la flexibilité de Python pour la logique applicative.
