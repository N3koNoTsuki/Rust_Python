import asyncio
import struct
import time
import eip
import cpf


class EIPUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, conn_state: dict) -> None:
        self.conn_state = conn_state
        self.last_ot_time = time.monotonic()
        self.encap_seq = 0
        self.plc_addr = None
        self.transport = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        eip_header = eip.parse_eip_header(data)
        if eip_header is None:
            return
        items = cpf.parse_cpf(data[30:])
        connected_data = items[1][1]
        run_idle_header = struct.unpack('<I', connected_data[0:4])[0]
        output_byte = connected_data[4]
        bit0 = run_idle_header & 0x01
        outputs = output_byte & 0x1F if bit0 else 0x00
        print(f"[IO] O→T: run={bit0}, outputs=0x{outputs:02X}")
        self.last_ot_time = time.monotonic()
        self.plc_addr = addr

async def task_send_inputs(protocol, conn_state):
    was_active = False
    while True:
        if not conn_state.get('active', False) or 'plc_ip' not in conn_state:
            was_active = False
            await asyncio.sleep(0.1)
            continue

        if not was_active:
            protocol.last_ot_time = time.monotonic()
            was_active = True

        inputs = 0x00  # TODO: read actual inputs

        cpf_payload = cpf.build_cpf([
            (cpf.CPF_CONNECTED_ADDR, struct.pack('<II', conn_state.get('t_o_conn_id', 0), protocol.encap_seq)),
            (cpf.CPF_CONNECTED_DATA, bytes([inputs]))
        ])
        payload = b'\x00\x00\x00\x00' + b'\x00\x00' + cpf_payload
        packet = eip.build_eip_header(eip.CMD_SEND_UNIT_DATA, len(payload), 0) + payload
        plc_addr = protocol.plc_addr or (conn_state['plc_ip'], 2222)
        protocol.transport.sendto(packet, plc_addr)
        protocol.encap_seq = (protocol.encap_seq + 1) % (2**32)
        await asyncio.sleep(conn_state.get('rpi_t_o', 20000) / 1_000_000)

async def task_watchdog(protocol, conn_state):
    while True:
        if conn_state.get('active', False) and (time.monotonic() - protocol.last_ot_time) > 0.5:
            print(f"[WATCHDOG] No O→T data received for 0.5 seconds, closing connection")
            conn_state['active'] = False
            protocol.plc_addr = None
        await asyncio.sleep(0.1)

