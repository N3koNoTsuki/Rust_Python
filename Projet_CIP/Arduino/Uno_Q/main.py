"""
EtherNet/IP CIP Adapter — Arduino Uno Q
Basé sur Arduino.eds :
  - VendCode : 0xFFFF  VendName : "Arduino"
  - ProdType : 12 (Communications Adapter)
  - ProdCode : 1  MajRev : 1  MinRev : 1
  - Assem100 : Output (PLC->Arduino) 1 byte  pins D2-D6
  - Assem101 : Input  (Arduino->PLC) 1 byte  pins D7-D11
  - Assem102 : Configuration         0 byte
  - Connection1 : Exclusive Owner, Class1, Cyclic, SCHEDULED
  - Transport word1 : 0x84010002
  - Transport word2 : 0x44240005
  - Path CIP : "20 06 24 01"

MPU Linux (QRB2210) — asyncio, TCP:44818, UDP:2222
Watchdog 500 ms : si aucun paquet O->T recu, sorties = 0
Bridge MCU via Arduino_RouterBridge sur /dev/ttyHS1
"""

import asyncio
import socket
import struct
import logging
import time
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("enip_adapter")

# ---------------------------------------------------------------------------
# Constantes EDS — identité de l'appareil
# ---------------------------------------------------------------------------
VENDOR_ID    = 0xFFFF
DEVICE_TYPE  = 12
PRODUCT_CODE = 1
MAJOR_REV    = 1
MINOR_REV    = 1
PRODUCT_NAME = b"Arduino Uno Q"

# ---------------------------------------------------------------------------
# Réseau
# ---------------------------------------------------------------------------
TCP_PORT   = 44818
UDP_PORT   = 2222
WATCHDOG_S = 0.5  # secondes avant mise à zéro des sorties si plus de paquet O->T

# ---------------------------------------------------------------------------
# Commandes EtherNet/IP (EIP encapsulation layer)
# ---------------------------------------------------------------------------
CMD_LIST_IDENTITY = 0x0065
CMD_LIST_SERVICES = 0x0004
CMD_REGISTER      = 0x0065
CMD_SEND_RR       = 0x006F
CMD_SEND_UNIT     = 0x0070

# ---------------------------------------------------------------------------
# Services CIP (Connection Manager / Identity Object)
# ---------------------------------------------------------------------------
SRV_FORWARD_OPEN       = 0x54
SRV_FORWARD_OPEN_LARGE = 0x5B
SRV_FORWARD_CLOSE      = 0x4E
SRV_GET_ATTR_ALL       = 0x01
SRV_GET_ATTR_SINGLE    = 0x0E

# ---------------------------------------------------------------------------
# Codes de statut CIP
# ---------------------------------------------------------------------------
STS_SUCCESS       = 0x00
STS_PATH_UNKNOWN  = 0x05
STS_INVALID_PARAM = 0x20
# Taille fixe de l'en-tête EIP : cmd(2) + length(2) + session(4) + status(4) + sender_ctx(8) + options(4)
EIP_HEADER_SIZE = 24

# ---------------------------------------------------------------------------
# État global de l'adaptateur
# ---------------------------------------------------------------------------
@dataclass
class AdapterState:
    output_byte:      int   = 0x00   # octet de sorties (Assembly 100, pins D2-D6)
    input_byte:       int   = 0x00   # octet d'entrées  (Assembly 101, pins D7-D11)
    last_ot_time:     float = 0.0    # horodatage du dernier paquet O->T reçu
    session_handle:   int   = 0
    connection_id_ot: int   = 0      # Connection ID O->T (PLC vers adaptateur)
    connection_id_to: int   = 0      # Connection ID T->O (adaptateur vers PLC)
    connection_sn:    int   = 0
    orig_vendor:      int   = 0
    orig_serial:      int   = 0
    o_api:            int   = 500_000  # Actual Packet Interval O->T (µs)
    t_api:            int   = 500_000  # Actual Packet Interval T->O (µs)
    cip_seq_count:    int   = 0        # compteur 16-bit pour le CIP data item
    encap_seq:        int   = 0        # compteur 32-bit pour l'adresse item (Sequenced Address)
    connected:        bool  = False
    udp_transport:    Optional[object] = None
    plc_addr:         Optional[tuple]  = None

state = AdapterState()

