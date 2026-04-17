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
import time
import eip
import cpf
import logging

log = logging.getLogger("io_server")

class EIPUDPProtocol(asyncio.DatagramProtocol):
    """Protocole UDP asyncio pour la réception des paquets O→T du PLC.

    Instancié une seule fois au démarrage et partagé avec les tâches
    task_send_inputs et task_watchdog via conn_state.
    """

    def __init__(self, conn_state: dict) -> None:
        self.conn_state = conn_state
        self.last_ot_time = time.monotonic()
        self.encap_seq = 0
        self.cip_seq = 0
        self.plc_addr = None
        self.transport = None

    def connection_made(self, transport) -> None:
        """Stocke le transport UDP pour l'envoi des paquets T→O."""
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        """Traite un datagramme O→T reçu du PLC.

        Parse le CPF, vérifie le type de l'item I/O (0x00B1),
        extrait CIP_seq et output_byte, met à jour last_ot_time et plc_addr.
        Ignore silencieusement les paquets malformés.
        """
        log.debug(f"--- UDP Datagram received from {addr} ---")
        log.debug(f"UDP RX ({len(data)}B): {data.hex()}")
        
        items = cpf.parse_cpf(data)
        log.debug(f"CPF parsed items count: {len(items)}")
        for i, (item_id, item_data) in enumerate(items):
            log.debug(f"  -> Item {i}: Type=0x{item_id:04X}, Length={len(item_data)}, Payload={item_data.hex()}")
            
        if len(items) < 2:
            log.warning("Less than 2 CPF items in UDP packet, ignoring.")
            return
            
        item2_id, connected_data = items[1]
        if item2_id != cpf.CPF_IO_DATA:
            log.warning(f"UDP Item 1 ID is 0x{item2_id:04X}, expected 0x{cpf.CPF_IO_DATA:04X} (I/O Data), ignoring.")
            return
            
        if len(connected_data) >= 3:
            cip_seq = struct.unpack('<H', connected_data[0:2])[0]
            output_byte = connected_data[2]
        else:
            log.warning(f"UDP connected data too short ({len(connected_data)} bytes), ignoring.")
            return
            
        log.debug(f"O->T: CIP Seq={cip_seq}, Output=0x{output_byte:02X}")
        self.last_ot_time = time.monotonic()
        self.plc_addr = addr

async def task_send_inputs(protocol: EIPUDPProtocol, conn_state: dict):
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
            protocol.last_ot_time = time.monotonic()
            was_active = True






        inputs = 0x00  # TODO: read actual inputs







        packet = cpf.build_cpf([
            (cpf.CPF_CONNECTED_ADDR, struct.pack('<II', conn_state.get('t_o_conn_id', 0), protocol.encap_seq)),
            (cpf.CPF_IO_DATA, struct.pack('<H', protocol.cip_seq) + bytes([inputs]))
        ])
        
        plc_addr = protocol.plc_addr or (conn_state['plc_ip'], 2222)
        log.debug(f"UDP TX ({len(packet)}B to {plc_addr}): {packet.hex()}")
        log.debug(f"T->O: CIP Seq={protocol.cip_seq}, Inputs=0x{inputs:02X}")
        protocol.cip_seq = (protocol.cip_seq + 1) % (2**16)
        protocol.transport.sendto(packet, plc_addr)
        protocol.encap_seq = (protocol.encap_seq + 1) % (2**32)
        await asyncio.sleep(conn_state.get('rpi_t_o', 20000) / 1_000_000)

async def task_watchdog(protocol: EIPUDPProtocol, conn_state: dict):
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
            protocol.last_ot_time = time.monotonic()
            was_active = True
        elif not active:
            was_active = False
        if active and (time.monotonic() - protocol.last_ot_time) > 5.0:
            log.warning("Watchdog: No O->T data for 5.0s, closing connection")
            conn_state['active'] = False
            protocol.plc_addr = None
        await asyncio.sleep(0.1)
