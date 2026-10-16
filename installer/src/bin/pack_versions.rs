use alicenation_korean::package::{self, PackageSet};
use anyhow::{Result, ensure};
use std::{fs, io::Write, path::PathBuf};

fn main() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    ensure!(
        args.len() == 3,
        "usage: pack-versions <1.0.5.akp> <1.0.6.akp> <output.akp>"
    );
    let first = fs::read(PathBuf::from(&args[0]))?;
    let second = fs::read(PathBuf::from(&args[1]))?;
    let combined = package::encode_set(&[&first, &second])?;
    let set = PackageSet::read(&combined)?;
    ensure!(!set.is_draft(), "draft payloads cannot be released");
    let mut output = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(PathBuf::from(&args[2]))?;
    output.write_all(&combined)?;
    output.sync_all()?;
    println!(
        "Versions: {}, bytes: {}, SHA-256: {}",
        set.versions(),
        combined.len(),
        package::hash(&combined)
    );
    Ok(())
}