# ---------------------------------------------------------------------------
# Bridge MCU (Arduino_RouterBridge) — ou mode simulation si absent
# ---------------------------------------------------------------------------
try:
    from Arduino_RouterBridge import RouterBridge
    bridge = RouterBridge("/dev/ttyHS1", 115200)
    SIMULATION = False
    log.info("Bridge MCU initialise sur /dev/ttyHS1")
except ImportError:
    SIMULATION = True
    log.warning("Arduino_RouterBridge non disponible - mode simulation")


def set_outputs(byte_val: int):
    """Applique les 5 bits de sortie (D2-D6) sur l'Arduino ou logue en simulation."""
    if SIMULATION:
        log.debug(f"[SIM] set_outputs(0x{byte_val:02X})")
        return
    try:
        bridge.call("set_outputs", [byte_val & 0x1F])
    except Exception as e:
        log.error(f"set_outputs error: {e}")


def get_inputs() -> int:
    """Lit les 5 bits d'entrée (D7-D11) depuis l'Arduino, ou retourne l'état simulé."""
    if SIMULATION:
        return state.input_byte
    try:
        return int(bridge.call("get_inputs", [])) & 0x1F
    except Exception as e:
        log.error(f"get_inputs error: {e}")
        return 0x00


# ---------------------------------------------------------------------------
# Utilitaires bas niveau
# ---------------------------------------------------------------------------
def ip2udint(ip_str: str) -> int:
    """Convertit une adresse IPv4 en entier non-signé 32 bits (big-endian)."""
    try:
        return struct.unpack('>I', socket.inet_aton(ip_str))[0]
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Construction / parsing des en-têtes EIP (24 octets)
# cmd(2) length(2) session(4) status(4) sender_ctx(8) options(4)
# ---------------------------------------------------------------------------
def eip_header(cmd: int, length: int, session: int, status: int = 0,
               sender_ctx: bytes = b'\x00' * 8, options: int = 0) -> bytes:
    """Construit un en-tête EIP de 24 octets."""
    ctx = (sender_ctx + b'\x00' * 8)[:8]
    return struct.pack("<HHIIQ", cmd, length, session, status,
        int.from_bytes(ctx, "little")) + struct.pack("<I", options)


def parse_eip_header(data: bytes) -> dict:
    """Extrait les champs de l'en-tête EIP et retourne un dict (vide si données insuffisantes)."""
    if len(data) < EIP_HEADER_SIZE:
        return {}
    cmd, length, session, status = struct.unpack_from("<HHII", data, 0)
    sender_ctx = data[12:20]
    return {
        "cmd":        cmd,
        "length":     length,
        "session":    session,
        "status":     status,
        "sender_ctx": sender_ctx,
        "payload":    data[EIP_HEADER_SIZE:],
    }


def build_service_response(hdr: dict, service: int, data: bytes) -> bytes:
    """Encapsule une réponse CIP dans un paquet SendRRData réussi."""
    cip     = bytes([service | 0x80, 0x00, STS_SUCCESS, 0x00]) + data
    cpf     = struct.pack("<HHHH", 0x0000, 0, 0x00B2, len(cip)) + cip
    payload = struct.pack("<IH", 0, 0) + cpf
    return eip_header(CMD_SEND_RR, len(payload), hdr["session"],
                      sender_ctx=hdr["sender_ctx"]) + payload


def build_error_response(hdr: dict, status: int) -> bytes:
    """Encapsule une réponse d'erreur CIP (service 0x8E) dans un paquet SendRRData."""
    cip     = bytes([0x8E, 0x00, status, 0x00])
    cpf     = struct.pack("<HHHH", 0x0000, 0, 0x00B2, len(cip)) + cip
    payload = struct.pack("<IH", 0, 0) + cpf
    return eip_header(CMD_SEND_RR, len(payload), hdr["session"],
                      sender_ctx=hdr["sender_ctx"]) + payload


# ---------------------------------------------------------------------------
# Gestionnaires des commandes EIP (couche encapsulation)
# ---------------------------------------------------------------------------
def handle_register_session(hdr: dict) -> bytes:
    """Enregistre une nouvelle session EIP et retourne le handle alloué."""
    state.session_handle = (state.session_handle + 1) & 0xFFFFFFFF
    payload = struct.pack("<HH", 1, 0)
    return eip_header(CMD_REGISTER, len(payload), state.session_handle) + payload


