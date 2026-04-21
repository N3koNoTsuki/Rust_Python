from arduino.app_utils import *
import time
import neko_no_lib as nl

from arduino.app_bricks.web_ui import WebUI

Grenoble = nl.City(name="Grenoble", lat=45.18, lon=5.72)
Meteo = nl.Meteo(temp=None, location=Grenoble)


def linux_started():
    return True


def python_func(data: float):
    global Meteo
    Meteo.temp = data
    print("Temp reçue:", data)


Bridge.provide("linux_started", linux_started)
Bridge.provide("python_func", python_func)

print("Hello WebUI")
ui = WebUI()

ui.expose_api("GET", "/hello", lambda: {"message": "initialisation"})


def loop():
    # Envoi régulier vers l'interface web
    if Meteo.temp is not None:
        ui.send_message("temp", Meteo.temp)
        nl.print_meteo(Meteo, False)
    time.sleep(1)


App.run(user_loop=loop)
