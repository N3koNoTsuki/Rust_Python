use pyo3::prelude::*;

pub const CPF_NULL_ADDR: u16        = 0x0000;
pub const CPF_UNCONNECTED_DATA: u16 = 0x00B2;
pub const CPF_CONNECTED_ADDR: u16   = 0x8002;
pub const CPF_CONNECTED_DATA: u16   = 0x8001;
pub const CPF_IO_DATA: u16          = 0x00B1;

#[pyfunction]
#[pyo3(name = "parse_cpf")]
pub fn parse_cpf(data: &[u8]) -> PyResult<Vec<(u16, Vec<u8>)>> {
    let item_count = data[0] as u16 + ((data[1] as u16) << 8);
    let mut list_item: Vec<(u16, Vec<u8>)> = Vec::new();
    let mut ind = 2usize;
    for _ in 0..item_count {
        let type_id = data[ind] as u16 + ((data[ind + 1] as u16) << 8);
        let length  = data[ind + 2] as usize + ((data[ind + 3] as usize) << 8);
        let payload = data[ind + 4..ind + 4 + length].to_vec();
        ind += 4 + length;
        list_item.push((type_id, payload));
    }
    Ok(list_item)
}

#[pyfunction]
#[pyo3(name = "build_cpf")]
pub fn build_cpf(items: Vec<(u16, Vec<u8>)>) -> PyResult<Vec<u8>> {
    let mut data = Vec::new();
    data.extend_from_slice(&(items.len() as u16).to_le_bytes());
    for (type_id, payload) in &items {
        data.extend_from_slice(&type_id.to_le_bytes());
        data.extend_from_slice(&(payload.len() as u16).to_le_bytes());
        data.extend_from_slice(payload);
    }
    Ok(data)
}