def handle_list_identity(hdr: dict) -> bytes:
    """Répond à la commande ListIdentity avec les informations de l'appareil."""
    name     = PRODUCT_NAME
    identity = struct.pack("<HHHBBHBBH",
        1, 0,
        VENDOR_ID, DEVICE_TYPE, PRODUCT_CODE,
        MAJOR_REV, MINOR_REV,
        0x0060, len(name)
    ) + name + b'\x00'
    item    = struct.pack("<HH", 0x000C, len(identity)) + identity
    payload = struct.pack("<H", 1) + item
    return eip_header(CMD_LIST_IDENTITY, len(payload), 0) + payload


def handle_list_services(hdr: dict) -> bytes:
    """Répond à la commande ListServices en déclarant le service Communications."""
    svc_name  = b"Communications\x00\x00"
    item_body = struct.pack("<HHH", 1, 0x20, 0) + svc_name
    item      = struct.pack("<HH", 0x0100, len(item_body)) + item_body
    payload   = struct.pack("<H", 1) + item
    return eip_header(CMD_LIST_SERVICES, len(payload), hdr["session"]) + payload


# ---------------------------------------------------------------------------
# Gestionnaires des services CIP (Connection Manager)
# ---------------------------------------------------------------------------
def handle_forward_open(req_data: bytes, hdr: dict) -> bytes:
    """
    Traite un Forward Open (CIP Vol.1 Table 3-5.16) et établit la connexion I/O.

    Layout du payload :
      tick_time(1)  timeout_ticks(1)
      ot_cid(4)     to_cid(4)
      conn_sn(2)    orig_vendor(2)   orig_serial(4)
      timeout_mult(1)  reserved(3)
      ot_rpi(4)     ot_params(2)
      to_rpi(4)     to_params(2)
      transport(1)  path_size(1)  path(N)

    La réponse n'inclut pas de socket items : le PLC utilise l'IP source
    de la session TCP pour les paquets O->T UDP (comportement PointIO Rockwell).
    """
    if len(req_data) < 36:
        log.warning(f"Forward Open trop court: {len(req_data)}B")
        return build_error_response(hdr, STS_INVALID_PARAM)

    try:
        offset = 0
        tick_time     = req_data[offset];                                    offset += 1
        timeout_ticks = req_data[offset];                                    offset += 1
        ot_cid        = struct.unpack_from('<I', req_data, offset)[0];       offset += 4
        to_cid        = struct.unpack_from('<I', req_data, offset)[0];       offset += 4
        conn_sn       = struct.unpack_from('<H', req_data, offset)[0];       offset += 2
        orig_vendor   = struct.unpack_from('<H', req_data, offset)[0];       offset += 2
        orig_serial   = struct.unpack_from('<I', req_data, offset)[0];       offset += 4
        timeout_mult  = req_data[offset];                                    offset += 1
        offset += 3  # reserved
        ot_rpi        = struct.unpack_from('<I', req_data, offset)[0];       offset += 4
        ot_params     = struct.unpack_from('<H', req_data, offset)[0];       offset += 2
        to_rpi        = struct.unpack_from('<I', req_data, offset)[0];       offset += 4
        to_params     = struct.unpack_from('<H', req_data, offset)[0];       offset += 2
        transport     = req_data[offset];                                    offset += 1
        path_size     = req_data[offset];                                    offset += 1
    except (IndexError, struct.error) as e:
        log.error(f"Forward Open parse error: {e}")
        return build_error_response(hdr, STS_INVALID_PARAM)

    # Mettre à jour l'état de connexion
    state.connection_id_ot = ot_cid if ot_cid else 0x1000
    state.connection_id_to = to_cid if to_cid else 0x1001
    state.connection_sn    = conn_sn
    state.orig_vendor      = orig_vendor
    state.orig_serial      = orig_serial
    state.o_api            = ot_rpi if ot_rpi else 500_000
    state.t_api            = to_rpi if to_rpi else 500_000
    state.connected        = True
    state.last_ot_time     = time.monotonic()

    if state.plc_addr is None and hasattr(state, '_plc_tcp_ip') and state._plc_tcp_ip:
        state.plc_addr = (state._plc_tcp_ip, UDP_PORT)
        log.info(f"PLC UDP addr: {state.plc_addr}")

    log.info(
        f"Forward Open OK | "
        f"O->T CID=0x{state.connection_id_ot:08X} "
        f"T->O CID=0x{state.connection_id_to:08X} "
        f"SN={conn_sn} "
        f"RPI O->T={ot_rpi}us T->O={to_rpi}us"
    )

    resp  = struct.pack('<II',  state.connection_id_ot, state.connection_id_to)
    resp += struct.pack('<HHI', conn_sn, orig_vendor, orig_serial)
    resp += struct.pack('<II',  state.o_api, state.t_api)
    resp += struct.pack('<BB',  0, 0)   # App Reply Size=0, Reserved=0
    return build_service_response(hdr, SRV_FORWARD_OPEN, resp)


