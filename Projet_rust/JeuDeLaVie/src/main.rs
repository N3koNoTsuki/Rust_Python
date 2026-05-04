/*
*   Name : main.rs
*   Objetif : Jeu de la vie de Conway
*   No cargo, just std
*
*   Author : NekoNoTsuki
*/

#![allow(dead_code)]

use std::fs::File;
use std::io::Read;
use std::thread::sleep;

fn test_color() {
    for i in 16..256 {
        print!("\x1b[48;5;{}m{:03}", i, i);
        print!("\x1b[0m");
        if (i - 15) % 6 != 0 {
            print!(" ");
        } else {
            println!();
        }
    }

    println!("===");
    println!("\x1b[48;5;{}\x1b[0m", 231);
    println!("\x1b[48;5;{}\x1b[0m", 232);
    println!("===");
}

fn randomize_grid(grid: &mut [Vec<bool>]) {
    let height = grid.len();
    let width = grid.first().map_or(0, |r| r.len());
    let total = height * width;

    let mut bytes = vec![0u8; total];
    File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut bytes))
        .unwrap();

    let mut idx = 0;
    for row in grid.iter_mut() {
        for cell in row.iter_mut() {
            *cell = bytes[idx] & 1 == 1;
            idx += 1;
        }
    }
}

fn display_grid(grid: &[Vec<bool>]) {
    for row in grid {
        for cell in row {
            if *cell {
                print!("\x1b[48;5;{}m  \x1b[0m", 231);
            } else {
                print!("\x1b[48;5;{}m  \x1b[0m", 232);
            }
        }
        println!();
    }
}

fn count_neighbors(grid: &[Vec<bool>], x: usize, y: usize) -> usize {
    let height = grid.len();
    let width = grid.first().map_or(0, |r| r.len());
    let mut count = 0;

    for dy in -1isize..=1isize {
        for dx in -1isize..=1isize {
            if dy == 0 && dx == 0 {
                continue;
            }
            let nx = ((x as isize + dx) + width as isize) % width as isize;
            let ny = ((y as isize + dy) + height as isize) % height as isize;
            if grid[ny as usize][nx as usize] {
                count += 1;
            }
        }
    }
    count
}

fn update_grid(grid: &mut Vec<Vec<bool>>) {
    let height = grid.len();
    let width = grid.first().map_or(0, |r| r.len());
    let mut new_grid = vec![vec![false; width]; height];

    for y in 0..height {
        for x in 0..width {
            let neighbors = count_neighbors(grid, x, y);
            new_grid[y][x] = neighbors == 3 || (neighbors == 2 && grid[y][x]);
        }
    }

    *grid = new_grid;
}

fn clear_screen() {
    println!("\x1B[2J\x1B[1;1H");
}

fn run_simulation(grid: &mut Vec<Vec<bool>>, iterations: usize) {
    for _ in 0..iterations {
        update_grid(grid);
        clear_screen();
        display_grid(grid);
        sleep(std::time::Duration::from_millis(50));
    }
}

fn main() {
    // test_color();
    let width = 80;
    let height = 24;

    let mut grid = vec![vec![false; width]; height];

    randomize_grid(&mut grid);
    display_grid(&grid);
    run_simulation(&mut grid, 1000);
}
