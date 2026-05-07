
pub fn fgcolor(word :String, ascii_color: u8) -> String{
    format!("\x1b[38;5;{}m{}\x1b[0m", ascii_color, word)
}

pub fn bgcolor(word :String, ascii_color: u8) -> String{
    format!("\x1b[48;5;{}m{}\x1b[0m", ascii_color, word)
}

pub fn color(word: String, fg_color: u8, bg_color: u8) -> String {
    format!("\x1b[48;5;{};38;5;{}m{}\x1b[0m", bg_color, fg_color, word)
}



#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_fgcolor(){
        let result = fgcolor(String::from("meow"), 255);
        assert_eq!(result, "\x1b[38;5;255mmeow\x1b[0m")
    }
    #[test]
    fn test_bgcolor(){
        let result = bgcolor(String::from("meow"), 255);
        assert_eq!(result, "\x1b[48;5;255mmeow\x1b[0m")
    }
    #[test]
    fn test_color(){
        let result = color(String::from("meow"), 196, 111);
        assert_eq!(result, "\x1b[48;5;111;38;5;196mmeow\x1b[0m")
    }
}
