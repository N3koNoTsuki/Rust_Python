/*
*   Name : main.rs
*   Objetif : recreate the famous grep function
*   No cargo, just std
*
*   Author : NekoNoTsuki
*/

use std::{env, error::Error, path::{Path}};
mod highlighter;

fn main() {
    let args: Vec<String> = env::args().collect();
    let args_count = args.len(); 
    if args_count < 2{
        eprintln!("ouch");
        return;
    }
    else {
        
        for arg in 1..args_count{
            let path = Path::new(&args[arg]);
            println!("\x1b[38;5;160m/-------------------/\x1b[0m");
            println!("> {}", path.file_name().unwrap_or_default().to_string_lossy());
            println!("\x1b[38;5;160m/-------------------/\x1b[0m");
            if let Err(e) = handle_files_type(path) {
                eprintln!("Error: {e}");
                std::process::exit(1);
            }
        }
    }
}


fn handle_files_type(path: &Path) -> Result<(), Box<dyn Error>> {

    let ext = path.extension().and_then(|e| e.to_str());
    match ext {
        Some("rs") => highlighter::display_rs(path)?,
        _ => return Err("not supported yet".into()),
    }
    Ok(())
}


#[allow(dead_code)]
fn sep(title: &str) {
    println!("\n\x1b[1;37m=== {} ===\x1b[0m", title);
}
#[allow(dead_code)]
fn styles() {
    // ── Styles ──────────────────────────────────────────────────────────────
    sep("STYLES");
    println!("\x1b[1mBold\x1b[22m | \x1b[2mDim\x1b[22m | \x1b[3mItalic\x1b[23m | \x1b[4mUnderline\x1b[24m | \x1b[5mBlink\x1b[25m | \x1b[7mReverse\x1b[27m | \x1b[8mHidden\x1b[28m | \x1b[9mStrikethrough\x1b[29m");

    // ── Couleurs FG 8 ────────────────────────────────────────────────────────
    sep("FG 8 COLORS (30-37)");
    let names = ["Black","Red","Green","Yellow","Blue","Magenta","Cyan","White"];
    for (i, name) in names.iter().enumerate() {
        print!("\x1b[{}m{}\x1b[0m ", 30 + i, name);
    }
    println!();

    // ── Couleurs BG 8 ────────────────────────────────────────────────────────
    sep("BG 8 COLORS (40-47)");
    for i in 0..8usize {
        print!("\x1b[{};30m {} \x1b[0m ", 40 + i, names[i]);
    }
    println!();

    // ── Bright FG (90-97) ───────────────────────────────────────────────────
    sep("BRIGHT FG (90-97)");
    for (i, name) in names.iter().enumerate() {
        print!("\x1b[{}mBright {}\x1b[0m ", 90 + i, name);
    }
    println!();

    // ── Bright BG (100-107) ─────────────────────────────────────────────────
    sep("BRIGHT BG (100-107)");
    for i in 0..8usize {
        print!("\x1b[{};30m {} \x1b[0m ", 100 + i, names[i]);
    }
    println!();

    // ── Bold + couleur combo ─────────────────────────────────────────────────
    sep("BOLD + COLOR COMBO");
    println!("\x1b[1;31mBold Red\x1b[0m | \x1b[2;37;41mDim White on Red\x1b[0m | \x1b[3;36mItalic Cyan\x1b[0m | \x1b[4;33mUnderline Yellow\x1b[0m");

    // ── 256 couleurs FG ──────────────────────────────────────────────────────
    sep("256 COLORS FG (38;5;n)");
    // Affiche les 256 couleurs en blocs de 16
    for row in 0..16 {
        for col in 0..16 {
            let n = row * 16 + col;
            print!("\x1b[38;5;{n}m{n:3}\x1b[0m ");
        }
        println!();
    }

    // ── 256 couleurs BG ──────────────────────────────────────────────────────
    sep("256 COLORS BG (48;5;n) - sample");
    for n in (0..256usize).step_by(8) {
        print!("\x1b[48;5;{n}m   \x1b[0m");
    }
    println!();

    // ── RGB Truecolor ────────────────────────────────────────────────────────
    sep("RGB TRUECOLOR (38;2;r;g;b)");
    // dégradé rouge → bleu
    for i in 0..=40u8 {
        let r = 255 - i * 6;
        let b = i * 6;
        print!("\x1b[38;2;{r};0;{b}m█\x1b[0m");
    }
    println!();

    sep("RGB TRUECOLOR BG (48;2;r;g;b)");
    // dégradé vert → jaune
    for i in 0..=40u8 {
        let g = 200u8.saturating_sub(i * 2);
        let r = i * 6;
        print!("\x1b[48;2;{r};{g};0m \x1b[0m");
    }
    println!();

    // ── Reset partiel ────────────────────────────────────────────────────────
    sep("PARTIAL RESETS");
    println!("\x1b[1;31mBold+Red → reset bold only → \x1b[22mstill Red\x1b[0m");
    println!("\x1b[1;34mBold+Blue → reset fg only → \x1b[39mno color, still bold\x1b[0m");
    println!("\x1b[41;37mWhite on Red → reset bg only → \x1b[49mno bg, still white text\x1b[0m");

    // ── Cursor controls ──────────────────────────────────────────────────────
    sep("CURSOR CONTROLS");
    println!("Save pos → move right 5 → restore:");
    print!("  [BEFORE]\x1b[s\x1b[5C[AFTER MOVE]\x1b[u[RESTORED]\n");

    println!("Move up 1, print, move back down:");
    println!("  line A");
    print!("\x1b[1A  → inserted above line A ←\x1b[1B\n");

    println!("Column jump to col 20:");
    print!("  \x1b[20G[col 20]\n");

    // ── Erase ────────────────────────────────────────────────────────────────
    sep("ERASE (demo visuel limité en batch)");
    println!("Erase from cursor to EOL demo:");
    print!("  AAAA BBBB CCCC\x1b[8D\x1b[0K\n"); // retour 8 chars, efface jusqu'à fin de ligne
    println!("  (les 'BBBB CCCC' devraient avoir disparu)");

    // ── Private modes ────────────────────────────────────────────────────────
    sep("PRIVATE MODES");
    println!("Cursor invisible 1s puis visible :");
    print!("\x1b[?25l");
    std::thread::sleep(std::time::Duration::from_secs(1));
    print!("\x1b[?25h");
    println!("  curseur de retour");

    sep("FIN - RESET GLOBAL");
    print!("\x1b[0m");
    println!("Tout reset. Done.");
}

