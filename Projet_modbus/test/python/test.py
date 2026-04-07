# Trame de requête (hexadécimal) :
# 00 01 00 00 00 06 01 03 00 01 00 02
#
# 00 01 : Transaction Identifier
# 00 00 : Protocol Identifier
# 00 06 : Length
# 01    : Unit Identifier
# 03    : Code fonction
# 00 01 : Adresse de départ
# 00 02 : Nombre de registres à lire

# Trame de réponse :
# 00 01 00 00 00 07 01 03 04 00 0A 00 14
#
# 00 01 : Transaction Identifier
# 00 00 : Protocol Identifier
# 00 07 : Length
# 01    : Unit Identifier
# 03    : Code fonction
# 04    : Nombre d’octets de données
# 00 0A : Valeur du registre 1
# 00 14 : Valeur du registre 2
import numpy as np


# =========================
# Registres internes
# =========================
REGISTRE_BOOL = np.zeros(100, dtype=bool)
REGISTRE_WORD = np.zeros(100, dtype=np.uint16)


# =========================
# Header MBAP
# =========================
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


# =========================
# Requête PDU décodée
# =========================
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


# =========================
# Réponse logique
# =========================
class ModbusResponse:
    def __init__(self, function_code: bytes, payload: bytes):
        self.function_code = function_code
        self.payload = payload

    @property
    def pdu(self) -> bytes:
        return self.function_code + self.payload


# =========================
# Construction header réponse
# =========================
def build_mbap_response_header(request_header: MBAPHeader, pdu_size: int) -> bytes:
    pid = b"\x00\x00"
    length = (1 + pdu_size).to_bytes(2, "big")  # Unit ID + PDU
    return request_header.tid + pid + length + request_header.unit_id


# =========================
# Vérifications générales
# =========================
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


# =========================
# Handlers métier
# =========================
def handle_read_coils(req: ModbusRequest) -> ModbusResponse:
    check_bool_range(req.start_address, req.quantity)

    data = b""
    val = 0

    for i in range(req.quantity):
        if REGISTRE_BOOL[req.start_address + i]:
            val |= 1 << (i % 8)

        # on pousse l'octet soit quand il est plein,
        # soit quand on arrive au dernier coil demandé
        if (i % 8 == 7) or (i == req.quantity - 1):
            print("val :", val)
            print(bin(val))
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

    print("old : ", REGISTRE_WORD[req.start_address])
    REGISTRE_WORD[req.start_address] = req.value
    print("new : ", REGISTRE_WORD[req.start_address])

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
        print("old : ", REGISTRE_WORD[req.start_address + i])
        REGISTRE_WORD[req.start_address + i] = val
        print("new : ", REGISTRE_WORD[req.start_address + i])

    payload = req.start_address.to_bytes(2, "big") + req.quantity.to_bytes(2, "big")
    return ModbusResponse(req.function_code, payload)


# =========================
# Traitement principal
# =========================
def handle_message(raw: bytes) -> bytes:
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
            print("fc = 01")
            response = handle_write_multiple_registers(request)

        case _:
            raise ValueError("Code fonction non supporté")

    response_header = build_mbap_response_header(header, len(response.pdu))
    return response_header + response.pdu


# =========================
# Main
# =========================
def main():
    REGISTRE_WORD[1] = 1
    REGISTRE_WORD[2] = 2
    REGISTRE_WORD[3] = 3
    REGISTRE_WORD[4] = 4

    REGISTRE_BOOL[1] = True
    REGISTRE_BOOL[2] = True
    REGISTRE_BOOL[3] = False
    REGISTRE_BOOL[4] = True
    REGISTRE_BOOL[10] = True

    raw_str = input("enter chain (hex): ").replace(" ", "")
    raw = bytes.fromhex(raw_str)

    response = handle_message(raw)
    print(response.hex().upper())


if __name__ == "__main__":
    main()
