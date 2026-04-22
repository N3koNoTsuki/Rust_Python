"""
io_server.py — Serveur UDP I/O EtherNet/IP (port 2222)

Gère l'échange cyclique de données I/O entre le PLC et l'adaptateur
une fois la connexion établie via ForwardOpen (TCP).

Direction O→T (PLC → Arduino) :
  Paquet UDP = CPF brut (pas de header EIP)
  Item 0 : Connected Address (0x8002) — 8B : conn_id (4B) + seq (4B)
  Item 1 : Connected I/O Data (0x00B1) — 3B : CIP_seq (2B) + output_byte (1B)

Direction T→O (Arduino → PLC) :
  Même format CPF, t_o_conn_id comme conn_id,
  encap_seq (32 bits) dans l'adresse, cip_seq (16 bits) dans les données.

Tâches asyncio :
  task_send_inputs  — envoie les T→O à la fréquence rpi_t_o
  task_watchdog     — coupe la connexion si aucun O→T reçu depuis 5s
"""

import asyncio
import struct
import socket as _socket
import threading
import time
import cpf
import logging

log = logging.getLogger("io_server")


class EIPUDPHandler:
    """Gestion UDP via socket bloquant (thread dédié pour la réception).

    Utilise un socket Python classique plutôt que asyncio.DatagramProtocol
    pour éviter les problèmes de réception UDP dans un thread non-principal.
    """

    def __init__(self, conn_state: dict) -> None:
        self.conn_state = conn_state
        self.last_ot_time = time.monotonic()
        self.encap_seq = 0
        self.cip_seq = 0
        self.plc_addr = None
        self.sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        self.sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEPORT, 1)
        try:
            self.sock.bind(('0.0.0.0', 2222))
        except OSError as e:
            log.error(f"UDP bind FAILED on port 2222: {e}")
            raise
        self.sock.settimeout(1.0)
        log.info(f"UDP socket bound to {self.sock.getsockname()}")

    def send(self, packet: bytes, addr: tuple) -> None:
        try:
            self.sock.sendto(packet, addr)
        except Exception as e:
            log.error(f"UDP send error to {addr}: {e}")

    def recv_loop(self) -> None:
        """Boucle bloquante de réception O→T — à lancer dans un thread dédié."""
        log.info("UDP recv thread started")
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
            except _socket.timeout:
                continue
            except Exception as e:
                log.error(f"UDP recv error: {e}")
                continue

            log.info(f"UDP RX ({len(data)}B) from {addr}")
            log.debug(f"UDP RX hex: {data.hex()}")

            items = cpf.parse_cpf(data)
            if len(items) < 2:
                log.warning("Less than 2 CPF items in UDP packet, ignoring.")
                continue

            item2_id, connected_data = items[1]
            if item2_id != cpf.CPF_IO_DATA:
                log.warning(f"UDP Item 1 ID is 0x{item2_id:04X}, expected 0x{cpf.CPF_IO_DATA:04X}, ignoring.")
                continue

            if len(connected_data) < 3:
                log.warning(f"UDP connected data too short ({len(connected_data)} bytes), ignoring.")
                continue

            cip_seq = struct.unpack('<H', connected_data[0:2])[0]
            output_byte = connected_data[2]
            log.debug(f"O->T: CIP Seq={cip_seq}, Output=0x{output_byte:02X}")
            self.last_ot_time = time.monotonic()
            self.plc_addr = addr
            self.conn_state['output_data'] = output_byte


def start_udp_handler(conn_state: dict) -> EIPUDPHandler:
    """Crée le handler UDP et démarre le thread de réception."""
    handler = EIPUDPHandler(conn_state)
    threading.Thread(target=handler.recv_loop, daemon=True, name="udp-recv").start()
    return handler


async def task_send_inputs(handler: EIPUDPHandler, conn_state: dict):
    """Coroutine d'envoi cyclique des paquets T→O vers le PLC.

    Tourne en permanence. Attend que la connexion soit active (conn_state['active'])
    et que plc_ip soit connu avant d'envoyer.
    Cadence : conn_state['rpi_t_o'] µs (défaut 20 000 µs = 20 ms).
    Incrémente encap_seq (32 bits) et cip_seq (16 bits) à chaque paquet.
    """
    was_active = False
    while True:
        if not conn_state.get('active', False) or 'plc_ip' not in conn_state:
            was_active = False
            await asyncio.sleep(0.1)
            continue

        if not was_active:
            handler.last_ot_time = time.monotonic()
            was_active = True

        try:
            inputs = int(conn_state.get('input_data', 0)) & 0xFF
        except (TypeError, ValueError) as e:
            log.error(f"input_data invalid ({conn_state.get('input_data')!r}): {e}")
            inputs = 0

        packet = cpf.build_cpf([
            (cpf.CPF_CONNECTED_ADDR, struct.pack('<II', conn_state.get('t_o_conn_id', 0), handler.encap_seq)),
            (cpf.CPF_IO_DATA, struct.pack('<H', handler.cip_seq) + bytes([inputs]))
        ])

        plc_addr = handler.plc_addr or (conn_state['plc_ip'], 2222)
        log.info(f"T->O: CIP Seq={handler.cip_seq}, Inputs=0x{inputs:02X}")
        log.debug(f"UDP TX ({len(packet)}B to {plc_addr}): {packet.hex()}")
        handler.cip_seq = (handler.cip_seq + 1) % (2**16)
        handler.send(packet, plc_addr)
        handler.encap_seq = (handler.encap_seq + 1) % (2**32)
        await asyncio.sleep(conn_state.get('rpi_t_o', 20000) / 1_000_000)


async def task_watchdog(handler: EIPUDPHandler, conn_state: dict):
    """Coroutine de surveillance de la connexion I/O.

    Vérifie toutes les 100 ms que des paquets O→T ont été reçus récemment.
    Si aucun paquet reçu depuis 5 secondes, ferme la connexion
    (conn_state['active'] = False, plc_addr = None).
    Reset last_ot_time à l'activation pour éviter une coupure immédiate.
    """
    was_active = False
    while True:
        active = conn_state.get('active', False)
        if active and not was_active:
            handler.last_ot_time = time.monotonic()
            was_active = True
        elif not active:
            was_active = False
        if active and (time.monotonic() - handler.last_ot_time) > 5.0:
            log.warning("Watchdog: No O->T data for 5.0s, closing connection")
            conn_state['active'] = False
            handler.plc_addr = None
        await asyncio.sleep(0.1)