def handle_forward_close(req_data: bytes, hdr: dict) -> bytes:
    """Ferme la connexion I/O et remet les sorties à zéro."""
    state.connected   = False
    state.output_byte = 0x00
    set_outputs(0x00)
    log.info("Forward Close — connexion fermee, sorties a zero")

    conn_sn = orig_vendor = orig_serial = 0
    if len(req_data) >= 8:
        conn_sn, orig_vendor, orig_serial = struct.unpack_from("<HHI", req_data, 2)

    resp = struct.pack("<HHIBB", conn_sn, orig_vendor, orig_serial, 0, 0)
    return build_service_response(hdr, SRV_FORWARD_CLOSE, resp)


# ---------------------------------------------------------------------------
# Gestionnaires des attributs CIP (Get Attribute)
# ---------------------------------------------------------------------------
def handle_get_attr_all(path: bytes, hdr: dict) -> bytes:
    """Retourne tous les attributs de l'objet Identity (classe 0x01)."""
    name = PRODUCT_NAME
    data = struct.pack("<HHHBBH",
        VENDOR_ID, DEVICE_TYPE, PRODUCT_CODE,
        MAJOR_REV, MINOR_REV, 0x0060
    ) + bytes([len(name)]) + name
    return build_service_response(hdr, SRV_GET_ATTR_ALL, data)


def handle_get_attr_single(path: bytes, hdr: dict) -> bytes:
    """
    Retourne un attribut CIP individuel selon la classe et l'instance.

    Classes supportées :
      - 0x01 : Identity Object        (attributs de l'appareil)
      - 0xC0 : TCP/IP Interface Object (configuration réseau — critique pour Rockwell)
      - 0xF4 : Port Object             (informations sur le port Ethernet)

    Une réponse incorrecte sur la classe 0xC0 peut faire abandonner la connexion au PLC.
    """
    cls  = path[1] if len(path) >= 2 else 0
    inst = path[3] if len(path) >= 4 else 0
    attr = path[5] if len(path) >= 6 else 0
    log.info(f"    GetAttrSingle class=0x{cls:02X} inst={inst} attr=0x{attr:02X}")

    # ------------------------------------------------------------------
    # Classe 0x01 — Identity Object
    # ------------------------------------------------------------------
    if cls == 0x01:
        if attr == 0x01:   # Vendor ID
            data = struct.pack("<H", VENDOR_ID)
        elif attr == 0x02: # Device Type
            data = struct.pack("<H", DEVICE_TYPE)
        elif attr == 0x03: # Product Code
            data = struct.pack("<H", PRODUCT_CODE)
        elif attr == 0x04: # Revision
            data = struct.pack("<BB", MAJOR_REV, MINOR_REV)
        elif attr == 0x05: # Status (WORD)
            data = struct.pack("<H", 0x0060)
        elif attr == 0x06: # Serial Number
            data = struct.pack("<I", 0x00000001)
        elif attr == 0x07: # Product Name
            data = bytes([len(PRODUCT_NAME)]) + PRODUCT_NAME
        else:
            data = struct.pack("<I", 0)

    # ------------------------------------------------------------------
    # Classe 0xC0 — TCP/IP Interface Object (CIP Vol.2 Appendix C)
    # ------------------------------------------------------------------
    elif cls == 0xC0:
        our_ip  = getattr(state, '_our_ip',     '192.120.0.202')
        plc_ip  = getattr(state, '_plc_tcp_ip', '192.120.0.206')

        # Déduction du masque et de la passerelle depuis l'IP (hypothèse /24)
        parts   = our_ip.split('.')
        netmask = '255.255.255.0'
        gateway = f"{parts[0]}.{parts[1]}.{parts[2]}.1"

        if attr == 0x01:   # Interface Status — 0x1 = configurée (statique)
            data = struct.pack("<I", 0x00000001)
        elif attr == 0x02: # Interface Config Capability — bit2=DHCP, bit4=configurable
            data = struct.pack("<I", 0x00000014)
        elif attr == 0x03: # Interface Config Control — 0 = config statique
            data = struct.pack("<I", 0x00000000)
        elif attr == 0x04: # Interface Configuration : IP(4)+subnet(4)+gw(4)+DNS1(4)+DNS2(4)+domain
            data  = struct.pack(">IIIII",
                ip2udint(our_ip),
                ip2udint(netmask),
                ip2udint(gateway),
                0, 0  # DNS servers (non configurés)
            )
            data += b'\x00'  # domain name = SHORT_STRING vide
        elif attr == 0x05: # Hostname (SHORT_STRING)
            hostname = b'arduino-uno-q'
            data = bytes([len(hostname)]) + hostname
        elif attr == 0x06: # Safety Network Number (optionnel)
            data = b'\x00' * 6
        else:
            data = struct.pack("<I", 0)

    # ------------------------------------------------------------------
    # Classe 0xF4 — Port Object
    # ------------------------------------------------------------------
    elif cls == 0xF4:
        if attr == 0x01:   # Port type — 4 = EtherNet/IP
            data = struct.pack("<H", 4)
        elif attr == 0x02: # Port number
            data = struct.pack("<H", 1)
        elif attr == 0x07: # Port name (SHORT_STRING)
            name = b'Ethernet'
            data = bytes([len(name)]) + name
        else:
            data = struct.pack("<I", 0)

    # ------------------------------------------------------------------
    # Toutes les autres classes : réponse générique
    # ------------------------------------------------------------------
    else:
        data = struct.pack("<I", 0x00000000)

    return build_service_response(hdr, SRV_GET_ATTR_SINGLE, data)


