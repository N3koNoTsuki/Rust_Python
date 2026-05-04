#[derive(Clone, Copy, PartialEq)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

pub struct Canva {
    pub height: usize,
    pub width: usize,
    pub pixels: Vec<Color>,
}
#[allow(dead_code)]
impl Canva {
    pub fn init(h: usize, w: usize) -> Self {
        Self {
            height: h,
            width: w,
            pixels: vec![],
        }
    }

    pub fn clear(&mut self, color: Color) {
        self.pixels = vec![color; self.height * self.width];
    }

    pub fn set_pixel(&mut self, h: usize, w: usize, color: Color) {
        match color.a {
            0 => {
                return;
            }
            255 => {
                let index = h * self.width + w;
                self.pixels[index] = color;
            }
            _ => {
                let old = self.pixels[h * self.width + w];
                let alpha = color.a as f32 / 255.0;
                let r = (old.r as f32 * (1.0 - alpha) + color.r as f32 * alpha) as u8;
                let g = (old.g as f32 * (1.0 - alpha) + color.g as f32 * alpha) as u8;
                let b = (old.b as f32 * (1.0 - alpha) + color.b as f32 * alpha) as u8;
                let a = 255;
                let index = h * self.width + w;
                self.pixels[index] = Color { r, g, b, a };
            }
        }
    }

    pub fn line_bresenham(&mut self, x1: usize, y1: usize, x2: usize, y2: usize, color: Color) {
        let dx = (x2 as isize - x1 as isize).abs();
        let dy = (y2 as isize - y1 as isize).abs();
        let sx: isize = if x1 < x2 { 1 } else { -1 };
        let sy: isize = if y1 < y2 { 1 } else { -1 };
        let mut err = dx - dy;
        let (mut x, mut y) = (x1 as isize, y1 as isize);
        loop {
            self.set_pixel(y as usize, x as usize, color);
            if x == x2 as isize && y == y2 as isize {
                break;
            }
            let e2 = 2 * err;
            if e2 > -dy {
                err -= dy;
                x += sx;
            }
            if e2 < dx {
                err += dx;
                y += sy;
            }
        }
    }

    pub fn midpoint_circle(&mut self, xc: usize, yc: usize, r: usize, color: Color) {
        let mut y: i32 = 0;
        let mut x: i32 = r as i32;
        let (xc, yc) = (xc as i32, yc as i32);

        if r == 0 {
            self.set_pixel(yc as usize, xc as usize, color);
            return;
        }

        for &(dy, dx) in &[(0, x), (0, -x), (x, 0), (-x, 0)] {
            let (py, px) = (yc + dy, xc + dx);
            if px >= 0 && py >= 0 && px < self.width as i32 && py < self.height as i32 {
                self.set_pixel(py as usize, px as usize, color);
            }
        }

        let mut p: i32 = 1 - x;
        loop {
            if p < 0 {
                p += 2 * y + 1;
            } else {
                p += 2 * (y - x) + 1;
                x -= 1;
            }
            y += 1;
            if x < y {
                break;
            }

            for &(dy, dx) in &[
                (y, x),
                (-y, x),
                (y, -x),
                (-y, -x),
                (x, y),
                (-x, y),
                (x, -y),
                (-x, -y),
            ] {
                let (py, px) = (yc + dy, xc + dx);
                if px >= 0 && py >= 0 && px < self.width as i32 && py < self.height as i32 {
                    self.set_pixel(py as usize, px as usize, color);
                }
            }
        }
    }

    pub fn fill_triangle(
        &mut self,
        x0: i32,
        y0: i32,
        x1: i32,
        y1: i32,
        x2: i32,
        y2: i32,
        color: Color,
    ) {
        let mut pts = [(x0, y0), (x1, y1), (x2, y2)];
        pts.sort_by_key(|&(_, y)| y);
        let [(ax, ay), (bx, by), (cx, cy)] = pts;

        let interp = |xa: i32, ya: i32, xb: i32, yb: i32, y: i32| -> i32 {
            if yb == ya {
                xa
            } else {
                xa + (xb - xa) * (y - ya) / (yb - ya)
            }
        };

        for y in ay..=cy {
            let x_long = interp(ax, ay, cx, cy, y);
            let x_short = if y < by {
                interp(ax, ay, bx, by, y)
            } else {
                interp(bx, by, cx, cy, y)
            };
            let (xl, xr) = (x_long.min(x_short), x_long.max(x_short));
            for x in xl..=xr {
                if x >= 0 && y >= 0 && x < self.width as i32 && y < self.height as i32 {
                    self.set_pixel(y as usize, x as usize, color);
                }
            }
        }
    }

    pub fn p6_ppm(&self) -> Vec<u8> {
        let mut ppm_map = Vec::new();
        ppm_map.extend_from_slice(b"P6\n");
        ppm_map.extend(format!("{} {}\n", self.width, self.height).as_bytes());
        ppm_map.extend_from_slice(b"255\n");
        for pixel in &self.pixels {
            ppm_map.push(pixel.r);
            ppm_map.push(pixel.g);
            ppm_map.push(pixel.b);
        }
        return ppm_map;
    }

    pub fn dfs(&mut self, x: i32, y: i32, fill_color: Color) {
        if fill_color.a == 0 { return; }
        let target = self.pixels[y as usize * self.width + x as usize];
        let same_rgb = |a: Color, b: Color| a.r == b.r && a.g == b.g && a.b == b.b;
        if same_rgb(target, fill_color) {
            return;
        }
        let mut stack = vec![(x, y)];
        while let Some((x, y)) = stack.pop() {
            if x < 0 || y < 0 || x >= self.width as i32 || y >= self.height as i32 {
                continue;
            }
            if same_rgb(self.pixels[y as usize * self.width + x as usize], target) {
                self.set_pixel(y as usize, x as usize, fill_color);
                stack.push((x + 1, y));
                stack.push((x - 1, y));
                stack.push((x, y + 1));
                stack.push((x, y - 1));
            }
        }
    }
}
