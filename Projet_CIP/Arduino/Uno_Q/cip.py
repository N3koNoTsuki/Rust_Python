"""
cip.py — CIP (Common Industrial Protocol) services

Implémente les services CIP utilisés par l'adaptateur :
  - Identity Object      (class 0x01) : GetAttributeAll, GetAttributeSingle
  - TCP/IP Object        (class 0xC0) : GetAttributeSingle (attr 1-3, 5, 0x12)
  - Port Object          (class 0xF4) : GetAttributeSingle (attr 7-8)
  - Connection Manager   (class 0x06) : ForwardOpen (0x54), ForwardClose (0x4E)

Format des réponses CIP :
  Succès : [service|0x80, 0x00, 0x00, 0x00] + data
  Erreur : [service|0x80, 0x00, error_code, 0x00]
    0x08 = Service Not Supported
    0x14 = Attribute Not Supported
"""

from socket import AF_INET
from dataclasses import dataclass
import struct
import logging

log = logging.getLogger("cip")


VENDOR_ID = 0xFFFF
DEVICE_TYPE = 12
PRODUCT_CODE = 1
REVISION = (1,1)
SERIAL_NUMBER = 0x00000001
PRODUCT_NAME = "Arduino Uno Q"

@dataclass
class ConnectionParameters :
    priority_time_tick  : int
    timeout_ticks       : int
    o_t_conn_id         : int    
    t_o_conn_id         : int    
    conn_serial         : int
    vendor_id           : int
    originator_serial   : int
    timeout_multiplier  : int
    reserved            : bytes
    rpi_o_t             : int    
    o_t_conn_params     : int
    rpi_t_o             : int
    t_o_conn_params     : int
    transport_type      : int   

def build_list_identity_payload() -> bytes:
    """Construit le payload CPF complet pour répondre à une commande ListIdentity.

    Retourne un item de type 0x000C contenant le sockaddr (16B) suivi
    des champs identité CIP (vendor, device type, product code, revision,
    status, serial, product name, state).
    """
    payload = bytearray()
    payload += 0x0001.to_bytes(2, 'little')                             # [0]item count
    payload += 0x000C.to_bytes(2, 'little')                             # [1] item type


    payload_secondary = bytearray()
    payload_secondary += 0x0001.to_bytes(2, 'little')                   # [3] protocol version
    payload_secondary += AF_INET.to_bytes(2, 'little')                  # [4] address family
    payload_secondary += 0xAF12.to_bytes(2, 'big')                      # [5] port
    payload_secondary += 0x00000000.to_bytes(4, 'big')                  # [6] IP address (0.0.0.0)
    payload_secondary += 0x0000000000000000.to_bytes(8, 'little')       # [7] padding
    payload_secondary += VENDOR_ID.to_bytes(2, 'little')                # [8] Vendor ID
    payload_secondary += DEVICE_TYPE.to_bytes(2, 'little')              # [9] Device Type
    payload_secondary += PRODUCT_CODE.to_bytes(2, 'little')             # [10] Product Code
    payload_secondary += REVISION[0].to_bytes(1, 'little')              # [11] Revision Major
    payload_secondary += REVISION[1].to_bytes(1, 'little')              # [12] Revision Minor
    payload_secondary += 0x0000.to_bytes(2, 'little')                   # [13] Status
    payload_secondary += SERIAL_NUMBER.to_bytes(4, 'little')            # [14] Serial Number
    payload_secondary += len(PRODUCT_NAME).to_bytes(1, 'little')        # [15] Product Length
    payload_secondary += PRODUCT_NAME.encode('ascii')                   # [16] Product Name
    payload_secondary += 0xFF.to_bytes(1, 'little')                     # [17] state

    item_length = len(payload_secondary)
    payload += item_length.to_bytes(2, 'little')                        # [2] item length
    payload += payload_secondary
    
    return bytes(payload)

def handle_get_attribute_all_identity() -> bytes:
    """Retourne les attributs de l'Identity Object (service 0x01 — GetAttributeAll).

    Champs : vendor_id, device_type, product_code, revision (2x1B),
             status, serial_number, product_name (short string), state.
    """
    payload = bytearray()
    payload += VENDOR_ID.to_bytes(2, 'little')              # Vendor ID
    payload += DEVICE_TYPE.to_bytes(2, 'little')            # Device Type
    payload += PRODUCT_CODE.to_bytes(2, 'little')           # Product Code
    payload += REVISION[0].to_bytes(1, 'little')            # Revision Major
    payload += REVISION[1].to_bytes(1, 'little')            # Revision Minor
    payload += 0x0000.to_bytes(2, 'little')                 # Status
    payload += SERIAL_NUMBER.to_bytes(4, 'little')          # Serial Number
    payload += len(PRODUCT_NAME).to_bytes(1, 'little')      # Product Length
    payload += PRODUCT_NAME.encode('ascii')                 # Product Name
    payload += 0xFF.to_bytes(1, 'little')                   # state
    return bytes(payload)

