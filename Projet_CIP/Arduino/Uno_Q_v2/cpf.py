CPF_NULL_ADDR = 0x0000
CPF_UNCONNECTED_DATA = 0x00B2
CPF_CONNECTED_ADDR = 0x8002
CPF_CONNECTED_DATA = 0x8001

def parse_cpf(data: bytes) -> list :
    ietm_count = data[0] + (data[1] << 8)
    list_ietm = []
    ind = 2
    for i in range(ietm_count) :
        type_id = data[ind] + (data[ind + 1] << 8)
        length = data[ind + 2] + (data[ind + 3] << 8)
        payload = data[ind + 4 : ind + 4 + length]
        ind += 4 + length
        list_ietm.append((type_id, payload))
    return list_ietm

def build_cpf(items : list) -> bytes :
    data = bytearray()
    data += (len(items) & 0xFF).to_bytes(1, 'little')
    data += ((len(items) >> 8) & 0xFF).to_bytes(1, 'little')
    for item in items :
        type_id, payload = item
        data += (type_id & 0xFF).to_bytes(1, 'little')
        data += ((type_id >> 8) & 0xFF).to_bytes(1, 'little')
        data += (len(payload) & 0xFF).to_bytes(1, 'little')
        data += ((len(payload) >> 8) & 0xFF).to_bytes(1, 'little')
        data += payload
    return bytes(data)