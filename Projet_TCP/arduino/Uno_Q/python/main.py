import socket
import signal
import sys

sserveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sserveur.bind(("0.0.0.0", 5010))
sserveur.listen(1)

sclient = None


def handler(sig, frame):
    print("\n[CTRL+C] Fermeture serveur + client")
    global sclient
    if sclient:
        try:
            sclient.close()
        except:
            raise
    sserveur.close()
    sys.exit(0)


signal.signal(signal.SIGINT, handler)

print("Serveur lancé")

while True:
    print("Attente d'un client ...")
    sclient, adclient = sserveur.accept()
    print(f"Connecté : {adclient}")

    while True:
        try:
            donnees = sclient.recv(4096)

            # client fermé (EOF côté socket)
            if not donnees:
                print("[Client déconnecté]")
                break

            print(donnees.decode())

            reponse = f"{len(donnees)} octets"
            sclient.send(reponse.encode())

        except EOFError:
            # Ctrl+D côté terminal (si tu fais input())
            print("[CTRL+D] Déconnexion client")
            break

        except ConnectionResetError:
            print("[Connexion reset par client]")
            break

    sclient.close()
    sclient = None
