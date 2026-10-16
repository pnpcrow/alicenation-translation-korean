#![cfg_attr(
    all(windows, feature = "gui", not(debug_assertions)),
    windows_subsystem = "windows"
)]

use alicenation_korean::{EMBEDDED, engine::Engine, package::Package};
use anyhow::{Context, Result, bail};
use std::path::PathBuf;

#[cfg(feature = "gui")]
mod gui;

fn run() -> Result<()> {
    let mut args = std::env::args_os().skip(1);
    let Some(command) = args.next() else {
        #[cfg(feature = "gui")]
        return gui::run();
        #[cfg(not(feature = "gui"))]
        bail!(
            "사용법: alicenation-korean <status|patch|restore> --game <게임 폴더> [--package <파일>] [--allow-draft]"
        );
    };
    let mut game = None;
    let mut package_path = None;
    let mut allow_draft = false;
    while let Some(option) = args.next() {
        match option.to_str() {
            Some("--game") => game = Some(PathBuf::from(args.next().context("--game 경로 누락")?)),
            Some("--package") => {
                package_path = Some(PathBuf::from(args.next().context("--package 경로 누락")?))
            }
            Some("--allow-draft") => allow_draft = true,
            _ => bail!("알 수 없는 옵션: {}", option.to_string_lossy()),
        }
    }
    let game = game.context("--game 옵션으로 게임 폴더를 지정해 주세요")?;
    let engine = Engine::open(&game)?;
    match command.to_str() {
        Some("status") => println!("{}", engine.status()?),
        Some("restore") => engine.restore(&mut |s| println!("{s}"))?,
        Some("patch") => {
            let bytes = package_path
                .map(std::fs::read)
                .transpose()?
                .unwrap_or_else(|| EMBEDDED.to_vec());
            let package = Package::read(&bytes)?;
            engine.install(&package, allow_draft, &mut |s| println!("{s}"))?;
        }
        _ => bail!("명령은 status, patch, restore 중 하나여야 합니다"),
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("오류: {error:#}");
        std::process::exit(1);
    }
}
