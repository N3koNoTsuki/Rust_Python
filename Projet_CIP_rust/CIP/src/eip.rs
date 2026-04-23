use pyo3::prelude::*;

const CMD_REGISTER_SESSION: u16 = 0x0065;
const CMD_LIST_IDENTITY: u16 = 0x0063;
const CMD_SEND_RR_DATA: u16 = 0x006F;
const CMD_SEND_UNIT_DATA: u16 = 0x0070;

#[derive(Clone, Debug)]
#[pyclass]
pub struct EIPHeader {
    #[pyo3(get, set)]
    command: u16,
    #[pyo3(get, set)]
    length: u16,
    #[pyo3(get, set)]
    session_handle: u32,
    #[pyo3(get, set)]
    status: u32,
    #[pyo3(get, set)]
    sender_context: [u8; 8],
    #[pyo3(get, set)]
    options: u32,
}

#[pyfunction]
#[pyo3(name = "parse_eip_header")]
pub fn parse_eip_header(data: &[u8]) -> PyResult<EIPHeader> {
    if data.len() < 24 {
        return Err(pyo3::exceptions::PyValueError::new_err("Data too short"));
    }

    let command = u16::from_le_bytes(data[0..2].try_into().unwrap());
    let length = u16::from_le_bytes(data[2..4].try_into().unwrap());
    let session_handle = u32::from_le_bytes(data[4..8].try_into().unwrap());
    let status = u32::from_le_bytes(data[8..12].try_into().unwrap());
    let sender_context = data[12..20].try_into().unwrap();
    let options = u32::from_le_bytes(data[20..24].try_into().unwrap());
    let header = EIPHeader {
        command,
        length,
        session_handle,
        status,
        sender_context,
        options,
    };
    Ok(header)
}   


#[pyfunction]
#[pyo3(name = "build_eip_header")]
pub fn build_eip_header(command: u16, 
                    length: u16, 
                    session_handle: u32, 
                    status: u32, 
                    sender_context: [u8; 8], 
                    options: u32) -> PyResult<Vec<u8>> {

    let mut header = Vec::new();
    header.extend_from_slice(&command.to_le_bytes());
    header.extend_from_slice(&length.to_le_bytes());
    header.extend_from_slice(&session_handle.to_le_bytes());
    header.extend_from_slice(&status.to_le_bytes());
    header.extend_from_slice(&sender_context);
    header.extend_from_slice(&options.to_le_bytes());
    Ok(header)
}

#[pyfunction]
#[pyo3(name = "handle_register_session")]
pub fn handle_register_session(mut header: EIPHeader, _data: &[u8]) -> PyResult<Vec<u8>> {
    let payload: Vec<u8> = vec![0x01, 0x00, 0x00, 0x00]; // version=1, options=0

    header.session_handle = 0x12345678;

    let rep_header = build_eip_header(
        CMD_REGISTER_SESSION,
        payload.len() as u16,
        header.session_handle,
        0,
        header.sender_context,
        0,
    )?;

    let mut response = rep_header;
    response.extend_from_slice(&payload);
    Ok(response)
}
