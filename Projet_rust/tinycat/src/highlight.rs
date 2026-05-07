// Couleurs ANSI 256 (style one-dark-ish)
const C_KEYWORD: u8 = 170; // violet
const C_TYPE: u8 = 38; // cyan
const C_STRING: u8 = 107; // vert
const C_NUMBER: u8 = 215; // orange
const C_COMMENT: u8 = 244; // gris
const C_MACRO: u8 = 203; // rouge clair
const C_LIFETIME: u8 = 215; // orange
const C_CHAR: u8 = 107; // vert (comme string)

fn fg(s: &str, color: u8) -> String {
    format!("\x1b[38;5;{}m{}\x1b[0m", color, s)
}

fn is_keyword(s: &str) -> bool {
    matches!(
        s,
        "as" | "break"
             | "const"
             | "continue"
             | "crate"
             | "else"
             | "enum"
             | "extern"
             | "false"
             | "fn"
             | "for"
             | "if"
             | "impl"
             | "in"
             | "let"
             | "loop"
             | "match"
             | "mod"
             | "move"
             | "mut"
             | "pub"
             | "ref"
             | "return"
             | "self"
             | "Self"
             | "static"
             | "struct"
             | "super"
             | "trait"
             | "true"
             | "type"
             | "unsafe"
             | "use"
             | "where"
             | "while"
             | "async"
             | "await"
             | "dyn"
             | "box"
    )
}

fn is_builtin_type(s: &str) -> bool {
    matches!(
        s,
        "i8" | "i16"
             | "i32"
             | "i64"
             | "i128"
             | "isize"
             | "u8"
             | "u16"
             | "u32"
             | "u64"
             | "u128"
             | "usize"
             | "f32"
             | "f64"
             | "bool"
             | "char"
             | "str"
             | "String"
             | "Vec"
             | "Option"
             | "Result"
             | "Box"
             | "Some"
             | "None"
             | "Ok"
             | "Err"
    )
}

fn is_ident_start(c: char) -> bool {
    c.is_alphabetic() || c == '_'
}
fn is_ident_cont(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// Highlighte une ligne. `in_block` track les /* */ qui débordent entre lignes.
pub fn highlight_line(line: &str, in_block: &mut bool) -> String {
    let chars: Vec<char> = line.chars().collect();
    let mut out = String::new();
    let mut i = 0;

    while i < chars.len() {
        // --- on est dans un /* ... */ multi-ligne ---
        if *in_block {
            let start = i;
            while i < chars.len() {
                if chars[i] == '*' && i + 1 < chars.len() && chars[i + 1] == '/' {
                    i += 2;
                    *in_block = false;
                    break;
                }
                i += 1;
            }
            let segment: String = chars[start..i].iter().collect();
            out.push_str(&fg(&segment, C_COMMENT));
            continue;
        }

        let c = chars[i];

        // --- // commentaire de ligne ---
        if c == '/' && i + 1 < chars.len() && chars[i + 1] == '/' {
            let segment: String = chars[i..].iter().collect();
            out.push_str(&fg(&segment, C_COMMENT));
            break;
        }

        // --- /* commentaire de bloc ---
        if c == '/' && i + 1 < chars.len() && chars[i + 1] == '*' {
            let start = i;
            i += 2;
            *in_block = true;
            while i < chars.len() {
                if chars[i] == '*' && i + 1 < chars.len() && chars[i + 1] == '/' {
                    i += 2;
                    *in_block = false;
                    break;
                }
                i += 1;
            }
            let segment: String = chars[start..i].iter().collect();
            out.push_str(&fg(&segment, C_COMMENT));
            continue;
        }

        // --- string literal "..." ---
        if c == '"' {
            let start = i;
            i += 1;
            while i < chars.len() {
                if chars[i] == '\\' && i + 1 < chars.len() {
                    i += 2; // skip échappement
                    continue;
                }
                if chars[i] == '"' {
                    i += 1;
                    break;
                }
                i += 1;
            }
            let segment: String = chars[start..i].iter().collect();
            out.push_str(&fg(&segment, C_STRING));
            continue;
        }

        // --- char literal OU lifetime ---
        if c == '\'' {
            // Heuristique : si on voit 'x' ou '\x' c'est un char, sinon lifetime
            let is_char_lit = if i + 2 < chars.len() && chars[i + 1] == '\\' {
                // '\n' '\t' '\\' etc -> cherche ' suivant
                chars[i + 2..].iter().take(4).any(|&ch| ch == '\'')
            } else if i + 2 < chars.len() && chars[i + 2] == '\'' {
                true
            } else {
                false
            };

            if is_char_lit {
                let start = i;
                i += 1;
                while i < chars.len() {
                    if chars[i] == '\\' && i + 1 < chars.len() {
                        i += 2;
                        continue;
                    }
                    if chars[i] == '\'' {
                        i += 1;
                        break;
                    }
                    i += 1;
                }
                let segment: String = chars[start..i].iter().collect();
                out.push_str(&fg(&segment, C_CHAR));
            } else {
                // lifetime : 'a, 'static
                let start = i;
                i += 1;
                while i < chars.len() && is_ident_cont(chars[i]) {
                    i += 1;
                }
                let segment: String = chars[start..i].iter().collect();
                out.push_str(&fg(&segment, C_LIFETIME));
            }
            continue;
        }

        // --- nombre ---
        if c.is_ascii_digit() {
            let start = i;
            while i < chars.len()
                && (chars[i].is_alphanumeric() || chars[i] == '_' || chars[i] == '.')
            {
                i += 1;
            }
            let segment: String = chars[start..i].iter().collect();
            out.push_str(&fg(&segment, C_NUMBER));
            continue;
        }

        // --- identifiant / keyword / type / macro ---
        if is_ident_start(c) {
            let start = i;
            while i < chars.len() && is_ident_cont(chars[i]) {
                i += 1;
            }
            let ident: String = chars[start..i].iter().collect();

            // macro ? -> consomme le !
            if i < chars.len() && chars[i] == '!' {
                i += 1;
                let segment: String = chars[start..i].iter().collect();
                out.push_str(&fg(&segment, C_MACRO));
            } else if is_keyword(&ident) {
                out.push_str(&fg(&ident, C_KEYWORD));
            } else if is_builtin_type(&ident) {
                out.push_str(&fg(&ident, C_TYPE));
            } else {
                out.push(c);
                // re-push le reste sans couleur
                for &ch in &chars[start + 1..i] {
                    out.push(ch);
                }
            }
            continue;
        }

        // --- tout le reste : ponctuation, espaces ---
        out.push(c);
        i += 1;
    }

    out
}