def handle_get_attribute_single(class_id: int, instance: int, atribute: int) -> bytes:
    """Traite une requête GetAttributeSingle (service 0x0E).

    Supporte :
      class 0x01 (Identity)  : attr 1-8
      class 0xC0 (TCP/IP)    : attr 1-3, 5, 0x12
      class 0xF4 (Port)      : attr 7-8

    Retourne [0x8E, 0x00, 0x00, 0x00] + data en cas de succès,
    ou [0x8E, 0x00, 0x14, 0x00] (Attribute Not Supported) sinon.
    """
    match class_id :
        case 0x01 : # Identity Object
            match atribute :
                case 0x01 : # Vendor ID
                    data = VENDOR_ID.to_bytes(2, 'little')
                case 0x02 : # Device Type
                    data = DEVICE_TYPE.to_bytes(2, 'little')
                case 0x03 : # Product Code
                    data = PRODUCT_CODE.to_bytes(2, 'little')
                case 0x04 : # Revision
                    data = REVISION[0].to_bytes(1, 'little') + REVISION[1].to_bytes(1, 'little')
                case 0x05 : # Status
                    data = 0x0000.to_bytes(2, 'little')
                case 0x06 : # Serial Number
                    data = SERIAL_NUMBER.to_bytes(4, 'little')      
                case 0x07 : # Product Name
                    data = len(PRODUCT_NAME).to_bytes(1, 'little') + PRODUCT_NAME.encode('ascii')
                case 0x08 : # State
                    data = 0xFF.to_bytes(1, 'little')
                case _ :
                    return bytes([0x8E, 0x00, 0x14, 0x00])
        case 0xC0 : # TCP/IP Object
            match atribute :
                case 0x01 : # Interface Count
                    data = 0x00000001.to_bytes(4, 'little')
                case 0x02 : # Configuration Capabilities
                    data = 0x00000010.to_bytes(4, 'little')
                case 0x03 : # Configuration Control
                    data = 0x00000000.to_bytes(4, 'little')
                case 0x05 : # Interface Configuration
                    data = 0x00000000000000000000.to_bytes(20, 'little') + b'\x00'
                case 0x12 : # Encapsulation Inactivity Timeout
                    data = 0x0000.to_bytes(2, 'little')
                case _ :
                    return bytes([0x8E, 0x00, 0x14, 0x00])

        case 0xF4 : # Port Object
            match atribute :
                case 0x07 : # Port Type
                    data = 0x0004.to_bytes(2, 'little')
                case 0x08 : # Port Number
                    data = 0x0001.to_bytes(2, 'little')
                case _ :
                    return bytes([0x8E, 0x00, 0x14, 0x00])
        case _ :
            return bytes([0x8E, 0x00, 0x14, 0x00])
    return bytes([0x8E, 0x00, 0x00, 0x00]) + data

def handle_forward_open(payload: bytes, conn_state: dict) -> bytes:
    """Traite une requête ForwardOpen (service 0x54) et établit la connexion I/O.

    Parse les paramètres de connexion (IDs, RPI, tailles) depuis le payload
    et met à jour conn_state. Active la connexion (active=True).

    conn_state mis à jour :
      o_t_conn_id, t_o_conn_id, rpi_o_t, rpi_t_o,
      conn_serial, vendor_id, originator_serial, active

    Retourne la réponse ForwardOpen Success (0xD4) avec les IDs et RPI confirmés.
    """

    conn_paarameters = ConnectionParameters(*struct.unpack('<BBIIHHIB3sIHIHB', payload[:35]))
    conn_state['o_t_conn_id'] = conn_paarameters.o_t_conn_id if conn_paarameters.o_t_conn_id != 0 else 0xDEAD0001
    conn_state['t_o_conn_id'] = conn_paarameters.t_o_conn_id
    conn_state['rpi_o_t'] = conn_paarameters.rpi_o_t
    conn_state['rpi_t_o'] = conn_paarameters.rpi_t_o
    conn_state['conn_serial'] = conn_paarameters.conn_serial
    conn_state['vendor_id'] = conn_paarameters.vendor_id
    conn_state['originator_serial'] = conn_paarameters.originator_serial
    conn_state['active'] = True
    log.info(
        f"ForwardOpen: O->T ID=0x{conn_state['o_t_conn_id']:X}, "
        f"T->O ID=0x{conn_state['t_o_conn_id']:X}, "
        f"RPI O->T={conn_paarameters.rpi_o_t}us, "
        f"RPI T->O={conn_paarameters.rpi_t_o}us"
    )
    log.debug(f"ForwardOpen params: {conn_paarameters}")
    return bytes([0xD4, 0x00, 0x00, 0x00]) + struct.pack('<IIHHIII',
                                                         conn_state['o_t_conn_id'],
                                                         conn_paarameters.t_o_conn_id, 
                                                         conn_paarameters.conn_serial, 
                                                         conn_paarameters.vendor_id, 
                                                         conn_paarameters.originator_serial, 
                                                         conn_paarameters.rpi_o_t, 
                                                         conn_paarameters.rpi_t_o) + b'\x00\x00'

def handle_forward_close(payload: bytes, conn_state: dict) -> bytes:
    """Traite une requête ForwardClose (service 0x4E) et ferme la connexion I/O.

    Remet conn_state['active'] à False et retourne la réponse
    ForwardClose Success (0xCE) avec conn_serial, vendor_id et originator_serial.
    """
    
    conn_state['active'] = False
    log.info("ForwardClose: Connection reset by PLC")
    return bytes([0xCE, 0x00, 0x00, 0x00]) + struct.pack('<HHI',
    conn_state.get('conn_serial', 0),
    conn_state.get('vendor_id', 0),
    conn_state.get('originator_serial', 0)) + b'\x00\x00'
