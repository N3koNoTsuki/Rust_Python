from dataclasses import dataclass
import struct




CMD_REGISTER_SESSION = 0x0065
CMD_LIST_IDENTITY = 0x0063
CMD_SEND_RR_DATA = 0x006F
CMD_SEND_UNIT_DATA = 0x0070

@dataclass
class EIPHeader:
    command         : int
    length          : int   #Taille du payload en octets 
    session_handle  : int
    status          : int
    sender_context  : bytes
    options         : int

def parse_eip_header(data: bytes) -> EIPHeader:

    if len(data) < 24:
        return None
    else :
        return EIPHeader(*struct.unpack('<HHII8sI', data[:24]))


def build_eip_header(command, length, 
                     session_handle, 
                     status = 0, 
                     sender_context = b'\x00' * 8, 
                     options = 0) -> bytes :
    
    return struct.pack('<HHII8sI',
                       command,
                       length,
                       session_handle,
                       status,
                       sender_context,
                       options)

def handle_register_session(header: EIPHeader, data: bytes) -> bytes:
    payload = struct.pack('<HH', 1, 0) # version 1, options 0
    header.session_handle = 0x12345678
    rep_header = build_eip_header(CMD_REGISTER_SESSION, len(payload), header.session_handle)
    return rep_header + payload