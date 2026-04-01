import socket
import time
import neko_no_lib as nl
from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

# -------------------------------------------------------------------
# Données globales
# -------------------------------------------------------------------
# Création d'un objet ville et d'un objet météo partagé dans l'application.
Grenoble = nl.City(name="Grenoble", lat=45.18, lon=5.72)
Meteo = nl.Meteo(temp=0.0, location=Grenoble)


# -------------------------------------------------------------------
# Fonction : linux_started
# Rôle :
#     Indique au MCU ou au bridge que la partie Linux est bien démarrée.
# Paramètres :
#     Aucun
# Retour :
#     True -> Linux prêt
# -------------------------------------------------------------------
def linux_started():
    return True


# -------------------------------------------------------------------
# Fonction : python_func
# Rôle :
#     Callback appelée depuis l'autre côté du bridge pour mettre à jour
#     la température stockée dans l'objet Meteo.
# Paramètres :
#     data (float) -> nouvelle température reçue
# Retour :
#     Aucun
# -------------------------------------------------------------------
def python_func(data: float):
    global Meteo
    Meteo.temp = data


# Création d’un socket TCP IPv4.
sserveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


# Activation de l’option SO_REUSEADDR au niveau du socket.
# - Niveau SOL_SOCKET :
#     Option générique appliquée au socket lui-même.
# - SO_REUSEADDR = 1 :
#     Autorise la réutilisation immédiate du couple (IP, port).
sserveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# bind(("0.0.0.0", 5010)) :
# 0.0.0.0  -> écoute sur toutes les interfaces réseau disponibles
# 5010     -> port TCP utilisé par le serveur
sserveur.bind(("0.0.0.0", 5010))

# listen(5) :
# Met le socket en mode serveur.
# Le "5" représente la taille de la file d'attente des connexions en attente.
sserveur.listen(5)

# settimeout(0.0) :
# Rend le accept() non bloquant.
sserveur.settimeout(0.0)

# Socket du client actuellement actif
sclient = None
adclient = None

print("Serveur lancé")

# Exposition des fonctions côté bridge
Bridge.provide("linux_started", linux_started)
Bridge.provide("python_func", python_func)

print("Hello WebUI")
ui = WebUI()
ui.expose_api("GET", "/hello", lambda: {"message": "initialisation"})


# -------------------------------------------------------------------
# Fonction : close_client
# Rôle :
#     Ferme proprement le client actuellement connecté et remet les
#     variables globales à None.
# Paramètres :
#     Aucun
# Retour :
#     Aucun
# -------------------------------------------------------------------
def close_client():
    global sclient, adclient

    if sclient is not None:
        try:
            # shutdown() coupe la communication dans les deux sens
            # avant fermeture du socket.
            sclient.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

        try:
            sclient.close()
        except Exception:
            pass

    sclient = None
    adclient = None


# -------------------------------------------------------------------
# Fonction : handle_message
# Rôle :
#     Traite le payload reçu depuis le client et construit la réponse
#     applicative à renvoyer.
# Paramètres :
#     decoded (str) -> message reçu déjà décodé en chaîne de caractères
# Retour :
#     str | None -> réponse applicative à renvoyer, ou None si rien à envoyer
# -------------------------------------------------------------------
def handle_message(decoded: str) -> str | None:
    # strip() enlève les espaces et retours ligne éventuels en début/fin
    message = decoded.strip()

    print(f"Message reçu : {message!r}")

    if message == "big":
        return (
            "Dans un systeme embarque, la transmission de données repose sur des "
            "trames structurees permettant d’assurer la synchronisation, l’intégrite "
            "et l’interpretation correcte des informations. Chaque trame est "
            "generalement composee d’un en-tete contenant des metadonnees, suivi "
            "d’un champ de donnees utile appele payload, puis d’un champ de controle "
            "comme un CRC ou checksum. La taille des trames peut varier selon le "
            "protocole utilise, mais elle doit rester adaptee aux contraintes du "
            "reseau, notamment en termes de bande passante et de latence. Une trame "
            "trop longue peut augmenter le risque d’erreurs, tandis qu’une trame trop "
            "courte peut reduire l’efficacite globale de la communication. Dans les "
            "systemes industriels, comme ceux utilisant Ethernet/IP ou Modbus, la "
            "gestion des trames est essentielle pour garantir un echange fiable entre "
            "les automates programmables et les equipements connectes."
        )

    if message == "temp":
        if Meteo.temp is not None:
            ui.send_message("temp", Meteo.temp)
            nl.print_meteo(Meteo, False)
            return f"{Meteo.temp}"
        return "temp indisponible"

    # Réponse par défaut si le message n'est pas reconnu
    return f"{len(message)} octets"


# -------------------------------------------------------------------
# Fonction : recv_exact
# Rôle :
#     Lit exactement "size" octets sur un socket.
#     Continue de lire tant que la quantité demandée n'a pas été reçue.
# Paramètres :
#     sock -> socket client à lire
#     size (int) -> nombre exact d'octets attendus
# Retour :
#     bytes -> données reçues
# Exceptions :
#     ConnectionResetError si le client ferme proprement avant la fin
# -------------------------------------------------------------------
def recv_exact(sock, size: int) -> bytes:
    data = b""

    while len(data) < size:
        # recv(n) lit jusqu'à n octets, mais peut en renvoyer moins
        chunk = sock.recv(size - len(data))

        # Si recv renvoie b"", cela signifie que la connexion est fermée
        if chunk == b"":
            raise ConnectionResetError("Connexion fermée proprement par le client")

        data += chunk

    return data


