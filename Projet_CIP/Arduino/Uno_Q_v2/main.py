import asyncio
import io_server as io
import eip
import cpf
import cip

conn_state = {'active': False}

async def handle_client(reader, writer): 
    (ip_str, port) = writer.get_extra_info('peername')
    print(f"[INFO] : Connection from : {ip_str}:{port}")
    while True:
        data = await reader.read(4096)
        if data == b'':
            break
        else :
            print(f"[INFO] : Received : {data.hex()} from : {ip_str}:{port}")
            header = eip.parse_eip_header(data)
            if header is None:
                continue
            match header.command:
                case eip.CMD_REGISTER_SESSION:
                    print(f"[INFO] : Register Session command received from : {ip_str}:{port}")
                    writer.write(eip.handle_register_session(header, data))
                    await writer.drain()

                case eip.CMD_LIST_IDENTITY:
                    print(f"[INFO] : List Identity command received from : {ip_str}:{port}")

                case eip.CMD_SEND_RR_DATA:
                    print(f"[INFO] : Send RR Data command received from : {ip_str}:{port}")
                    try:
                        items = cpf.parse_cpf(data[30:])
                        cip_data = items[1][1]      # [1] 2ème item, [1] payload
                        service = cip_data[0]
                        path_size = cip_data[1]
                        path = cip_data[2:2+path_size*2]
                        extra = cip_data[2+path_size*2:]
                        class_id = path[1]
                        instance_id = path[3]
                        attribute_id = path[5] if len(path) >= 6 else 0

                        match service:
                            case 0x0E :
                                cip_response = cip.handle_get_attribute_single(class_id, instance_id, attribute_id)
                            case 0x01 :
                                cip_response = cip.handle_get_attribute_all_identity()
                            case 0x54 :
                                conn_state['plc_ip'] = ip_str   
                                cip_response = cip.handle_forward_open(extra, conn_state)
                                print(f"[INFO] : ForwardOpen: o_t={hex(conn_state.get('o_t_conn_id', 0))}, t_o={hex(conn_state.get('t_o_conn_id', 0))}, active={conn_state.get('active')}")
                            
                            case 0x4E :
                                cip_response = cip.handle_forward_close(extra, conn_state)
                                print(f"[INFO] : ForwardClose: o_t={hex(conn_state.get('o_t_conn_id', 0))}, t_o={hex(conn_state.get('t_o_conn_id', 0))}, active={conn_state.get('active')}")
                            
                            case _ :
                                print(f"[WARNING] : Unknown service received from : {ip_str}:{port}")
                                cip_response = b''

                        cpf_response = cpf.build_cpf([(0x0000, b''), (0x00B2, cip_response)])
                        payload_response = b'\x00\x00\x00\x00' + b'\x00\x00' + cpf_response
                        eip_response = eip.build_eip_header(eip.CMD_SEND_RR_DATA, len(payload_response), header.session_handle) + payload_response
                        writer.write(eip_response)
                        await writer.drain()
                    except Exception as e:
                        print(f"[ERROR] : SendRRData handler: {e}")

                case eip.CMD_SEND_UNIT_DATA:
                    print(f"[INFO] : Send Unit Data command received from : {ip_str}:{port}")

                case _:
                    print(f"[WARNING] : Unknown command received from : {ip_str}:{port}")




async def main():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 44818)
    print("[INFO] : Server started on port 44818")

    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: io.EIPUDPProtocol(conn_state),
        local_addr=('0.0.0.0', 2222)
    )
    print("[INFO] : UDP server started on port 2222")

    asyncio.create_task(io.task_send_inputs(protocol, conn_state))
    asyncio.create_task(io.task_watchdog(protocol, conn_state))

    await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
