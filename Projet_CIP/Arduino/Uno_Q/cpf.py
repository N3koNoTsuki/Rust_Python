"""
cpf.py — Common Packet Format (CPF)

Enveloppe les données CIP dans les commandes SendRRData et SendUnitData.
Référence : ODVA EtherNet/IP Specification, Volume 2, Chapter 2.3.

Structure d'un paquet CPF :
  item_count (2B LE)
  item[] :
    type_id (2B LE)
    length  (2B LE)
    data    (length octets)

Types d'items utilisés :
  0x0000  Null Address          — item d'adresse vide (non-connecté)
  0x00B2  Unconnected Data      — données CIP non-connectées
  0x8002  Connected Address     — adresse connexion I/O (8B : conn_id + seq)
  0x00B1  Connected I/O Data    — données CIP connectées (I/O cyclique)
  0x8000  O→T Socket Address    — sockaddr UDP pour la direction O→T
  0x8001  T→O Socket Address    — sockaddr UDP pour la direction T→O
"""

CPF_NULL_ADDR        = 0x0000
CPF_UNCONNECTED_DATA = 0x00B2
CPF_CONNECTED_ADDR   = 0x8002
CPF_CONNECTED_DATA   = 0x8001
CPF_IO_DATA          = 0x00B1


def parse_cpf(data: bytes) -> list:
    """Décode un paquet CPF et retourne la liste des items.

    Args:
        data : octets bruts commençant par item_count (2B LE)

    Returns:
        Liste de tuples (type_id: int, payload: bytes)
    """
    ietm_count = data[0] + (data[1] << 8)
    list_ietm = []
    ind = 2
    for i in range(ietm_count) :
        type_id = data[ind] + (data[ind + 1] << 8)
        length = data[ind + 2] + (data[ind + 3] << 8)
        payload = data[ind + 4 : ind + 4 + length]
        ind += 4 + length
        list_ietm.append((type_id, payload))
    return list_ietm

def build_cpf(items: list) -> bytes:
    """Construit un paquet CPF à partir d'une liste d'items.

    Args:
        items : liste de tuples (type_id: int, payload: bytes)

    Returns:
        Paquet CPF sérialisé en bytes (little-endian)
    """
    data = bytearray()
    data += (len(items) & 0xFF).to_bytes(1, 'little')
    data += ((len(items) >> 8) & 0xFF).to_bytes(1, 'little')
    for item in items :
        type_id, payload = item
        data += (type_id & 0xFF).to_bytes(1, 'little')
        data += ((type_id >> 8) & 0xFF).to_bytes(1, 'little')
        data += (len(payload) & 0xFF).to_bytes(1, 'little')
        data += ((len(payload) >> 8) & 0xFF).to_bytes(1, 'little')
        data += payload
    return bytes(data)