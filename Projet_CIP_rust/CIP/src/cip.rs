use pyo3::prelude::*;

const VENDOR_ID: u16     = 0xFFFF;
const DEVICE_TYPE: u16   = 12;
const PRODUCT_CODE: u16  = 1;
const REVISION: (u8, u8) = (1, 1);
const SERIAL_NUMBER: u32 = 0x00000001;
const PRODUCT_NAME: &str = "Arduino Uno Q";

#[derive(Clone, Debug)]
#[pyclass]
pub struct ConnectionParameters {
    #[pyo3(get, set)]
    priority_time_tick : u8,
    #[pyo3(get, set)]
    timeout_ticks : u8,
    #[pyo3(get, set)]
    o_t_conn_id : u32,
    #[pyo3(get, set)]
    t_o_conn_id : u32,
    #[pyo3(get, set)]
    conn_serial : u16,
    #[pyo3(get, set)]
    vendor_id : u16,
    #[pyo3(get, set)]
    originator_serial : u32,
    #[pyo3(get, set)]
    timeout_multiplier : u8,
    #[pyo3(get, set)]
    reserved : [u8; 3],
    #[pyo3(get, set)]
    rpi_o_t : u32,
    #[pyo3(get, set)]
    o_t_conn_params : u16,
    #[pyo3(get, set)]
    rpi_t_o : u32,
    #[pyo3(get, set)]
    t_o_conn_params : u16,
    #[pyo3(get, set)]
    transport_type : u8,
}

#[derive(Clone, Debug)]
#[pyclass]
pub struct ConnState {
    #[pyo3(get, set)]
    o_t_conn_id       : u32,
    #[pyo3(get, set)]
    t_o_conn_id       : u32,
    #[pyo3(get, set)]
    rpi_o_t           : u32,
    #[pyo3(get, set)]
    rpi_t_o           : u32,
    #[pyo3(get, set)]
    conn_serial       : u16,
    #[pyo3(get, set)]
    vendor_id         : u16,
    #[pyo3(get, set)]
    originator_serial : u32,
    #[pyo3(get, set)]
    active            : bool,
}

#[pyfunction]
#[pyo3(name = "build_list_identity_payload")]
pub fn build_list_identity_payload() -> Vec<u8> {
    let mut payload = Vec::new();
    payload.extend_from_slice(&0x0001u16.to_le_bytes()); // item count
    payload.extend_from_slice(&0x000Cu16.to_le_bytes()); // item type

    let mut payload_secondary = Vec::new();
    payload_secondary.extend_from_slice(&0x0001u16.to_le_bytes()); // protocol version
    payload_secondary.extend_from_slice(&2u16.to_le_bytes());       // AF_INET
    payload_secondary.extend_from_slice(&0xAF12u16.to_be_bytes());  // port
    payload_secondary.extend_from_slice(&0x00000000u32.to_be_bytes()); // ip address
    payload_secondary.extend_from_slice(&0u64.to_le_bytes());       // padding
    payload_secondary.extend_from_slice(&VENDOR_ID.to_le_bytes());
    payload_secondary.extend_from_slice(&DEVICE_TYPE.to_le_bytes());
    payload_secondary.extend_from_slice(&PRODUCT_CODE.to_le_bytes());
    payload_secondary.push(REVISION.0);
    payload_secondary.push(REVISION.1);
    payload_secondary.extend_from_slice(&0x0000u16.to_le_bytes()); // status
    payload_secondary.extend_from_slice(&SERIAL_NUMBER.to_le_bytes());
    payload_secondary.push(PRODUCT_NAME.len() as u8);
    payload_secondary.extend_from_slice(PRODUCT_NAME.as_bytes());
    payload_secondary.push(0xFF); // state

    let item_length = payload_secondary.len() as u16;
    payload.extend_from_slice(&item_length.to_le_bytes());
    payload.extend_from_slice(&payload_secondary);

    payload
}

#[pyfunction]
#[pyo3(name = "handle_get_attribute_all_identity")]
pub fn handle_get_attribute_all_identity() -> Vec<u8> {
    let mut payload = Vec::new();
    payload.extend_from_slice(&VENDOR_ID.to_le_bytes());
    payload.extend_from_slice(&DEVICE_TYPE.to_le_bytes());
    payload.extend_from_slice(&PRODUCT_CODE.to_le_bytes());
    payload.push(REVISION.0);
    payload.push(REVISION.1);
    payload.extend_from_slice(&0x0000u16.to_le_bytes()); // status
    payload.extend_from_slice(&SERIAL_NUMBER.to_le_bytes());
    payload.push(PRODUCT_NAME.len() as u8);
    payload.extend_from_slice(PRODUCT_NAME.as_bytes());
    payload.push(0xFF); // state
    payload
}

