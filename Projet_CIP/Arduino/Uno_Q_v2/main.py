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
import io_server as io
import eip
import cpf
import cip
import logging
import argparse
from arduino.app_utils import Bridge, App



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
    """Configure le niveau de logging global avec timestamp ms.

    Args:
        level : niveau sous forme de string ('INFO', 'DEBUG', etc.)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s.%(msecs)03d [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S"
    )

log = logging.getLogger("main")

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Coroutine de traitement d'une connexion TCP cliente.

    Boucle sur reader.read(4096) jusqu'à déconnexion.
    Dispatche chaque paquet EIP reçu vers le bon handler :
      0x0065 RegisterSession, 0x006F SendRRData, 0x0070 SendUnitData.
    Dans SendRRData, dispatche ensuite sur le service CIP :
      0x0E GetAttributeSingle, 0x01 GetAttributeAll,
      0x54 ForwardOpen, 0x4E ForwardClose.
    """
    (ip_str, port) = writer.get_extra_info('peername')
    log.info(f"TCP Connection from: {ip_str}:{port}")
    while True:
        data = await reader.read(4096)
        if data == b'':
            break
        else :
            log.debug(f"TCP RX ({len(data)}B): {data.hex()}")
            header = eip.parse_eip_header(data)
            if header is None:
                continue
            
            log.debug(f"EIP Header: CMD=0x{header.command:04X}, Len={header.length}, Session=0x{header.session_handle:08X}, Ctx={header.sender_context.hex()}")
            eip_response = b''

            match header.command:
                case eip.CMD_REGISTER_SESSION:
                    log.info("EIP Command: Register Session")
                    eip_response = eip.handle_register_session(header, data)

                case eip.CMD_LIST_IDENTITY:
                    log.info("EIP Command: List Identity")
                    # Pas d'implémentation dans ce scope, le PLC ne semble pas l'utiliser.

                case eip.CMD_SEND_RR_DATA:
                    log.info("EIP Command: Send RR Data")
                    try:
                        items           = cpf.parse_cpf(data[30:])
                        cip_data        = items[1][1]
                        service         = cip_data[0]
                        path_size       = cip_data[1]
                        path            = cip_data[2:2+path_size*2]
                        extra           = cip_data[2+path_size*2:]
                        class_id        = path[1]
                        instance_id     = path[3]
                        attribute_id    = path[5] if len(path) >= 6 else 0
                        log.debug(f"  -> CIP Service=0x{service:02X}, Path={path.hex()}, Attr={attribute_id if attribute_id else 'N/A'}")

                        match service:
                            case 0x0E:
                                cip_response = cip.handle_get_attribute_single(class_id, instance_id, attribute_id)
                            case 0x01:
                                cip_response = cip.handle_get_attribute_all_identity()
                            case 0x54:
                                conn_state['plc_ip'] = ip_str
                                cip_response = cip.handle_forward_open(extra, conn_state)
                            case 0x4E:
                                cip_response = cip.handle_forward_close(extra, conn_state)
                            case _:
                                log.warning(f"Unknown CIP service 0x{service:02X}")
                                cip_response = bytes([0x8E, 0x00, 0x0E, 0x00]) # Service not supported

                        if service == 0x54:
                            sock_ot = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8
                            sock_to = b'\x00\x02\x08\xae\x00\x00\x00\x00' + b'\x00'*8
                            cpf_response = cpf.build_cpf([
                                (0x0000, b''),
                                (0x00B2, cip_response),
                                (0x8000, sock_ot),
                                (0x8001, sock_to)
                            ])
                        else:
                            cpf_response = cpf.build_cpf([(0x0000, b''), (0x00B2, cip_response)])

                        payload_response = b'\x00\x00\x00\x00' + b'\x00\x00' + cpf_response
                        eip_response = eip.build_eip_header(
                            command=eip.CMD_SEND_RR_DATA,
                            length=len(payload_response),
                            session_handle=header.session_handle,
                            sender_context=header.sender_context
                        ) + payload_response

                    except Exception as e:
                        log.error(f"SendRRData handler error: {e}", exc_info=True)

                case eip.CMD_SEND_UNIT_DATA:
                    log.info("EIP Command: Send Unit Data (ignored)")

                case _:
                    log.warning(f"Unknown EIP command received: 0x{header.command:04X}")
            
            if eip_response:
                log.debug(f"TCP TX ({len(eip_response)}B): {eip_response.hex()}")
                writer.write(eip_response)
                await writer.drain()
    
    log.info(f"TCP Connection closed for {ip_str}:{port}")


async def main() -> None:
    """Lance le serveur TCP EIP (44818), le serveur UDP I/O (2222)
    et démarre les tâches asyncio task_send_inputs et task_watchdog.
    """
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
