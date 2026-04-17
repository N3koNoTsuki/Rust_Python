"""
eip.py — EtherNet/IP encapsulation layer

Gère le header EIP 24 octets commun à toutes les commandes TCP et UDP.
Référence : ODVA EtherNet/IP Specification, Volume 2, Chapter 2.

Commandes supportées :
  - RegisterSession  (0x0065) : ouverture de session TCP
  - ListIdentity     (0x0063) : découverte du device
  - SendRRData       (0x006F) : échange requête/réponse non-connecté (CIP)
  - SendUnitData     (0x0070) : échange connecté (I/O)
"""

from dataclasses import dataclass
import struct
import logging

log = logging.getLogger("eip")


CMD_REGISTER_SESSION = 0x0065
CMD_LIST_IDENTITY    = 0x0063
CMD_SEND_RR_DATA     = 0x006F
CMD_SEND_UNIT_DATA   = 0x0070


@dataclass
class EIPHeader:
    """Header EIP de 24 octets, commun à toutes les commandes."""
    command         : int
    length          : int   # Taille du payload en octets
    session_handle  : int
    status          : int
    sender_context  : bytes # 8 octets opaques, renvoyés en miroir dans la réponse
    options         : int


def parse_eip_header(data: bytes) -> EIPHeader:
    """Décode les 24 premiers octets d'un paquet EIP.

    Retourne None si le paquet est trop court (< 24 octets).
    Format struct : '<HHII8sI' (little-endian).
    """
    if len(data) < 24:
        return None
    return EIPHeader(*struct.unpack('<HHII8sI', data[:24]))


def build_eip_header(command: int, length: int,
                     session_handle: int,
                     status: int = 0,
                     sender_context: bytes = b'\x00' * 8,
                     options: int = 0) -> bytes:
    """Construit un header EIP de 24 octets.

    Args:
        command        : code de commande EIP (CMD_*)
        length         : taille du payload qui suit le header
        session_handle : handle de session assigné lors du RegisterSession
        status         : code de statut (0 = succès)
        sender_context : 8 octets à renvoyer en miroir dans la réponse
        options        : champ options (toujours 0)
    """
    return struct.pack('<HHII8sI',
                       command,
                       length,
                       session_handle,
                       status,
                       sender_context,
                       options)


def handle_register_session(header: EIPHeader, data: bytes) -> bytes:
    """Traite une requête RegisterSession et retourne la réponse complète.

    Assigne un session_handle fixe (0x12345678) et renvoie le payload
    standard : version=1, options=0 (4 octets).
    Le sender_context est renvoyé en miroir dans le header de réponse.
    """
    payload = struct.pack('<HH', 1, 0)  # version=1, options=0
    header.session_handle = 0x12345678
    log.info(f"Registering new session, handle=0x{header.session_handle:08X}")
    rep_header = build_eip_header(
        command=CMD_REGISTER_SESSION,
        length=len(payload),
        session_handle=header.session_handle,
        sender_context=header.sender_context
    )
    return rep_header + payload