# ---------------------------------------------------------------------------
# Routage des requêtes CIP et traitement SendRRData
# ---------------------------------------------------------------------------
def route_cip_request(cip: bytes, hdr: dict) -> bytes:
    """Décode le service CIP et dispatche vers le bon gestionnaire."""
    if len(cip) < 2:
        return build_error_response(hdr, STS_INVALID_PARAM)

    service  = cip[0]
    path_wds = cip[1]
    path     = cip[2 : 2 + path_wds * 2]
    req_data = cip[2 + path_wds * 2 :]
    log.info(f"    CIP service=0x{service:02X} path={path.hex()} datalen={len(req_data)}")

    if service in (SRV_FORWARD_OPEN, SRV_FORWARD_OPEN_LARGE):
        return handle_forward_open(req_data, hdr)
    if service == SRV_FORWARD_CLOSE:
        return handle_forward_close(req_data, hdr)
    if service == SRV_GET_ATTR_ALL:
        return handle_get_attr_all(path, hdr)
    if service == SRV_GET_ATTR_SINGLE:
        return handle_get_attr_single(path, hdr)

    log.warning(f"    CIP service inconnu: 0x{service:02X}")
    return build_error_response(hdr, STS_PATH_UNKNOWN)


def process_send_rr(hdr: dict, payload: bytes) -> bytes:
    """Extrait le CIP data item d'un paquet SendRRData et le route."""
    if len(payload) < 6:
        return build_error_response(hdr, STS_INVALID_PARAM)

    cpf = payload[6:]
    if len(cpf) < 2:
        return build_error_response(hdr, STS_INVALID_PARAM)

    item_count = struct.unpack_from("<H", cpf)[0]
    offset     = 2
    cip_data   = b""

    for _ in range(item_count):
        if offset + 4 > len(cpf):
            break
        item_type, item_len = struct.unpack_from("<HH", cpf, offset)
        offset += 4
        if item_type == 0x00B2:
            cip_data = cpf[offset : offset + item_len]
        offset += item_len

    if not cip_data:
        return build_error_response(hdr, STS_INVALID_PARAM)

    return route_cip_request(cip_data, hdr)