# -------------------------------------------------------------------
# Fonction : send_frame
# Rôle :
#     Construit et envoie une trame de réponse au format :
#         header = NKP1 + taille sur 4 chiffres
#         payload = contenu encodé en bytes
# Paramètres :
#     sock -> socket client destinataire
#     payload (str) -> contenu à envoyer
# Retour :
#     Aucun
# -------------------------------------------------------------------
def send_frame(sock, payload: str):
    payload_bytes = f"{payload}NKP2".encode()

    # :04d -> force un entier sur 4 chiffres avec des zéros devant
    header = f"NKP1{len(payload_bytes):04d}".encode()

    # sendall() garantit l'envoi complet tant que la connexion reste valide
    sock.sendall(header)
    sock.sendall(payload_bytes)


# -------------------------------------------------------------------
# Fonction : accept_new_client_if_any
# Rôle :
#     Vérifie s'il y a un nouveau client en attente de connexion.
#     Si oui :
#       - il devient le client actif,
#       - l'ancien client est fermé si nécessaire.
# Paramètres :
#     Aucun
# Retour :
#     Aucun
# -------------------------------------------------------------------
def accept_new_client_if_any():
    global sclient, adclient

    while True:
        try:
            client, addr = sserveur.accept()

            # settimeout(1.0) sur le client :
            # recv() attendra au maximum 1 seconde avant de lever socket.timeout.
            client.settimeout(1.0)

            print(f"Nouveau client détecté : {addr}")

            # Si un client est déjà actif, on le remplace
            if sclient is not None:
                print(f"Remplacement de l'ancien client : {adclient}")
                close_client()

            sclient = client
            adclient = addr
            print(f"Client actif : {adclient}")

        except BlockingIOError:
            # Aucun nouveau client en attente
            break
        except Exception as e:
            print(f"[Erreur accept] {e}")
            break


# -------------------------------------------------------------------
# Fonction : loop
# Rôle :
#     Boucle principale appelée par App.run().
#     Elle :
#       1. accepte un nouveau client si présent,
#       2. lit une trame complète,
#       3. vérifie le header,
#       4. vérifie le footer,
#       5. traite le message,
#       6. renvoie une réponse.
# Paramètres :
#     Aucun
# Retour :
#     Aucun
# -------------------------------------------------------------------
def loop():
    global sclient, adclient

    # Vérifie si un nouveau client tente de se connecter
    accept_new_client_if_any()

    # Si aucun client actif, on ne fait rien ce cycle
    if sclient is None:
        return

    try:
        # Lecture des 8 octets du header :
        # "NKP1" + "XXXX"
        header = recv_exact(sclient, 8)
        print(f"Header brut : {header!r}")

        # Signature protocolaire
        signature = header[:4].decode(errors="replace")

        # Taille du payload encodée sur 4 caractères
        size_str = header[4:8].decode(errors="replace")

        # Vérification de la signature d'entrée
        if signature != "NKP1":
            print(f"[Header invalide] Signature reçue : {signature!r}")
            send_frame(sclient, "ERR_SIGNATURE")
            return

        # Vérification que la taille est bien numérique
        if not size_str.isdigit():
            print(f"[Header invalide] Taille non numérique : {size_str!r}")
            send_frame(sclient, "ERR_SIZE_FORMAT")
            return

        payload_size = int(size_str)
        print(f"Taille payload annoncée : {payload_size}")

        # Lecture exacte du payload annoncé
        payload_bytes = recv_exact(sclient, payload_size)

        if len(payload_bytes) != payload_size:
            print(
                f"[Payload invalide] attendu={payload_size}, reçu={len(payload_bytes)}"
            )
            send_frame(sclient, "ERR_PAYLOAD_SIZE")
            return

        decoded_payload = payload_bytes.decode(errors="replace")
        print(f"Payload reçu : {decoded_payload!r}")

        # Vérification qu'il y a au moins de quoi contenir le footer NKP2
        if len(decoded_payload) < 4:
            print("[Payload invalide] trop court pour contenir NKP2")
            send_frame(sclient, "ERR_SIGNATURE")
            return

        # On sépare données utiles et footer
        payload = decoded_payload[:-4]
        footer = decoded_payload[-4:]

        # Vérification de la signature de fin
        if footer != "NKP2":
            print(f"[Footer invalide] Signature reçue : {footer!r}")
            send_frame(sclient, "ERR_SIGNATURE")
            return

        # Traitement applicatif
        response = handle_message(payload)

        # Envoi d'une réponse si nécessaire
        if response is not None:
            send_frame(sclient, response)

    except socket.timeout:
        # Aucun octet reçu pendant le délai fixé sur le socket client
        return

    except (ConnectionResetError, BrokenPipeError):
        print("[Client déconnecté]")
        close_client()
        return

    except EOFError:
        print("[EOF client]")
        close_client()
        return

    except Exception as e:
        print(f"[Erreur] {e}")
        close_client()


App.run(user_loop=loop)
