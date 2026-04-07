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
            case b"\x01" | b"\x03":
                if len(raw) < 12:
                    raise ValueError("Trame trop courte")
                self.start_address = int.from_bytes(raw[8:10], "big")
                self.quantity = int.from_bytes(raw[10:12], "big")

            case b"\x06":
                if len(raw) < 12:
                    raise ValueError("Trame trop courte")
                self.start_address = int.from_bytes(raw[8:10], "big")
                self.value = int.from_bytes(raw[10:12], "big")

            case b"\x10":
                if len(raw) < 13:
                    raise ValueError("Trame trop courte")

                self.start_address = int.from_bytes(raw[8:10], "big")
                self.quantity = int.from_bytes(raw[10:12], "big")
                self.byte_count = raw[12]

                expected_len = 13 + self.byte_count
                if len(raw) < expected_len:
                    raise ValueError("Trame incomplète")

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
    length = (1 + pdu_size).to_bytes(2, "big")
    return request_header.tid + pid + length + request_header.unit_id


# =========================================================
# Vérifications
# =========================================================
def validate_mbap(header: MBAPHeader, raw: bytes):
    if header.pid != b"\x00\x00":
        raise ValueError("Protocol Identifier invalide")

    # ✔️ CORRECTION ICI
    if header.length_int != len(raw[6:]):
        raise ValueError(
            f"Longueur MBAP incohérente : annoncée={header.length_int}, réelle={len(raw[6:])}"
        )


def check_word_range(start: int, qty: int):
    if start < 0 or qty <= 0 or start + qty > len(REGISTRE_WORD):
        raise ValueError("Erreur plage registre WORD")


def check_bool_range(start: int, qty: int):
    if start < 0 or qty <= 0 or start + qty > len(REGISTRE_BOOL):
        raise ValueError("Erreur plage registre BOOL")


# =========================================================
# Handlers
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

    return ModbusResponse(req.function_code, len(data).to_bytes(1, "big") + data)


def handle_read_holding_registers(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, req.quantity)

    data = b""
    for i in range(req.quantity):
        val = int(REGISTRE_WORD[req.start_address + i])
        data += val.to_bytes(2, "big")

    return ModbusResponse(req.function_code, len(data).to_bytes(1, "big") + data)


def handle_write_single_register(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, 1)

    REGISTRE_WORD[req.start_address] = req.value
    payload = req.start_address.to_bytes(2, "big") + req.value.to_bytes(2, "big")

    return ModbusResponse(req.function_code, payload)


def handle_write_multiple_registers(req: ModbusRequest) -> ModbusResponse:
    check_word_range(req.start_address, req.quantity)

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
            response = handle_read_coils(request)
        case b"\x03":
            response = handle_read_holding_registers(request)
        case b"\x06":
            response = handle_write_single_register(request)
        case b"\x10":
            response = handle_write_multiple_registers(request)
        case _:
            raise ValueError("Code fonction non supporté")

    response_header = build_mbap_response_header(header, len(response.pdu))
    return response_header + response.pdu


# =========================================================
# Socket serveur
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
# Utils socket
# =========================================================
def close_client():
    global sclient, adclient
    if sclient:
        try:
            sclient.shutdown(socket.SHUT_RDWR)
        except:
            pass
        sclient.close()
    sclient = None
    adclient = None


def recv_exact(sock, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if chunk == b"":
            raise ConnectionResetError
        data += chunk
    return data


def accept_new_client_if_any():
    global sclient, adclient
    while True:
        try:
            client, addr = sserveur.accept()
            client.settimeout(1.0)

            print(f"Nouveau client détecté : {addr}")

            if sclient:
                close_client()

            sclient = client
            adclient = addr

        except BlockingIOError:
            break


# =========================================================
# Réception Modbus TCP
# =========================================================
def recv_modbus_tcp_frame(sock) -> bytes:
    mbap = recv_exact(sock, 7)
    length_field = int.from_bytes(mbap[4:6], "big")

    # ✔️ CORRECTION ICI
    pdu = recv_exact(sock, length_field - 1)

    return mbap + pdu


# =========================================================
# Loop
# =========================================================
def loop():
    global sclient

    accept_new_client_if_any()

    if not sclient:
        return

    try:
        raw_request = recv_modbus_tcp_frame(sclient)
        print("RX:", raw_request.hex())

        raw_response = handle_modbus_message(raw_request)
        print("TX:", raw_response.hex())

        sclient.sendall(raw_response)

    except socket.timeout:
        return

    except Exception:
        close_client()


# =========================================================
# Init
# =========================================================
REGISTRE_WORD[1] = 1
REGISTRE_WORD[2] = 2
REGISTRE_WORD[3] = 3
REGISTRE_WORD[4] = 4

REGISTRE_BOOL[1] = True
REGISTRE_BOOL[2] = True
REGISTRE_BOOL[3] = False
REGISTRE_BOOL[4] = True

App.run(user_loop=loop)
