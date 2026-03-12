use pyo3::prelude::*;

/// This module is implemented in Rust.
#[pymodule]
mod neko_no_lib {

    use core::fmt;
    use std::fmt::{Display, Formatter};

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

    #[pyfunction]
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
        name: String,
        // Latitude
        lat: f32,
        // Longitude
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

        fn __str__(&self) -> String {
            format!("{}", self)
        }

        fn __repr__(&self) -> String {
            format!(
                "Debug: City(Name: {}, lat: {}, lon: {})",
                self.name, self.lat, self.lon
            )
        }
    }

    #[derive(Clone, Debug)]
    #[pyclass]
    struct Meteo {
        temp: f64,
        location: City,
    }

    impl Display for Meteo {
        fn fmt(&self, f: &mut Formatter) -> fmt::Result {
            write!(f, "Il fait {}°C a {}", self.temp, self.location)
        }
    }

    #[pymethods]
    impl Meteo {
        #[new]
        fn new(temp: f64, location: City) -> Self {
            Meteo { temp, location }
        }

        fn __str__(&self) -> String {
            format!("{}", self)
        }

        fn __repr__(&self) -> String {
            format!(
                "Debug: Meteo(temp : {}, City : {})",
                self.temp, self.location
            )
        }
    }

    fn print_meteo_rust(meteo: &Meteo) {
        println!("{:?}", meteo);
        println!("{}", meteo);
    }

    #[pyfunction]
    fn print_meteo(meteo: PyRef<'_, Meteo>) {
        print_meteo_rust(&meteo);
    }

    #[pyfunction]
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
        print_meteo_rust(&b);
    }
}
