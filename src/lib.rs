use pyo3::prelude::*;

/// This module is implemented in Rust.
#[pymodule]
mod neko_no_lib {
    use pyo3::prelude::*;

    #[pyfunction] // Inline definition of a pyfunction, also made available to Python
    fn triple(x: usize) -> usize {
        x * 3
    }

    #[pyfunction]
    fn hello_people(x: usize) {
        match x {
            0 => println!("Hello to nobody"),
            1 => println!("Hello to {} people", x),
            _ => println!("Hello to {} peoples", x),
        }
    }
}
