/*
*   Name : main.rs
*   Objetif : recreate the famous grep function
*   No cargo, just std
*
*   Author : NekoNoTsuki
*/

use std::io::{self, BufRead};
use std::{env, error::Error, fs};


fn highlight(line: &str, pattern: &str) -> String {
    line.replace(pattern, &format!("\x1b[31m{pattern}\x1b[0m"))
}

fn handle_single(files: &str, string: &str) -> Result<(), Box<dyn Error>> {
    println!("searching in {files} for {string} :");

    let content: String = fs::read_to_string(files)?;
    for line in content.lines() {
        if line.contains(string) {
            println!("{}", highlight(line, string));
        }
    }
    Ok(())
}

fn handle_stdout(string: &str) -> Result<(), Box<dyn Error>> {
    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = line?;
        if line.contains(string) {
            println!("{}", highlight(&line, string));
        }
    }
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();

    let result = match args.len() {
        1 | 0 => {
            eprintln!("Usage: nekonogrep <pattern> [file]");
            return;
        }
        2 => handle_stdout(&args[1]),
        3 => handle_single(&args[2], &args[1]),
        _ => {
            eprintln!("Usage: nekonogrep <pattern> [file]");
            return;
        }
    };

    if let Err(e) = result {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}