#[pyfunction]
#[pyo3(name = "handle_get_attribute_single")]
pub fn handle_get_attribute_single(class_id: u16, _instance: u16, attribute: u16) -> PyResult<Vec<u8>> {
    let data: Vec<u8> = match class_id {
        0x01 => match attribute {
            0x0001 => VENDOR_ID.to_le_bytes().to_vec(),
            0x0002 => DEVICE_TYPE.to_le_bytes().to_vec(),
            0x0003 => PRODUCT_CODE.to_le_bytes().to_vec(),
            0x0004 => vec![REVISION.0, REVISION.1],
            0x0005 => 0x0000u16.to_le_bytes().to_vec(),
            0x0006 => SERIAL_NUMBER.to_le_bytes().to_vec(),
            0x0007 => {
                let mut d = vec![PRODUCT_NAME.len() as u8];
                d.extend_from_slice(PRODUCT_NAME.as_bytes());
                d
            }
            0x0008 => vec![0xFF],
            _ => return Ok(vec![0x8E, 0x00, 0x14, 0x00]),
        },
        0xC0 => match attribute {
            0x0001 => 0x00000001u32.to_le_bytes().to_vec(),
            0x0002 => 0x00000010u32.to_le_bytes().to_vec(),
            0x0003 => 0x00000000u32.to_le_bytes().to_vec(),
            0x0005 => vec![0u8; 21],
            0x0012 => 0x0000u16.to_le_bytes().to_vec(),
            _ => return Ok(vec![0x8E, 0x00, 0x14, 0x00]),
        },
        0xF4 => match attribute {
            0x0007 => 0x0004u16.to_le_bytes().to_vec(),
            0x0008 => 0x0001u16.to_le_bytes().to_vec(),
            _ => return Ok(vec![0x8E, 0x00, 0x14, 0x00]),
        },
        _ => return Ok(vec![0x8E, 0x00, 0x14, 0x00]),
    };

    let mut response = vec![0x8E, 0x00, 0x00, 0x00];
    response.extend_from_slice(&data);
    Ok(response)
}

#[pyfunction]
#[pyo3(name = "handle_forward_open")]
pub fn handle_forward_open(payload: &[u8], conn_state: &mut ConnState) -> PyResult<Vec<u8>> {
    let conn_parameters = ConnectionParameters {
        priority_time_tick : payload[0],
        timeout_ticks      : payload[1],
        o_t_conn_id        : u32::from_le_bytes(payload[2..6].try_into().unwrap()),
        t_o_conn_id        : u32::from_le_bytes(payload[6..10].try_into().unwrap()),
        conn_serial        : u16::from_le_bytes(payload[10..12].try_into().unwrap()),
        vendor_id          : u16::from_le_bytes(payload[12..14].try_into().unwrap()),
        originator_serial  : u32::from_le_bytes(payload[14..18].try_into().unwrap()),
        timeout_multiplier : payload[18],
        reserved           : payload[19..22].try_into().unwrap(),
        rpi_o_t            : u32::from_le_bytes(payload[22..26].try_into().unwrap()),
        o_t_conn_params    : u16::from_le_bytes(payload[26..28].try_into().unwrap()),
        rpi_t_o            : u32::from_le_bytes(payload[28..32].try_into().unwrap()),
        t_o_conn_params    : u16::from_le_bytes(payload[32..34].try_into().unwrap()),
        transport_type     : payload[34],
    };

    conn_state.o_t_conn_id = if conn_parameters.o_t_conn_id != 0 {
        conn_parameters.o_t_conn_id
    } else {
        0xDEAD0001
    };
    conn_state.t_o_conn_id       = conn_parameters.t_o_conn_id;
    conn_state.rpi_o_t           = conn_parameters.rpi_o_t;
    conn_state.rpi_t_o           = conn_parameters.rpi_t_o;
    conn_state.conn_serial       = conn_parameters.conn_serial;
    conn_state.vendor_id         = conn_parameters.vendor_id;
    conn_state.originator_serial = conn_parameters.originator_serial;
    conn_state.active            = true;

    let mut response = vec![0xD4, 0x00, 0x00, 0x00];
    response.extend_from_slice(&conn_state.o_t_conn_id.to_le_bytes());
    response.extend_from_slice(&conn_parameters.t_o_conn_id.to_le_bytes());
    response.extend_from_slice(&conn_parameters.conn_serial.to_le_bytes());
    response.extend_from_slice(&conn_parameters.vendor_id.to_le_bytes());
    response.extend_from_slice(&conn_parameters.originator_serial.to_le_bytes());
    response.extend_from_slice(&conn_parameters.rpi_o_t.to_le_bytes());
    response.extend_from_slice(&conn_parameters.rpi_t_o.to_le_bytes());
    response.extend_from_slice(&0x0000u16.to_le_bytes());
    Ok(response)
}

#[pyfunction]
#[pyo3(name = "handle_forward_close")]
pub fn handle_forward_close(_payload: &[u8], conn_state: &mut ConnState) -> PyResult<Vec<u8>> {
    conn_state.active = false;

    let mut response = vec![0xCE, 0x00, 0x00, 0x00];
    response.extend_from_slice(&conn_state.conn_serial.to_le_bytes());
    response.extend_from_slice(&conn_state.vendor_id.to_le_bytes());
    response.extend_from_slice(&conn_state.originator_serial.to_le_bytes());
    response.extend_from_slice(&0x0000u16.to_le_bytes());
    Ok(response)
}
