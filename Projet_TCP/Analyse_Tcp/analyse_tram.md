# Analyse des echanges de trames TCP entre Arduino Uno_Q et Rockwell 1769-L36ERMS

## Ordre des testes :
 - Une Grosse trame envoyer Arduino -> Rockwell
 - Une Grosse trame envoyer Rockwell -> Arduino
 - Plein de trames envoyer Arduino -> Rockwell
 - Plein de trames envoyer Rockwell -> Arduino

### Une Grosse trame envoyer Arduino -> Rockwell 

Sequence observer avec Wireshark :

    PLC → PC : "semp" (4 bytes)
    PC → PLC : ACK
    PC → PLC : gros message (937 bytes)
    PLC → PC : ACK
![Texte alternatif](img/Gros_Ard_Rock.png "Gros_Ard_Rock")





