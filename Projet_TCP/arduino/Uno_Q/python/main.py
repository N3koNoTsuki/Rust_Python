import socket
import time
import neko_no_lib as nl
from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI

Grenoble = nl.City(name="Grenoble", lat=45.18, lon=5.72)
Meteo = nl.Meteo(temp=0.0, location=Grenoble)


def linux_started():
    return True


def python_func(data: float):
    global Meteo
    Meteo.temp = data
    print("Temp reçue:", data)


sserveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sserveur.bind(("0.0.0.0", 5010))
sserveur.listen(1)
sclient = None
print("Serveur lancé")


Bridge.provide("linux_started", linux_started)
Bridge.provide("python_func", python_func)

print("Hello WebUI")
ui = WebUI()

ui.expose_api("GET", "/hello", lambda: {"message": "initialisation"})


def loop():
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

            decoded = donnees.decode()
            print(decoded)
            if decoded == "temp":
                # Envoi régulier vers l'interface web
                if Meteo.temp is not None:
                    ui.send_message("temp", Meteo.temp)
                    nl.print_meteo(Meteo, False)
                    reponse = f"{decoded}"
                    sclient.send(reponse.encode())

            else:
                reponse = f"{len(donnees)} octets"
                sclient.send(reponse.encode())

        except EOFError:
            print("Déconnexion client")
            break

        except ConnectionResetError:
            print("[Connexion reset par client]")
            break

    sclient.close()
    sclient = None


App.run(user_loop=loop)
