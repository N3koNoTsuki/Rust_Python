"""
main.py — Point d'entrée de l'adaptateur EtherNet/IP CIP

Lance deux serveurs asyncio :
  - TCP port 44818 : session EIP, échanges CIP non-connectés
      RegisterSession, GetAttributeSingle/All, ForwardOpen, ForwardClose
  - UDP port 2222  : échange I/O cyclique (O→T / T→O)

Usage :
  python main.py           # niveau INFO
  python main.py -v        # niveau DEBUG (trames hex complètes)
"""

import asyncio
import threading
import time
import struct
import CIP
import io_server as io
import logging
import argparse
from arduino.app_utils import Bridge, App

CMD_REGISTER_SESSION = 0x0065
CMD_LIST_IDENTITY    = 0x0063
CMD_SEND_RR_DATA     = 0x006F
CMD_SEND_UNIT_DATA   = 0x0070


def linux_started():
    return True


conn_state = {'active': False, 'input_data': 0, 'output_data': 0}

def receive_cip_data(data):
    conn_state['input_data'] = int(data) & 0xFF
    log.info(f"Received CIP data from Arduino: {conn_state['input_data']:#04x}")

def send_cip_data() -> int:
    val = conn_state['output_data'] & 0xFF
    log.info(f"send_cip_data called, returning: {val:#04x}")
    return val


Bridge.provide("linux_started", linux_started)
Bridge.provide("receive_cip_data", receive_cip_data)
Bridge.provide("send_cip_data", send_cip_data)

def setup_logging(level: str) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S"
    )

