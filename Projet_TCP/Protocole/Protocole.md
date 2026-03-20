# Protocole de communication personnalisé

## Description

Chaque trame est composée de trois parties :
1. Une **signature** 
2. La **taille** des données envoyées
3. La **trame** 

---

## Structure d’une trame

| Champ      | Taille       | Description                          |
|------------|--------------|--------------------------------------|
| Signature  | 4 octets     | Identifiant fixe du protocole        |
| Taille     | 2 octets     | Taille de la trame (payload)         |
| Données    | N octets     | Contenu utile (payload)              |

---

## Signature

Signature proposée :

```

0x4E 0x4B 0x50 0x31

```

Correspondance ASCII :

```

NKP1  (Neko Protocol v1)

```

Permet de :
- Valider que la trame est correcte
- Synchroniser le flux
- Ignorer les données corrompues

---

## Champ Taille

- Représente la taille **exacte du payload**
- Ne contient **pas** la signature ni le champ taille lui-même

Exemple :
```

Payload = 100 octets → Taille = 100

```
---

## Payload

Contient les données utiles.

Exemples :
- Texte
- Données binaires
- JSON
- Trame industrielle

---

## Exemple complet

### Données envoyées :
```

"HELLO"

```

### Encodage :

| Champ      | Valeur                 |
|------------|------------------------|
| Signature  | `4E 4B 50 31`            |
| Taille     | `00 05`                  |
| Données    | `48 45 4C 4C 4F`         |

### Trame finale :
```

4E 4B 50 31 00 05 48 45 4C 4C 4F

```

---

## Fonctionnement côté réception

1. Lire les 4 premiers octets → vérifier la signature
2. Lire le champ taille
3. Lire exactement `taille` octets
4. Traiter la trame

---

## Points importants

- TCP est un **flux**, pas un message → une trame peut être :
  - fragmentée
  - concaténée avec d’autres
- Toujours utiliser un buffer et reconstruire les trames

---

## Nom du protocole

**NKP1 — Neko Protocol v1**

---
