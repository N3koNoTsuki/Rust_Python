use color::*;

fn main(){
    println!("{}", fgcolor(String::from("meow"), 111));
    println!("{}", bgcolor(String::from("meow"), 202));
    println!("{}", color(String::from("meow"), 111, 202));
}