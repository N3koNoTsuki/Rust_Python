use std::{fs, error::Error, path::Path};
use crate::highlight;

pub fn display_rs(path: &Path) -> Result<(), Box<dyn Error>> {
    let content = fs::read_to_string(path)?;
    let mut in_block = false;
    for (i, line) in content.lines().enumerate() {
        let highlighted = highlight::highlight_line(line, &mut in_block);
        println!("{:05} : {}", i, highlighted);
    }
    Ok(())
}