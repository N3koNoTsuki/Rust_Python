# Analyse du Protocole TCP

## Objectif
Valider le comportement du protocole de communication face à différentes stratégies d’envoi des données (header et payload), en observant :
- le comportement du réseau (Wireshark)
- le comportement côté automate Rockwell (buffer + parsing)

Le protocole repose sur :
- un **header fixe** : `NKP1XXXX`
  - `NKP1` : signature
  - `XXXX` : taille du payload (zéro-padding)
- suivi du **payload et du footer**

---

## Tests effectués

### 1. Header envoyé en deux parties

Le header est volontairement découpé en deux envois TCP distincts.

#### Observation Wireshark
Le header apparaît bien en **deux trames TCP distinctes**.

![Texte alternatif](img/Header_slice.png "Header_slice")

#### Observation côté Rockwell
- Les données sont **correctement reconstituées dans le buffer TCP**
- Le parsing fonctionne normalement
- Aucun impact fonctionnel

#### Conclusion
Le protocole est robuste à un **header fragmenté**.
→ Conforme au fonctionnement TCP (stream, pas message-based)

---

### 2. Header envoyé byte par byte

Chaque byte du header est envoyé individuellement.

#### Observation Wireshark
Contrairement à l’attente :
- Les bytes ne sont pas forcément visibles comme des trames séparées
- Le TCP **regroupe automatiquement les petits envois**

![Texte alternatif](img/Header_fully_slice_et_Header_plus_payload.png "Header_fully_slice_et_Header_plus_payload")
![Texte alternatif](img/Header_fully_slice_Python.png "Header_fully_slice_Python")  

#### Explication technique
TCP est un protocole **orienté flux (stream)** :
- Il n’y a **aucune garantie de découpage des paquets**
- Le système réseau (stack TCP) peut :
  - fusionner les envois 
  - bufferiser avant envoi

#### Observation côté Rockwell
- Réception en un bloc
- Parsing fonctionnel

#### Conclusion
Envoyer byte par byte :
- N’a aucun intérêt en TCP
- Ne garantit pas une séparation réseau
- Le protocole reste fonctionnel grâce au parsing basé sur contenu

---

### 3. Header + Payload envoyés en une seule trame

Envoi classique : header + payload en une fois.

#### Observation Wireshark
- Une seule trame contenant l’ensemble des données

![Texte alternatif](img/Header_fully_slice_et_Header_plus_payload.png "Header_fully_slice_et_Header_plus_payload")

#### Observation côté Rockwell

Buffer brut :
![Texte alternatif](img/Raw_Rockwell.png "Raw_Rockwell")

Données décodées :
![Texte alternatif](img/Decoded_Rockwell.png "Decoded_Rockwell")

#### Conclusion
- Comportement attendu
- Parsing immédiat possible

---

### 4. Mauvais Header envoyés

Envoi d'un mauvais header 

#### Observation cote Rockwell

On detecte bien le mauvais header, on vas lire tout le buffer du socket pour assayer de le trouver, si rien, on retourne en idle

![Texte alternatif](img/Bad_Header_test.png "Bad_Header_test")

--- 

### 5. Taille trop grande

Envoi d'un payload trop importnat 

#### Observation cote Rockwell

On detecte bien que la size et trop grande comparer au buffer, on vient donc retourner en idle tout en vidant le buffer 


![Texte alternatif](img/Bad_Size_Reset_test.png "Bad_Size_Reset_test")
![Texte alternatif](img/Bad_Size_test.png "Bad_Size_test")


--- 

### 6. Mauvais format de size

Envoi d'un format non comforme pour la taille du payload

#### Observation cote Rockwell

On detecte l'erreur de format, resync puis retour en idle

![Texte alternatif](img/Bad_Size_format_test.png "Bad_Size_format_test")

--- 

### 7. Mauvais footer 

Envoi d'un mauvais footer 

#### Observation cote Rockwell

On detecte l'erreur de footer, resync puis idle

![Texte alternatif](img/Bad_footer_test.png "Bad_footer_test")

--- 

### 8. Bruit avant le Header

Envoie d'un header avec du bruit avant 

#### Observation Wireshark

![Texte alternatif](img/Noise_header_Wireshark_test.png "Noise_header_Wireshark_test ")

#### Observation Rockwell

![Texte alternatif](img/Noise_header_test.png "Noise_header_test")








