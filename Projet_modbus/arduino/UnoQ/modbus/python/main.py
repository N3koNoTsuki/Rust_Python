import socket
import numpy as np
import neko_no_lib as nl
from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI


# =========================================================
# Données globales "application"
# =========================================================
Grenoble = nl.City(name="Grenoble", lat=45.18, lon=5.72)
Meteo = nl.Meteo(temp=0.0, location=Grenoble)

REGISTRE_BOOL = np.zeros(100, dtype=bool)
REGISTRE_WORD = np.zeros(100, dtype=np.uint16)


# =========================================================
# Bridge / callbacks Arduino
# =========================================================
def linux_started():
    return True


def python_func(data: float):
    global Meteo
    Meteo.temp = data

    # Exemple : on recopie aussi la température dans un registre Modbus
    # ici en dixième de degré pour éviter les float
    # ex: 23.4°C -> 234
    REGISTRE_WORD[10] = int(data * 10)


# =========================================================
# Modbus TCP - Header MBAP
# =========================================================
class MBAPHeader:
    def __init__(self, raw: bytes):
        if len(raw) < 7:
            raise ValueError("Trame trop courte pour contenir un header MBAP")

        self.tid = raw[0:2]
        self.pid = raw[2:4]
        self.length = raw[4:6]
        self.unit_id = raw[6:7]

    @property
    def length_int(self) -> int:
        return int.from_bytes(self.length, "big")


# =========================================================
# Modbus TCP - Requête décodée
# =========================================================
class ModbusRequest:
    def __init__(self, raw: bytes):
        if len(raw) < 8:
            raise ValueError("Trame trop courte pour contenir un PDU")

        self.function_code = raw[7:8]

        self.start_address = 0
        self.quantity = 0
        self.value = 0
        self.values = []
        self.byte_count = 0

        match self.function_code:
            case b"\x01":
                if len(raw) < 12:
                    raise ValueError("Trame trop courte pour la fonction 0x01")
                self.start_address = int.from_bytes(raw[8:10], "big")
                self.quantity = int.from_bytes(raw[10:12], "big")

            case b"\x03":
                if len(raw) < 12:
                    raise ValueError("Trame trop courte pour la fonction 0x03")
                self.start_address = int.from_bytes(raw[8:10], "big")
                self.quantity = int.from_bytes(raw[10:12], "big")

            case b"\x06":
                if len(raw) < 12:
                    raise ValueError("Trame trop courte pour la fonction 0x06")
                self.start_address = int.from_bytes(raw[8:10], "big")
                self.value = int.from_bytes(raw[10:12], "big")

            case b"\x10":
                if len(raw) < 13:
                    raise ValueError("Trame trop courte pour la fonction 0x10")

                self.start_address = int.from_bytes(raw[8:10], "big")
                self.quantity = int.from_bytes(raw[10:12], "big")
                self.byte_count = raw[12]

                expected_len = 13 + self.byte_count
                if len(raw) < expected_len:
                    raise ValueError("Trame incomplète pour la fonction 0x10")

                for i in range(self.quantity):
                    start = 13 + (2 * i)
                    end = start + 2
                    val = int.from_bytes(raw[start:end], "big")
                    self.values.append(val)

            case _:
                raise ValueError("Code fonction non supporté")


# =========================================================
# Modbus TCP - Réponse
# =========================================================
class ModbusResponse:
    def __init__(self, function_code: bytes, payload: bytes):
        self.function_code = function_code
        self.payload = payload

    @property
    def pdu(self) -> bytes:
        return self.function_code + self.payload


# =========================================================
# Construction du header MBAP réponse
# =========================================================
def build_mbap_response_header(request_header: MBAPHeader, pdu_size: int) -> bytes:
    pid = b"\x00\x00"
    length = (1 + pdu_size).to_bytes(2, "big")  # Unit ID + PDU
    return request_header.tid + pid + length + request_header.unit_id


# =========================================================
# Vérifications
# =========================================================
def validate_mbap(header: MBAPHeader, raw: bytes):
    if header.pid != b"\x00\x00":
        raise ValueError("Protocol Identifier invalide")

    if header.length_int != len(raw[6:]):
        raise ValueError(
            f"Longueur MBAP incohérente : annoncée={header.length_int}, réelle={len(raw[6:])}"
        )


def check_word_range(start: int, qty: int):
    if start < 0:
        raise ValueError("Adresse de départ invalide")
    if qty <= 0:
        raise ValueError("Quantité invalide")
    if start + qty > len(REGISTRE_WORD):
        raise ValueError("Lecture/écriture hors limites du tableau REGISTRE_WORD")


def check_bool_range(start: int, qty: int):
    if start < 0:
        raise ValueError("Adresse de départ invalide")
    if qty <= 0:
        raise ValueError("Quantité invalide")
    if start + qty > len(REGISTRE_BOOL):
        raise ValueError("Lecture hors limites du tableau REGISTRE_BOOL")


# =========================================================
# Handlers métier Modbus
# =========================================================
def handle_read_coils(req: ModbusRequest) -> ModbusResponse:
    check_bool_range(req.start_address, req.quantity)

    data = b""
    val = 0

    for i in range(req.quantity):
        if REGISTRE_BOOL[req.start_address + i]:
            val |= 1 << (i % 8)

        if (i % 8 == 7) or (i == req.quantity - 1):
            data += int(val).to_bytes(1, "big")
            val = 0

    byte_count = len(data).to_bytes(1, "big")
    return ModbusResponse(req.function_code, byte_count + data)


