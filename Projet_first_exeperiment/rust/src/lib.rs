use pyo3::prelude::*;

/// This module is implemented in Rust.
#[pymodule]
mod neko_no_lib {

    use core::fmt;
    use pyo3::prelude::*;
    use std::fmt::{Display, Formatter};

    #[pyfunction] // Inline definition of a pyfunction, also made available to Python
    #[pyo3(name = "triple")]
    fn triple(x: usize) -> usize {
        x * 3
    }

    #[pyfunction]
    #[pyo3(name = "hello_people")]
    fn hello_people(x: usize) {
        match x {
            0 => println!("Hello to nobody"),
            1 => println!("Hello to {} people", x),
            _ => println!("Hello to {} peoples", x),
        }
    }

    #[pyfunction]
    #[pyo3(name = "display_by_char")]
    fn display_by_char(i_string: String) -> Vec<String> {
        let mut o_string = Vec::new();

        for (_i, c) in i_string.chars().enumerate() {
            let buffer = format!("{:02x}", c as i32).to_uppercase();
            println!("H: {buffer}  C: {c}");
            o_string.push(buffer);
        }
        return o_string;
    }

    #[derive(Clone, Debug)]
    #[pyclass]
    struct City {
        #[pyo3(get, set)]
        name: String,
        // Latitude
        #[pyo3(get, set)]
        lat: f32,
        // Longitude
        #[pyo3(get, set)]
        lon: f32,
    }

    impl Display for City {
        fn fmt(&self, f: &mut Formatter) -> fmt::Result {
            let lat_c = if self.lat >= 0.0 { 'N' } else { 'S' };
            let lon_c = if self.lon >= 0.0 { 'E' } else { 'W' };
            write!(
                f,
                "{}: {:.3}°{} {:.3}°{}",
                self.name,
                self.lat.abs(),
                lat_c,
                self.lon.abs(),
                lon_c
            )
        }
    }

    #[pymethods]
    impl City {
        #[new]
        fn new(name: String, lat: f32, lon: f32) -> Self {
            City { name, lat, lon }
        }
    }

    #[derive(Clone, Debug)]
    #[pyclass]
    struct Meteo {
        #[pyo3(get, set)]
        temp: f64,
        #[pyo3(get, set)]
        location: City,
    }

    impl Display for Meteo {
        fn fmt(&self, f: &mut Formatter) -> fmt::Result {
            write!(f, "Il fait {:.2}°C a {}", self.temp, self.location)
        }
    }

    #[pymethods]
    impl Meteo {
        #[new]
        fn new(temp: f64, location: City) -> Self {
            Meteo { temp, location }
        }
    }

    fn print_meteo_rust(meteo: &Meteo, debug: bool) {
        if debug {
            println!("{:?}", meteo);
        }
        println!("{}", meteo);
    }

    #[pyfunction]
    #[pyo3(name = "print_meteo")]
    fn print_meteo(meteo: PyRef<'_, Meteo>, debug: bool) {
        print_meteo_rust(&meteo, debug);
    }

    #[pyfunction]
    #[pyo3(name = "test_meteo")]
    fn test_meteo() {
        let a = City {
            name: String::from("Lyon"),
            lat: 45.75 as f32,
            lon: 4.85 as f32,
        };
        let b = Meteo {
            temp: 25 as f64,
            location: a,
        };
        print_meteo_rust(&b, false);
        println!("");
        print_meteo_rust(&b, true);
    }
}