log = logging.getLogger("main")

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    (ip_str, port) = writer.get_extra_info('peername')
    log.info(f"TCP Connection from: {ip_str}:{port}")
    while True:
        data = await reader.read(4096)
        if data == b'':
            break
        else:
            log.debug(f"TCP RX ({len(data)}B): {data.hex()}")
            if len(data) < 24:
                continue
            header = CIP.parse_eip_header(data)

            log.debug(f"EIP Header: CMD=0x{header.command:04X}, Len={header.length}, Session=0x{header.session_handle:08X}, Ctx={bytes(header.sender_context).hex()}")
            eip_response = b''

            match header.command:
                case 0x0065:  # RegisterSession
                    log.info("EIP Command: Register Session")
                    eip_response = bytes(CIP.handle_register_session(header, data))
                    log.info("Registering new session, handle=0x12345678")

                case 0x0063:  # ListIdentity
                    log.info("EIP Command: List Identity")

                case 0x006F:  # SendRRData
                    log.info("EIP Command: Send RR Data")
                    try:
                        items        = CIP.parse_cpf(data[30:])
                        cip_data     = items[1][1]
                        service      = cip_data[0]
                        path_size    = cip_data[1]
                        path         = cip_data[2:2+path_size*2]
                        extra        = cip_data[2+path_size*2:]
                        class_id     = path[1]
                        instance_id  = path[3]
                        attribute_id = path[5] if len(path) >= 6 else 0
                        log.debug(f"  -> CIP Service=0x{service:02X}, Path={path.hex()}, Attr={attribute_id if attribute_id else 'N/A'}")

                        match service:
                            case 0x0E:
                                cip_response = bytes(CIP.handle_get_attribute_single(class_id, instance_id, attribute_id))
                            case 0x01:
                                cip_response = bytes(CIP.handle_get_attribute_all_identity())
                            case 0x54:  # ForwardOpen
                                conn_state['plc_ip'] = ip_str
                                p = struct.unpack('<BBIIHHIB3sIHIHB', extra[:35])
                                o_t_conn_id       = p[2] if p[2] != 0 else 0xDEAD0001
                                t_o_conn_id       = p[3]
                                conn_serial       = p[4]
                                vendor_id         = p[5]
                                originator_serial = p[6]
                                rpi_o_t           = p[9]
                                rpi_t_o           = p[11]
                                conn_state.update({
                                    'o_t_conn_id':       o_t_conn_id,
                                    't_o_conn_id':       t_o_conn_id,
                                    'rpi_o_t':           rpi_o_t,
                                    'rpi_t_o':           rpi_t_o,
                                    'conn_serial':       conn_serial,
                                    'vendor_id':         vendor_id,
                                    'originator_serial': originator_serial,
                                    'active':            True,
                                })
                                log.info(
                                    f"ForwardOpen: O->T ID=0x{o_t_conn_id:X}, T->O ID=0x{t_o_conn_id:X}, "
                                    f"RPI O->T={rpi_o_t}us, RPI T->O={rpi_t_o}us"
                                )
                                cip_response = (bytes([0xD4, 0x00, 0x00, 0x00])
                                                + struct.pack('<IIHHIII', o_t_conn_id, t_o_conn_id,
                                                             conn_serial, vendor_id, originator_serial,
                                                             rpi_o_t, rpi_t_o)
                                                + b'\x00\x00')
                            case 0x4E:  # ForwardClose
                                conn_state['active'] = False
                                log.info("ForwardClose: Connection reset by PLC")
                                cip_response = (bytes([0xCE, 0x00, 0x00, 0x00])
                                                + struct.pack('<HHI',
                                                             conn_state.get('conn_serial', 0),
                                                             conn_state.get('vendor_id', 0),
                                                             conn_state.get('originator_serial', 0))
                                                + b'\x00\x00')
                            case _:
                                log.warning(f"Unknown CIP service 0x{service:02X}")
                                cip_response = bytes([0x8E, 0x00, 0x0E, 0x00])

                        if service == 0x54:
                            sock_ot = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8
                            sock_to = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8
                            cpf_response = bytes(CIP.build_cpf([
                                (0x0000, b''),
                                (0x00B2, cip_response),
                                (0x8000, sock_ot),
                                (0x8001, sock_to)
                            ]))
                        else:
                            cpf_response = bytes(CIP.build_cpf([(0x0000, b''), (0x00B2, cip_response)]))

                        payload_response = b'\x00\x00\x00\x00' + b'\x00\x00' + cpf_response
                        eip_response = bytes(CIP.build_eip_header(
                            CMD_SEND_RR_DATA,
                            len(payload_response),
                            header.session_handle,
                            0,
                            bytes(header.sender_context),
                            0
                        )) + payload_response

                    except Exception as e:
                        log.error(f"SendRRData handler error: {e}", exc_info=True)

                case 0x0070:  # SendUnitData
                    log.info("EIP Command: Send Unit Data (ignored)")

                case _:
                    log.warning(f"Unknown EIP command received: 0x{header.command:04X}")

            if eip_response:
                log.debug(f"TCP TX ({len(eip_response)}B): {eip_response.hex()}")
                writer.write(eip_response)
                await writer.drain()

    log.info(f"TCP Connection closed for {ip_str}:{port}")


async def main() -> None:
    server = await asyncio.start_server(handle_client, '0.0.0.0', 44818)
    log.info("TCP server started on port 44818")

    udp_handler = io.start_udp_handler(conn_state)
    log.info("UDP server started on port 2222")

    asyncio.create_task(io.task_send_inputs(udp_handler, conn_state))
    asyncio.create_task(io.task_watchdog(udp_handler, conn_state))

    await server.serve_forever()

def loop():
    time.sleep(0.1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EtherNet/IP CIP Adapter for Arduino")
    parser.add_argument(
        '-v', '--verbose',
        action='store_const',
        dest='loglevel',
        const='DEBUG',
        default='DEBUG',
        help='Enable verbose logging (DEBUG level)'
    )
    args = parser.parse_args()
    setup_logging(args.loglevel)
    def _run_main():
        try:
            asyncio.run(main())
        except Exception as e:
            log.critical(f"asyncio main crashed: {e}", exc_info=True)
    threading.Thread(target=_run_main, daemon=True).start()
    App.run(user_loop=loop)
