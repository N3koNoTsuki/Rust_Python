/*
*   Name : main.rs
*   Objetif : recreate the famous cat function
*   No cargo, just std
*
*   Author : NekoNoTsuki
*/
use std::{env, error::Error, path::Path};
mod display;
mod highlight;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("ouch");
        return;
    }
    for arg in args.iter().skip(1) {
        let path = Path::new(arg);
        let name = path.file_name().unwrap_or_default().to_string_lossy();
        print_header(&name);
        if let Err(e) = handle_files_type(path) {
            eprintln!("Error on {}: {e}", name);
        }
    }
}

fn print_header(name: &str) {
    let border = format!("/{}/", "-".repeat(name.len() + 2));
    println!("\x1b[38;5;160m{}\x1b[0m", border);
    println!("\x1b[38;5;160m>\x1b[0m {}", name);
    println!("\x1b[38;5;160m{}\x1b[0m", border);
}

fn handle_files_type(path: &Path) -> Result<(), Box<dyn Error>> {
    let ext = path.extension().and_then(|e| e.to_str());
    match ext {
        Some("rs") => display::display_rs(path)?,
        _ => return Err("not supported yet".into()),
    }
    Ok(())
}
