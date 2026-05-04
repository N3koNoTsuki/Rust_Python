use std::{fs::File, io::Write};
mod canva;
use canva::{Canva, Color};




fn main() {
    let mut canva = Canva::init(255, 255);
    canva.clear(Color { r: 0, g: 0, b: 255, a: 255 });
    canva.midpoint_circle(122, 122, 50, Color { r: 255, g: 0, b: 0, a: 255 });
    canva.dfs(122, 122, Color { r: 0, g: 255, b: 0, a: 255 });
    let ppm_map = canva.p6_ppm();
    let mut file = File::create("ppm_map.ppm").unwrap();
    file.write_all(&ppm_map).unwrap();
}