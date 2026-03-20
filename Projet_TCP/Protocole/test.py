payload = "Dans un système embarqué, la transmission de données repose sur des trames structurées permettant d’assurer la synchronisation, l’intégrité et l’interprétation correcte des informations. Chaque trame est généralement composée d’un en-tête contenant des métadonnées, suivi d’un champ de données utile appelé payload, puis d’un champ de contrôle comme un CRC ou checksum. La taille des trames peut varier selon le protocole utilisé, mais elle doit rester adaptée aux contraintes du réseau, notamment en termes de bande passante et de latence. Une trame trop longue peut augmenter le risque d’erreurs, tandis qu’une trame trop courte peut réduire l’efficacité globale de la communication. Dans les systèmes industriels, comme ceux utilisant Ethernet/IP ou Modbus, la gestion des trames est essentielle pour garantir un échange fiable entre les automates programmables et les équipements connectés."
# payload = handle_message(decoded)
signature = "NKP1"
size = len(payload.encode())
size = f"{size:04d}"
header = f"{signature}{size}"
print(header.encode())
print(signature.encode())
print(size.encode())
print(payload.encode())
