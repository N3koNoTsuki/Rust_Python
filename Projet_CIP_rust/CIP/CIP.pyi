from typing import List, Tuple

class EIPHeader:
    command: int
    length: int
    session_handle: int
    status: int
    sender_context: bytes
    options: int

class ConnectionParameters:
    priority_time_tick: int
    timeout_ticks: int
    o_t_conn_id: int
    t_o_conn_id: int
    conn_serial: int
    vendor_id: int
    originator_serial: int
    timeout_multiplier: int
    reserved: bytes
    rpi_o_t: int
    o_t_conn_params: int
    rpi_t_o: int
    t_o_conn_params: int
    transport_type: int

class ConnState:
    o_t_conn_id: int
    t_o_conn_id: int
    rpi_o_t: int
    rpi_t_o: int
    conn_serial: int
    vendor_id: int
    originator_serial: int
    active: bool

def parse_cpf(data: bytes) -> List[Tuple[int, bytes]]: ...
def build_cpf(items: List[Tuple[int, bytes]]) -> bytes: ...

def parse_eip_header(data: bytes) -> EIPHeader: ...
def build_eip_header(
    command: int,
    length: int,
    session_handle: int,
    status: int,
    sender_context: bytes,
    options: int,
) -> bytes: ...
def handle_register_session(header: EIPHeader, data: bytes) -> bytes: ...

def build_list_identity_payload() -> bytes: ...
def handle_get_attribute_all_identity() -> bytes: ...
def handle_get_attribute_single(class_id: int, instance: int, attribute: int) -> bytes: ...
def handle_forward_open(payload: bytes, conn_state: ConnState) -> bytes: ...
def handle_forward_close(payload: bytes, conn_state: ConnState) -> bytes: ...