# ---------------------------------------------------------------------------
# Protocoles asyncio — TCP (encapsulation EIP) et UDP (I/O temps réel)
# ---------------------------------------------------------------------------
class EIPTCPProtocol(asyncio.Protocol):
    """Protocole TCP : gère la session EIP et les requêtes CIP explicites."""

    def __init__(self):
        self.buf      = b""
        self.transport = None
        self.peer_ip   = None

    def connection_made(self, transport):
        self.transport = transport
        peer = transport.get_extra_info('peername')
        sock = transport.get_extra_info('sockname')
        self.peer_ip = peer[0] if peer else None
        if sock:
            state._our_ip = sock[0]
        log.info(f"TCP connexion depuis {peer} (notre IP locale: {getattr(state, '_our_ip', '?')})")

    def connection_lost(self, exc):
        log.info("TCP connexion fermee")

    def data_received(self, data: bytes):
        self.buf += data
        while len(self.buf) >= EIP_HEADER_SIZE:
            hdr = parse_eip_header(self.buf)
            if not hdr:
                self.buf = b""
                break
            total = EIP_HEADER_SIZE + hdr["length"]
            if len(self.buf) < total:
                break
            packet   = self.buf[:total]
            self.buf = self.buf[total:]
            try:
                response = self.dispatch(hdr, packet[EIP_HEADER_SIZE:])
                if response and self.transport:
                    self.transport.write(response)
            except Exception as e:
                log.error(f"dispatch error: {e}", exc_info=True)

    def dispatch(self, hdr: dict, payload: bytes) -> Optional[bytes]:
        """Distribue une commande EIP vers le bon gestionnaire."""
        cmd = hdr["cmd"]
        if self.peer_ip:
            state._plc_tcp_ip = self.peer_ip
        log.info(
            f">>> CMD=0x{cmd:04X} len={hdr['length']} "
            f"session=0x{hdr['session']:08X} "
            f"payload_hex={payload[:16].hex()}"
        )

        # 0x0065 sert à la fois pour RegisterSession (length=4) et ListIdentity (length=0)
        if cmd == CMD_REGISTER:
            return handle_register_session(hdr) if hdr["length"] == 4 \
                   else handle_list_identity(hdr)
        if cmd == CMD_LIST_SERVICES:
            return handle_list_services(hdr)
        if cmd in (CMD_SEND_RR, CMD_SEND_UNIT):
            return process_send_rr(hdr, payload)

        log.warning(f"Commande EIP inconnue: 0x{cmd:04X}")
        return None


class EIPUDPProtocol(asyncio.DatagramProtocol):
    """
    Protocole UDP : reçoit les paquets I/O O->T (PLC -> adaptateur) en Class 1.

    Le PLC envoie deux formats selon la taille de connexion négociée :

    Format COMPACT (O->T size = 3B, notre cas avec 1B d'I/O) :
      [16B] CPF header (item_count + addr_item + data_item_header)
      [2B]  CIP Sequence Count
      [1B]  Output byte (Assembly Instance 100)

    Format AVEC Run/Idle Header (O->T size >= 7B, vrai PointIO Rockwell) :
      [16B] CPF header
      [2B]  CIP Sequence Count
      [4B]  Run/Idle Header (bit0=1 -> PLC en RUN, 0 -> IDLE)
      [1B]  Output byte
      [N]   padding éventuel

    En mode IDLE (run_idle bit0=0), les sorties restent à 0 (CIP Vol.1 §3-6.1).
    """

    def connection_made(self, transport):
        state.udp_transport = transport
        log.info(f"UDP I/O en ecoute sur :{UDP_PORT}")

    def datagram_received(self, data: bytes, addr: tuple):
        # Minimum absolu : CPF header 16B + cip_seq 2B + output 1B = 19B
        if len(data) < 19:
            log.warning(f"Paquet O->T trop court: {len(data)}B")
            return

        item_count = struct.unpack_from("<H", data, 0)[0]
        if item_count < 2:
            return

        # Addr item à offset 2 : type(2) + len(2) + conn_id(4) + encap_seq(4)
        addr_len         = struct.unpack_from("<H", data, 4)[0]   # = 8
        data_item_offset = 6 + addr_len                           # = 14
        data_item_len    = struct.unpack_from("<H", data, data_item_offset + 2)[0]
        cip_data_offset  = data_item_offset + 4                   # = 18

        if len(data) < cip_data_offset + 3:  # minimum : cip_seq(2) + output(1)
            log.warning(f"Paquet O->T data trop court: data_item_len={data_item_len}")
            return

        cip_seq = struct.unpack_from("<H", data, cip_data_offset)[0]

        if data_item_len >= 7:
            # Format avec Run/Idle Header : cip_seq(2) + run_idle(4) + output(1)
            run_idle    = struct.unpack_from("<I", data, cip_data_offset + 2)[0]
            output_byte = data[cip_data_offset + 6] & 0x1F
            is_run      = bool(run_idle & 0x1)
            if not is_run:
                output_byte = 0x00  # IDLE : sorties à zéro (CIP Vol.1 §3-6.1)
            log.debug(f"O->T seq={cip_seq} run={'RUN' if is_run else 'IDLE'} "
                      f"outputs=0b{output_byte:05b} depuis {addr}")
        else:
            # Format compact : cip_seq(2) + output(1), sans Run/Idle Header
            output_byte = data[cip_data_offset + 2] & 0x1F
            log.debug(f"O->T seq={cip_seq} outputs=0b{output_byte:05b} depuis {addr}")

        state.output_byte  = output_byte
        state.last_ot_time = time.monotonic()
        state.plc_addr     = addr
        set_outputs(output_byte)

    def error_received(self, exc):
        log.error(f"UDP error: {exc}")


