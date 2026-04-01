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


class Header_Convert:
    def __init__(self, Rx_Raw):
        self.TID = Rx_Raw[:2]
        self.PID = Rx_Raw[2:4]
        self.LEN = Rx_Raw[4:6]
        self.UI = Rx_Raw[6:7]


class Data_Convert:
    def __init__(self, Rx_Raw):
        self.CF = Rx_Raw[7:8]
        self.START = Rx_Raw[8:10]
        self.LEN = Rx_Raw[10:12]  # ici = Quantity of Registers pour FC 0x10
        self.VAL = []
        self.BC = None

        match self.CF:
            case b"\x01":
                pass
            case b"\x03":
                pass
            case b"\x06":
                pass
                # TODO: implementer pour x06
            case b"\x10":
                self.BC = Rx_Raw[12:13]
                byte_count = self.BC[0]
                start = int.from_bytes(self.START, "big")
                for i in range(byte_count // 2):
                    val = Rx_Raw[13 + (2 * i) : 13 + (2 * i) + 2]
                    print("ind :", start + i)
                    print("old :", REGISTRE_WORD[start + i])
                    REGISTRE_WORD[start + i] = int.from_bytes(val, "big")
                    print("New :", REGISTRE_WORD[start + i])
                    self.VAL.append(val)
            case _:
                print("Cas non traiter / CF incorect")
                raise EOFError


class Make_Header:
    def __init__(self, Actual_TID, Size_PDU, Actual_UI):
        self.TID = Actual_TID
        self.PID = b"\x00\x00"
        self.LEN = (1 + Size_PDU).to_bytes(2, byteorder="big")  # Unit ID + PDU
        self.UI = Actual_UI
        self.data = self.TID + self.PID + self.LEN + self.UI


class Make_Data:
    def __init__(self, data_convert):

        self.CF = data_convert.CF

        match data_convert.CF:
            case b"\x10" | b"\x06":
                self.START = data_convert.START
                self.QR = data_convert.LEN  # Quantity of Registers
                self.data = self.CF + self.START + self.QR
                self.DATA_BYTES = 5
            case b"\x01":
                # TODO: implementer pour x01
                pass
            case b"\x03":
                start = int.from_bytes(data_convert.START, "big")
                print("start :", start)
                qty = int.from_bytes(data_convert.LEN, "big")
                print("qty :", qty)

                self.BC = (qty * 2).to_bytes(1, byteorder="big")
                self.VAL = b""

                for i in range(qty):
                    print("REGISTRE_WORD :", REGISTRE_WORD[start + i])
                    self.VAL += int(REGISTRE_WORD[start + i]).to_bytes(
                        2, byteorder="big"
                    )
                self.data = self.CF + self.BC + self.VAL
                self.DATA_BYTES = 1 + 1 + len(self.VAL)


def handle_message(header, data):
    if header.PID != b"\x00\x00":
        print("PID invalide")
        return

    # TODO: implementer le check du header, pour pas process si inutil

    data_send = Make_Data(data)
    header_send = Make_Header(header.TID, data_send.DATA_BYTES, header.UI)
    tramme = header_send.data + data_send.data
    print(tramme.hex().upper())


REGISTRE_BOOL = np.zeros(100, dtype=bool)
REGISTRE_WORD = np.zeros(100, dtype=np.uint16)


def main():
    raw_str = input("enter chain (hex): ").replace(" ", "")
    Rx_Raw = bytes.fromhex(raw_str)

    header = Header_Convert(Rx_Raw=Rx_Raw)
    data = Data_Convert(Rx_Raw=Rx_Raw)
    REGISTRE_WORD[1] = 1
    REGISTRE_WORD[2] = 2
    REGISTRE_WORD[3] = 3
    REGISTRE_WORD[4] = 4
    handle_message(header=header, data=data)


if __name__ == "__main__":
    main()
