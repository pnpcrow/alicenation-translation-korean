use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    fs::File,
    io::Read,
    path::Path,
};

pub const MAGIC: &[u8; 8] = b"ALICKO1\n";
const SET_MAGIC: &[u8; 8] = b"ALICKO2\n";
pub const MAX_FILE: u64 = 1024 * 1024 * 1024;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Guard {
    pub path: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct PatchFile {
    pub path: String,
    pub original_sha256: String,
    pub patched_sha256: String,
    pub original_size: u64,
    pub size: u64,
    pub delta_sha256: String,
    pub delta_offset: u64,
    pub delta_size: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub format: u32,
    pub game_version: String,
    pub patch_version: String,
    pub draft: bool,
    pub guards: Vec<Guard>,
    pub files: Vec<PatchFile>,
}

pub fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn hash_file(path: &Path) -> Result<String> {
    let mut file =
        File::open(path).with_context(|| format!("파일을 열 수 없습니다: {}", path.display()))?;
    let mut digest = Sha256::new();
    let mut buffer = [0u8; 1024 * 64];
    loop {
        let n = file.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        digest.update(&buffer[..n]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

pub fn validate_relative(path: &str) -> Result<()> {
    ensure!(!path.is_empty() && path.len() < 240, "잘못된 파일 경로");
    for part in path.split('/') {
        ensure!(
            !part.is_empty() && part != "." && part != "..",
            "잘못된 파일 경로: {path}"
        );
        ensure!(
            part.bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"._-".contains(&b)),
            "허용하지 않는 파일 경로: {path}"
        );
        ensure!(!part.ends_with('.'), "잘못된 파일 경로: {path}");
        let stem = part.split('.').next().unwrap().to_ascii_uppercase();
        ensure!(
            ![
                "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7",
                "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8",
                "LPT9"
            ]
            .contains(&stem.as_str()),
            "예약된 파일 이름: {path}"
        );
    }
    Ok(())
}

fn valid_hash(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

impl Manifest {
    pub fn validate(&self) -> Result<()> {
        ensure!(
            self.format == 1
                && ["1.0.5", "1.0.6", "1.0.9", "1.0.10", "1.0.10-b26075487"]
                    .contains(&self.game_version.as_str()),
            "지원하지 않는 패치 형식 또는 게임 버전"
        );
        ensure!(
            self.patch_version == if self.draft { "v1-draft" } else { "v1" },
            "잘못된 패치 버전"
        );
        ensure!(
            !self.files.is_empty() && self.files.len() <= 400,
            "잘못된 파일 목록"
        );
        let mut seen = HashSet::new();
        let mut offset = 0;
        for row in &self.files {
            validate_relative(&row.path)?;
            let allowed = row.path == "GameAssembly.dll"
                || row.path == "alicenation_Data/resources.assets"
                || row.path == "alicenation_Data/StreamingAssets/aa/catalog.json"
                || (row
                    .path
                    .starts_with("alicenation_Data/StreamingAssets/aa/StandaloneWindows64/")
                    && row.path.ends_with(".bundle"));
            ensure!(allowed, "패치 대상이 아닌 파일: {}", row.path);
            ensure!(
                seen.insert(row.path.to_ascii_lowercase()),
                "중복된 파일: {}",
                row.path
            );
            ensure!(
                valid_hash(&row.original_sha256)
                    && valid_hash(&row.patched_sha256)
                    && valid_hash(&row.delta_sha256),
                "잘못된 파일 해시"
            );
            ensure!(
                row.size > 0
                    && row.size <= MAX_FILE
                    && row.original_size <= MAX_FILE
                    && row.delta_size <= MAX_FILE,
                "파일 크기 제한 초과"
            );
            ensure!(row.delta_offset == offset, "잘못된 델타 위치");
            offset = offset
                .checked_add(row.delta_size)
                .context("델타 크기 초과")?;
        }
        ensure!(offset <= 2 * MAX_FILE, "패키지 크기 제한 초과");
        ensure!(self.guards.len() == 2, "버전 검증 파일이 누락되었습니다");
        let guards: HashSet<_> = self.guards.iter().map(|g| g.path.as_str()).collect();
        ensure!(
            guards == HashSet::from(["alicenation.exe", "alicenation_Data/globalgamemanagers"]),
            "잘못된 버전 검증 목록"
        );
        ensure!(
            self.guards.iter().all(|g| valid_hash(&g.sha256)),
            "잘못된 버전 검증 해시"
        );
        Ok(())
    }
}

pub struct Package<'a> {
    pub manifest: Manifest,
    data: &'a [u8],
}

impl<'a> Package<'a> {
    pub fn read(bytes: &'a [u8]) -> Result<Self> {
        ensure!(
            bytes.len() >= 16 && &bytes[..8] == MAGIC,
            "패치 데이터가 없거나 손상되었습니다"
        );
        let len = u64::from_le_bytes(bytes[8..16].try_into().unwrap());
        ensure!(
            len <= 1024 * 1024 && len <= (bytes.len() - 16) as u64,
            "패치 목록이 손상되었습니다"
        );
        let end = 16 + len as usize;
        let manifest: Manifest =
            serde_json::from_slice(&bytes[16..end]).context("패치 목록을 읽을 수 없습니다")?;
        manifest.validate()?;
        let data = &bytes[end..];
        let last = manifest.files.last().unwrap();
        ensure!(
            last.delta_offset + last.delta_size == data.len() as u64,
            "패치 데이터 길이가 일치하지 않습니다"
        );
        let result = Self { manifest, data };
        for i in 0..result.manifest.files.len() {
            ensure!(
                hash(result.delta(i)) == result.manifest.files[i].delta_sha256,
                "패치 데이터가 손상되었습니다: {}",
                result.manifest.files[i].path
            );
        }
        Ok(result)
    }

    pub fn delta(&self, index: usize) -> &[u8] {
        let row = &self.manifest.files[index];
        &self.data[row.delta_offset as usize..(row.delta_offset + row.delta_size) as usize]
    }
}

pub fn encode(manifest: &Manifest, data: &[u8]) -> Result<Vec<u8>> {
    manifest.validate()?;
    let json = serde_json::to_vec(manifest)?;
    let mut out = Vec::with_capacity(16 + json.len() + data.len());
    out.extend_from_slice(MAGIC);
    out.extend_from_slice(&(json.len() as u64).to_le_bytes());
    out.extend_from_slice(&json);
    out.extend_from_slice(data);
    if Package::read(&out).is_err() {
        bail!("생성한 패키지가 검증을 통과하지 못했습니다");
    }
    Ok(out)
}

/// A version set retains the independently verified v1 payload format.
/// Legacy single-version payloads are accepted without conversion.
pub struct PackageSet<'a> {
    pub packages: Vec<Package<'a>>,
}

impl<'a> PackageSet<'a> {
    pub fn read(bytes: &'a [u8]) -> Result<Self> {
        if bytes.starts_with(MAGIC) {
            return Ok(Self {
                packages: vec![Package::read(bytes)?],
            });
        }
        ensure!(
            bytes.len() >= 16 && bytes.starts_with(SET_MAGIC),
            "패치 데이터가 없거나 손상되었습니다"
        );
        let count = u64::from_le_bytes(bytes[8..16].try_into().unwrap());
        ensure!((1..=2).contains(&count), "잘못된 게임 버전 목록");
        let mut cursor = 16;
        let mut packages = Vec::new();
        let mut versions = HashSet::new();
        for _ in 0..count {
            ensure!(
                bytes.len() - cursor >= 8,
                "패치 데이터 길이가 손상되었습니다"
            );
            let size = u64::from_le_bytes(bytes[cursor..cursor + 8].try_into().unwrap());
            cursor += 8;
            ensure!(
                size <= 2 * MAX_FILE && size <= (bytes.len() - cursor) as u64,
                "패치 데이터 길이가 손상되었습니다"
            );
            let end = cursor + size as usize;
            let package = Package::read(&bytes[cursor..end])?;
            ensure!(
                versions.insert(package.manifest.game_version.clone()),
                "중복된 게임 버전"
            );
            packages.push(package);
            cursor = end;
        }
        ensure!(
            cursor == bytes.len(),
            "패치 데이터 뒤에 알 수 없는 내용이 있습니다"
        );
        Ok(Self { packages })
    }

    pub fn versions(&self) -> String {
        self.packages
            .iter()
            .map(|p| p.manifest.game_version.as_str())
            .collect::<Vec<_>>()
            .join(" / ")
    }

    pub fn is_draft(&self) -> bool {
        self.packages.iter().any(|p| p.manifest.draft)
    }

    pub fn select(&self, game: &Path) -> Result<&Package<'a>> {
        let mut hashes = HashMap::new();
        let mut matched = None;
        for package in &self.packages {
            let mut matches = true;
            for guard in &package.manifest.guards {
                if !hashes.contains_key(&guard.path) {
                    hashes.insert(guard.path.clone(), hash_file(&game.join(&guard.path))?);
                }
                matches &= hashes[&guard.path] == guard.sha256;
            }
            if matches {
                ensure!(matched.is_none(), "게임 버전을 명확히 판별할 수 없습니다");
                matched = Some(package);
            }
        }
        matched.with_context(|| format!("지원하는 게임 원본과 일치하지 않습니다. 지원 버전: {}. 게임 버전과 파일 변경 여부를 확인해 주세요", self.versions()))
    }
}

pub fn encode_set(packages: &[&[u8]]) -> Result<Vec<u8>> {
    ensure!((1..=2).contains(&packages.len()), "잘못된 게임 버전 목록");
    let mut out = Vec::new();
    out.extend_from_slice(SET_MAGIC);
    out.extend_from_slice(&(packages.len() as u64).to_le_bytes());
    for bytes in packages {
        out.extend_from_slice(&(bytes.len() as u64).to_le_bytes());
        out.extend_from_slice(bytes);
    }
    PackageSet::read(&out)?;
    Ok(out)
}
