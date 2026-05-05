use std::{fs, error::Error, path::{Path}};


pub fn display_rs(path: &Path) -> Result<(), Box<dyn Error>>{
    let content: String = fs::read_to_string(path)?;
    let mut i = 0;
    for line in content.lines() {
        println!("{:02} : {}", i, line);
        i += 1;
    }
    Ok(())
}

fn highlight(word: String, ascii_fgcolor: u8, ascii_bgcolor: u8) -> String {
    format!("\x1b[38;5;{ascii_fgcolor}m\x1b[48;5;{ascii_bgcolor}m{word}\x1b[0m")
}
