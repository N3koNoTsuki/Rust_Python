"""
Stub file for the Rust PyO3 module `neko_no_lib`.

This file describes the Python interface exposed by the compiled Rust extension.
It is used only for static typing, IDE completion, and linters.
The real implementation is in the compiled Rust module.
"""

class City:
    """
    Represents a geographic city.

    Created from Rust with the constructor exposed by `#[new]`.

    Parameters
    ----------
    name : str
        Name of the city.
    lat : float
        Latitude in degrees.
    lon : float
        Longitude in degrees.

    Notes
    -----
    These attributes exist only if the Rust fields are declared with
    `#[pyo3(get)]` or `#[pyo3(get, set)]`.
    """

    # Public attributes exposed from Rust struct fields
    name: str
    lat: float
    lon: float

    def __new__(cls, name: str, lat: float, lon: float) -> "City": ...
    """
    Create a new City instance.

    Implemented in Rust via `#[new]`.
    """

class Meteo:
    """
    Represents a weather measurement associated with a city.

    Parameters
    ----------
    temp : float
        Temperature in degrees Celsius.
    location : City
        City where the measurement was taken.
    """

    # Attributes exposed from Rust if `#[pyo3(get)]` is used
    temp: float
    location: City

    def __new__(cls, temp: float, location: City) -> "Meteo": ...
    """
    Create a new Meteo instance.

    Implemented in Rust via `#[new]`.
    """

def triple(x: int) -> int:
    """
    Multiply an integer by 3.

    Parameters
    ----------
    x : int
        Input integer.

    Returns
    -------
    int
        Result of x * 3.
    """
    ...

def hello_people(x: int) -> None:
    """
    Print a greeting depending on the number of people.

    Parameters
    ----------
    x : int
        Number of people.

    Behavior
    --------
    Prints one of:
        - "Hello to nobody"
        - "Hello to 1 people"
        - "Hello to N peoples"
    """
    ...

def display_by_char(i_string: str) -> list[str]:
    """
    Convert each character of a string to its hexadecimal code.

    Parameters
    ----------
    i_string : str
        Input string.

    Returns
    -------
    list[str]
        List containing the hexadecimal value of each character.
        Example:
            "Hi" -> ["48", "69"]
    """
    ...

def print_meteo(meteo: Meteo, Debug: bool) -> None:
    """
    Print a Meteo object using the Rust Display implementation.

    Parameters
    ----------
    meteo : Meteo
        Meteo instance to print.
    """
    ...

def test_meteo() -> None:
    """
    Internal test function implemented in Rust.

    Creates:
        City("Lyon", 45.75, 4.85)
        Meteo(25.0, City)

    Then prints the structure using Rust formatting.
    """
    ...