# ---------------------------------------------------------------------------
# Tâches asyncio de fond
# ---------------------------------------------------------------------------
async def task_send_inputs():
    """
    Envoie périodiquement les entrées (T->O) au PLC via UDP.

    Format du paquet CPF (CIP Vol.2 §2-6.3) :
      [2]  Item Count = 2
      [2]  Addr Item Type = 0x8002 (Sequenced Address Item)
      [2]  Addr Item Length = 8
      [4]  Connection ID T->O
      [4]  Encap Sequence (32-bit, incrémenté à chaque envoi)
      [2]  Data Item Type = 0x00B1 (Connected Data Item)
      [2]  Data Item Length = 3
      [2]  CIP Sequence Count (16-bit, incrémenté à chaque envoi)
      [1]  Input byte (Assembly Instance 101)
    """
    while True:
        rpi = max(0.05, min(state.t_api / 1_000_000, 1.0))
        await asyncio.sleep(rpi)

        if not state.connected or state.udp_transport is None or state.plc_addr is None:
            continue

        state.input_byte = get_inputs()

        state.cip_seq_count = (state.cip_seq_count + 1) & 0xFFFF
        state.encap_seq     = (state.encap_seq     + 1) & 0xFFFFFFFF

        cip_data  = struct.pack("<H", state.cip_seq_count) + bytes([state.input_byte & 0x1F])
        addr_item = struct.pack("<HHII",
            0x8002,                  # Sequenced Address Item
            8,                       # longueur de l'item addr
            state.connection_id_to,  # Connection ID T->O
            state.encap_seq
        )
        data_item = struct.pack("<HH", 0x00B1, len(cip_data)) + cip_data
        packet    = struct.pack("<H", 2) + addr_item + data_item  # item_count=2

        state.udp_transport.sendto(packet, state.plc_addr)
        log.debug(
            f"T->O encap={state.encap_seq} cip_seq={state.cip_seq_count} "
            f"inputs=0b{state.input_byte:05b} -> {state.plc_addr}"
        )


async def task_watchdog():
    """Remet les sorties à zéro si aucun paquet O->T n'est reçu pendant WATCHDOG_S secondes."""
    while True:
        await asyncio.sleep(0.1)
        if not state.connected:
            continue
        if time.monotonic() - state.last_ot_time > WATCHDOG_S and state.output_byte != 0:
            log.warning("Watchdog — sorties a zero")
            state.output_byte = 0x00
            set_outputs(0x00)


async def task_status_log():
    """Logue l'état de l'adaptateur toutes les 10 secondes."""
    while True:
        await asyncio.sleep(10)
        log.info(
            f"Status | connected={state.connected} "
            f"out=0b{state.output_byte:05b} "
            f"in=0b{state.input_byte:05b} "
            f"sim={SIMULATION}"
        )


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
async def main():
    loop       = asyncio.get_running_loop()
    tcp_server = await loop.create_server(EIPTCPProtocol, "0.0.0.0", TCP_PORT)
    log.info(f"TCP EtherNet/IP en ecoute sur :{TCP_PORT}")
    await loop.create_datagram_endpoint(EIPUDPProtocol, local_addr=("0.0.0.0", UDP_PORT))
    async with tcp_server:
        await asyncio.gather(
            tcp_server.serve_forever(),
            task_send_inputs(),
            task_watchdog(),
            task_status_log(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arret demande")
        set_outputs(0x00)
