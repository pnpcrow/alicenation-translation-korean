use alicenation_korean::package::{self, Guard, Manifest, PatchFile};
use anyhow::{Context, Result, ensure};
use serde::Deserialize;
use std::{fs, io::Write, path::PathBuf};

#[derive(Deserialize)]
struct BuildFile {
    path: String,
    original_sha256: String,
    patched_sha256: String,
    size: u64,
}
#[derive(Deserialize)]
struct Build {
    game_version: String,
    patch_version: String,
    translated: usize,
    total: usize,
    missing: usize,
    tutorial: Tutorial,
    files: Vec<BuildFile>,
}

#[derive(Deserialize)]
struct Tutorial {
    total: usize,
    translated: usize,
    preserved: usize,
    pending: usize,
}

fn main() -> Result<()> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    ensure!(
        args.len() == 3 || (args.len() == 4 && args[3] == "--allow-draft"),
        "usage: pack-payload <original game> <patched directory> <output.akp> [--allow-draft]"
    );
    let game = PathBuf::from(&args[0]);
    let patched = PathBuf::from(&args[1]);
    let output = PathBuf::from(&args[2]);
    ensure!(
        !output.exists(),
        "output already exists; choose a new package path"
    );
    let build: Build = serde_json::from_slice(&fs::read(patched.join("manifest.json"))?)?;
    let draft = build.missing != 0 || build.tutorial.pending != 0;
    ensure!(
        !draft || args.len() == 4,
        "incomplete text or tutorial graphics; release package refused"
    );
    let expected = match build.game_version.as_str() {
        "1.0.5" => 7410,
        "1.0.6" => 7417,
        "1.0.9" => 7436,
        "1.0.10" => 7436,
        _ => anyhow::bail!("unsupported game version"),
    };
    ensure!(
        build.translated + build.missing == build.total && build.total == expected,
        "translation count mismatch"
    );
    ensure!(
        build.tutorial.total == 52
            && build.tutorial.translated + build.tutorial.preserved + build.tutorial.pending == 52,
        "tutorial coverage count mismatch"
    );
    ensure!(
        build.patch_version == if draft { "v1-draft" } else { "v1" },
        "patch version mismatch"
    );
    let mut manifest = Manifest {
        format: 1,
        game_version: build.game_version,
        patch_version: build.patch_version,
        draft,
        guards: Vec::new(),
        files: Vec::new(),
    };
    for path in ["alicenation.exe", "alicenation_Data/globalgamemanagers"] {
        manifest.guards.push(Guard {
            path: path.into(),
            sha256: package::hash_file(&game.join(path))?,
        });
    }
    let mut payload = Vec::new();
    for (i, file) in build.files.iter().enumerate() {
        package::validate_relative(&file.path)?;
        let original = fs::read(game.join(&file.path))?;
        let target = fs::read(patched.join(&file.path))?;
        ensure!(
            package::hash(&original) == file.original_sha256,
            "source mismatch: {}",
            file.path
        );
        ensure!(
            package::hash(&target) == file.patched_sha256 && target.len() as u64 == file.size,
            "target mismatch: {}",
            file.path
        );
        let mut delta = Vec::new();
        qbsdiff::Bsdiff::new(&original, &target).compare(&mut delta)?;
        let mut verify = Vec::new();
        qbsdiff::Bspatch::new(&delta)?.apply(&original, &mut verify)?;
        ensure!(verify == target, "delta roundtrip mismatch");
        println!(
            "{}/{} {} -> {} bytes: {}",
            i + 1,
            build.files.len(),
            target.len(),
            delta.len(),
            file.path
        );
        std::io::stdout().flush()?;
        manifest.files.push(PatchFile {
            path: file.path.clone(),
            original_sha256: file.original_sha256.clone(),
            patched_sha256: file.patched_sha256.clone(),
            original_size: original.len() as u64,
            size: target.len() as u64,
            delta_sha256: package::hash(&delta),
            delta_offset: payload.len() as u64,
            delta_size: delta.len() as u64,
        });
        payload.extend(delta);
    }
    let encoded = package::encode(&manifest, &payload)?;
    fs::create_dir_all(output.parent().context("output parent missing")?)?;
    let mut out = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&output)?;
    out.write_all(&encoded)?;
    out.sync_all()?;
    println!(
        "Written {} bytes, SHA-256 {}",
        encoded.len(),
        package::hash(&encoded)
    );
    Ok(())
}