def handle_read_holding_registers(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, req.quantity)

    data = b""
    for i in range(req.quantity):
        val = int(REGISTRE_WORD[req.start_address + i])
        data += val.to_bytes(2, "big")

    byte_count = len(data).to_bytes(1, "big")
    return ModbusResponse(req.function_code, byte_count + data)


def handle_write_single_register(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, 1)

    REGISTRE_WORD[req.start_address] = req.value

    payload = req.start_address.to_bytes(2, "big") + req.value.to_bytes(2, "big")
    return ModbusResponse(req.function_code, payload)


def handle_write_multiple_registers(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, req.quantity)

    if req.byte_count != req.quantity * 2:
        raise ValueError(
            f"Byte count incohérent : byte_count={req.byte_count}, attendu={req.quantity * 2}"
        )

    if len(req.values) != req.quantity:
        raise ValueError("Nombre de valeurs incohérent avec la quantité demandée")

    for i, val in enumerate(req.values):
        REGISTRE_WORD[req.start_address + i] = val

    payload = req.start_address.to_bytes(2, "big") + req.quantity.to_bytes(2, "big")
    return ModbusResponse(req.function_code, payload)


def handle_modbus_message(raw: bytes) -> bytes:
    header = MBAPHeader(raw)
    validate_mbap(header, raw)

    request = ModbusRequest(raw)

    match request.function_code:
        case b"\x01":
            print("fc = 01")
            response = handle_read_coils(request)

        case b"\x03":
            print("fc = 03")
            response = handle_read_holding_registers(request)

        case b"\x06":
            print("fc = 06")
            response = handle_write_single_register(request)

        case b"\x10":
            print("fc = 10")
            response = handle_write_multiple_registers(request)

        case _:
            raise ValueError("Code fonction non supporté")

    response_header = build_mbap_response_header(header, len(response.pdu))
    return response_header + response.pdu


# =========================================================
# Socket serveur Arduino / Linux
# =========================================================
sserveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sserveur.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sserveur.bind(("0.0.0.0", 5010))
sserveur.listen(5)
sserveur.settimeout(0.0)

sclient = None
adclient = None

print("Serveur Modbus TCP lancé sur 0.0.0.0:5010")

Bridge.provide("linux_started", linux_started)
Bridge.provide("python_func", python_func)

ui = WebUI()
ui.expose_api("GET", "/hello", lambda: {"message": "initialisation"})


# =========================================================
# Utilitaires socket
# =========================================================
def close_client():
    global sclient, adclient

    if sclient is not None:
        try:
            sclient.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass

        try:
            sclient.close()
        except Exception:
            pass

    sclient = None
    adclient = None


def recv_exact(sock, size: int) -> bytes:
    data = b""

    while len(data) < size:
        chunk = sock.recv(size - len(data))

        if chunk == b"":
            raise ConnectionResetError("Connexion fermée proprement par le client")

        data += chunk

    return data


def accept_new_client_if_any():
    global sclient, adclient

    while True:
        try:
            client, addr = sserveur.accept()
            client.settimeout(1.0)

            print(f"Nouveau client détecté : {addr}")

            if sclient is not None:
                print(f"Remplacement de l'ancien client : {adclient}")
                close_client()

            sclient = client
            adclient = addr
            print(f"Client actif : {adclient}")

        except BlockingIOError:
            break
        except Exception as e:
            print(f"[Erreur accept] {e}")
            break


# =========================================================
# Lecture d'une trame Modbus TCP complète
# =========================================================
def recv_modbus_tcp_frame(sock) -> bytes:
    # D'abord header MBAP complet = 7 octets
    mbap = recv_exact(sock, 7)

    # length = Unit ID + PDU
    length_field = int.from_bytes(mbap[4:6], "big")

    # On a déjà lu le Unit ID dans les 7 octets
    # Il reste donc à lire le PDU : length_field - 1
    if length_field < 1:
        raise ValueError("Champ length MBAP invalide")

    pdu = recv_exact(sock, length_field - 1)

    return mbap + pdu


# =========================================================
# Boucle principale Arduino App
# =========================================================
def loop():
    global sclient, adclient

    accept_new_client_if_any()

    if sclient is None:
        return

    try:
        raw_request = recv_modbus_tcp_frame(sclient)
        print(f"Trame Modbus reçue : {raw_request.hex().upper()}")

        raw_response = handle_modbus_message(raw_request)
        print(f"Trame Modbus réponse : {raw_response.hex().upper()}")

        sclient.sendall(raw_response)

        # Exemple optionnel : remonter la température au WebUI
        ui.send_message("temp", Meteo.temp)

    except socket.timeout:
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


# =========================================================
# Init de quelques valeurs de test
# =========================================================
REGISTRE_WORD[1] = 1
REGISTRE_WORD[2] = 2
REGISTRE_WORD[3] = 3
REGISTRE_WORD[4] = 4

REGISTRE_BOOL[1] = True
REGISTRE_BOOL[2] = True
REGISTRE_BOOL[3] = False
REGISTRE_BOOL[4] = True
REGISTRE_BOOL[10] = True


App.run(user_loop=loop)
