use pyo3::prelude::*;

mod cpf;
mod cip;
mod eip;

#[pymodule]
fn CIP(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // cpf
    m.add_function(wrap_pyfunction!(cpf::parse_cpf, m)?)?;
    m.add_function(wrap_pyfunction!(cpf::build_cpf, m)?)?;
    // cip
    m.add_function(wrap_pyfunction!(cip::build_list_identity_payload, m)?)?;
    m.add_function(wrap_pyfunction!(cip::handle_get_attribute_all_identity, m)?)?;
    m.add_function(wrap_pyfunction!(cip::handle_get_attribute_single, m)?)?;
    m.add_function(wrap_pyfunction!(cip::handle_forward_open, m)?)?;
    m.add_function(wrap_pyfunction!(cip::handle_forward_close, m)?)?;
    m.add_class::<cip::ConnectionParameters>()?;
    m.add_class::<cip::ConnState>()?;
    // eip
    m.add_function(wrap_pyfunction!(eip::parse_eip_header, m)?)?;
    m.add_function(wrap_pyfunction!(eip::build_eip_header, m)?)?;
    m.add_function(wrap_pyfunction!(eip::handle_register_session, m)?)?;
    m.add_class::<eip::EIPHeader>()?;
    Ok(())
}
