use crate::{
    package::{Manifest, Package, PackageSet, hash_file, validate_relative},
    platform,
};
use anyhow::{Context, Result, bail, ensure};
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
};

const STORE: &str = ".alicenation-korean";
const STATE: &str = ".alicenation-korean/state.json";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum Phase {
    Applying,
    Installed,
    Restoring,
    Restored,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct State {
    format: u32,
    phase: Phase,
    manifest: Manifest,
}

impl State {
    fn backup_path(&self, relative: &str) -> String {
        if self.format == 1 {
            format!("{STORE}/backup/{relative}")
        } else {
            format!("{STORE}/backup/{}/{relative}", self.manifest.game_version)
        }
    }
}

pub struct Engine {
    root: PathBuf,
    _lock: File,
}

impl Engine {
    pub fn open(game: &Path) -> Result<Self> {
        platform::reject_link(game)?;
        let root = game
            .canonicalize()
            .context("게임 폴더를 찾을 수 없습니다")?;
        ensure!(
            root.is_dir() && root.join("alicenation.exe").is_file(),
            "alicenation.exe가 있는 게임 폴더를 선택해 주세요"
        );
        platform::reject_link(&root.join(STORE))?;
        fs::create_dir_all(root.join(STORE))
            .context("게임 폴더에 쓸 수 없습니다. 폴더 권한을 확인해 주세요")?;
        let lock_path = root.join(STORE).join("lock");
        platform::reject_link(&lock_path)?;
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(lock_path)?;
        lock.try_lock_exclusive()
            .context("다른 인스톨러가 이 게임 폴더를 사용하고 있습니다")?;
        Ok(Self { root, _lock: lock })
    }

    fn checked(&self, relative: &str) -> Result<PathBuf> {
        validate_relative(relative)?;
        let mut path = self.root.clone();
        for part in relative.split('/') {
            path.push(part);
            platform::reject_link(&path)?;
        }
        Ok(path)
    }

    fn state(&self) -> Result<Option<State>> {
        let path = self.checked(STATE)?;
        if !path.exists() {
            return Ok(None);
        }
        ensure!(
            path.metadata()?.len() <= 1024 * 1024,
            "설치 기록 크기가 올바르지 않습니다"
        );
        let state: State = serde_json::from_slice(&fs::read(path)?)
            .context("설치 기록이 손상되었습니다. 백업 폴더를 보존해 주세요")?;
        ensure!([1, 2].contains(&state.format), "지원하지 않는 설치 기록");
        state.manifest.validate()?;
        Ok(Some(state))
    }

    fn write_state(&self, state: &State) -> Result<()> {
        let path = self.checked(STATE)?;
        let mut temp = tempfile::NamedTempFile::new_in(path.parent().unwrap())?;
        temp.write_all(&serde_json::to_vec_pretty(state)?)?;
        temp.as_file().sync_all()?;
        platform::replace(temp.path(), &path)?;
        Ok(())
    }

    fn verify_guards(&self, manifest: &Manifest) -> Result<()> {
        for guard in &manifest.guards {
            ensure!(
                hash_file(&self.checked(&guard.path)?)? == guard.sha256,
                "게임 {} 원본과 일치하지 않습니다: {}. 다른 버전에는 적용할 수 없습니다",
                manifest.game_version,
                guard.path
            );
        }
        Ok(())
    }

    fn copy_verified(&self, from: &Path, relative: &str, expected: &str) -> Result<()> {
        let path = self.checked(relative)?;
        fs::create_dir_all(path.parent().unwrap())?;
        let mut input = File::open(from)?;
        let mut temp = tempfile::NamedTempFile::new_in(path.parent().unwrap())?;
        std::io::copy(&mut input, &mut temp)?;
        temp.as_file().sync_all()?;
        ensure!(
            hash_file(temp.path())? == expected,
            "복사 중 파일이 변경되었거나 손상되었습니다: {}",
            from.display()
        );
        platform::replace(temp.path(), &path)?;
        Ok(())
    }

    fn stage_path(index: usize) -> String {
        format!("{STORE}/stage/{index:04}.bin")
    }

    pub fn status(&self) -> Result<String> {
        let Some(state) = self.state()? else {
            return Ok("설치 기록 없음".into());
        };
        self.verify_guards(&state.manifest)?;
        let mut original = 0;
        let mut patched = 0;
        let mut changed = 0;
        for row in &state.manifest.files {
            let path = self.checked(&row.path)?;
            let digest = if path.exists() {
                hash_file(&path)?
            } else {
                String::new()
            };
            if digest == row.original_sha256 {
                original += 1;
            } else if digest == row.patched_sha256 {
                patched += 1;
            } else {
                changed += 1;
            }
        }
        let phase = match state.phase {
            Phase::Applying => "설치가 중단됨 · 원상 복구 필요",
            Phase::Restoring => "복구가 중단됨 · 원상 복구 재시도 필요",
            Phase::Installed => "한국어 패치 설치 기록 있음",
            Phase::Restored => "원상 복구 기록 있음",
        };
        Ok(format!(
            "{phase}\n버전: {} / {}\n원본 {original}개, 패치 {patched}개, 변경·누락 {changed}개",
            state.manifest.game_version, state.manifest.patch_version
        ))
    }

    pub fn install(
        &self,
        package: &Package<'_>,
        allow_draft: bool,
        progress: &mut dyn FnMut(&str),
    ) -> Result<()> {
        self.install_with_hook(package, allow_draft, progress, &mut |_| Ok(()))
    }

    pub fn install_available(
        &self,
        packages: &PackageSet<'_>,
        allow_draft: bool,
        progress: &mut dyn FnMut(&str),
    ) -> Result<()> {
        let package = packages.select(&self.root)?;
        progress(&format!(
            "게임 {}를 확인했습니다.",
            package.manifest.game_version
        ));
        self.install(package, allow_draft, progress)
    }

    fn install_with_hook(
        &self,
        package: &Package<'_>,
        allow_draft: bool,
        progress: &mut dyn FnMut(&str),
        before_swap: &mut dyn FnMut(usize) -> Result<()>,
    ) -> Result<()> {
        platform::ensure_game_closed()?;
        let manifest = &package.manifest;
        manifest.validate()?;
        ensure!(
            !manifest.draft || allow_draft,
            "이 패키지는 제작 중인 시험본입니다. 정식 배포본이 아닙니다"
        );
        self.verify_guards(manifest)?;
        if let Some(state) = self.state()? {
            match state.phase {
                Phase::Applying | Phase::Restoring => {
                    bail!("이전 작업이 중단되었습니다. 먼저 원상 복구를 실행해 주세요")
                }
                Phase::Installed => {
                    ensure!(
                        state.manifest == *manifest,
                        "다른 패치가 설치되어 있습니다. 먼저 원상 복구를 실행해 주세요"
                    );
                    for row in &manifest.files {
                        ensure!(
                            hash_file(&self.checked(&row.path)?)? == row.patched_sha256,
                            "설치된 파일이 변경되었습니다: {}",
                            row.path
                        );
                    }
                    progress("같은 한국어 패치가 이미 설치되어 있습니다.");
                    return Ok(());
                }
                Phase::Restored => (),
            }
        }
        let state = State {
            format: 2,
            phase: Phase::Applying,
            manifest: manifest.clone(),
        };
        progress("게임 원본을 검증하고 있습니다.");
        for row in &manifest.files {
            let target = self.checked(&row.path)?;
            ensure!(
                target.metadata()?.len() == row.original_size
                    && hash_file(&target)? == row.original_sha256,
                "원본 파일이 일치하지 않습니다: {}. 게임 버전이나 다른 패치 적용 여부를 확인해 주세요",
                row.path
            );
            let backup = self.checked(&state.backup_path(&row.path))?;
            if backup.exists() {
                ensure!(
                    hash_file(&backup)? == row.original_sha256,
                    "기존 백업이 일치하지 않습니다: {}. 백업을 덮어쓰지 않았습니다",
                    row.path
                );
            }
        }
        let needed: u64 = manifest
            .files
            .iter()
            .map(|r| r.original_size + r.size)
            .sum::<u64>()
            + 32 * 1024 * 1024;
        ensure!(
            fs2::available_space(&self.root)? >= needed,
            "작업 공간이 부족합니다. 최소 {} MB가 필요합니다",
            needed / 1024 / 1024
        );
        for (index, row) in manifest.files.iter().enumerate() {
            progress(&format!(
                "준비 {}/{}: {}",
                index + 1,
                manifest.files.len(),
                row.path
            ));
            let original_path = self.checked(&row.path)?;
            let backup_rel = state.backup_path(&row.path);
            let backup = self.checked(&backup_rel)?;
            if !backup.exists() {
                self.copy_verified(&original_path, &backup_rel, &row.original_sha256)?;
            }
            let source = fs::read(&backup)?;
            ensure!(
                crate::package::hash(&source) == row.original_sha256,
                "백업 파일이 변경되었습니다"
            );
            let patcher = qbsdiff::Bspatch::new(package.delta(index))?;
            ensure!(
                patcher.hint_target_size() == row.size,
                "델타 출력 크기가 일치하지 않습니다"
            );
            let stage = self.checked(&Self::stage_path(index))?;
            fs::create_dir_all(stage.parent().unwrap())?;
            let mut temp = tempfile::NamedTempFile::new_in(stage.parent().unwrap())?;
            // Limit decoded output even for a corrupt delta stream.
            let mut writer = LimitedWriter {
                inner: temp.as_file_mut(),
                remaining: row.size,
            };
            let size = patcher.apply(&source, &mut writer)?;
            ensure!(size == row.size, "패치 출력 크기가 일치하지 않습니다");
            temp.as_file().sync_all()?;
            ensure!(
                hash_file(temp.path())? == row.patched_sha256,
                "패치 결과 검증 실패: {}",
                row.path
            );
            platform::replace(temp.path(), &stage)?;
        }
        // All originals and all generated files are intact before the first game-file write.
        platform::ensure_game_closed()?;
        for row in &manifest.files {
            ensure!(
                hash_file(&self.checked(&row.path)?)? == row.original_sha256,
                "준비 중 게임 파일이 변경되었습니다: {}",
                row.path
            );
        }
        self.write_state(&state)?;
        let commit = (|| -> Result<()> {
            for (index, row) in manifest.files.iter().enumerate() {
                before_swap(index)?;
                ensure!(
                    hash_file(&self.checked(&row.path)?)? == row.original_sha256,
                    "적용 중 원본 파일이 변경되었습니다: {}",
                    row.path
                );
                progress(&format!(
                    "적용 {}/{}: {}",
                    index + 1,
                    manifest.files.len(),
                    row.path
                ));
                platform::replace(
                    &self.checked(&Self::stage_path(index))?,
                    &self.checked(&row.path)?,
                )
                .with_context(|| format!("파일 교체 실패: {}", row.path))?;
                ensure!(
                    hash_file(&self.checked(&row.path)?)? == row.patched_sha256,
                    "적용 후 검증 실패"
                );
            }
            self.write_state(&State {
                phase: Phase::Installed,
                ..state
            })?;
            Ok(())
        })();
        if let Err(error) = commit {
            progress("설치에 실패하여 원본으로 되돌리고 있습니다.");
            match self.restore(progress) {
                Ok(()) => bail!("설치 실패 후 원본 복구를 완료했습니다: {error:#}"),
                Err(recovery) => bail!(
                    "설치 실패: {error:#}\n자동 복구 실패: {recovery:#}\n백업은 보존되어 있습니다. 게임을 닫고 원상 복구를 다시 실행해 주세요"
                ),
            }
        }
        progress("한국어 패치를 적용했습니다. 게임의 언어 설정에서 한국어를 선택해 주세요.");
        Ok(())
    }

    pub fn restore(&self, progress: &mut dyn FnMut(&str)) -> Result<()> {
        platform::ensure_game_closed()?;
        let mut state = self
            .state()?
            .context("설치 기록이 없어 복구할 파일이 없습니다")?;
        self.verify_guards(&state.manifest)?;
        progress("현재 파일과 원본 백업을 검증하고 있습니다.");
        for row in &state.manifest.files {
            ensure!(
                hash_file(&self.checked(&state.backup_path(&row.path))?)? == row.original_sha256,
                "백업 파일이 손상되었습니다: {}. 게임 파일은 변경하지 않았습니다",
                row.path
            );
            let target = self.checked(&row.path)?;
            if target.exists() {
                let current = hash_file(&target)?;
                ensure!(
                    current == row.original_sha256 || current == row.patched_sha256,
                    "패치 이후 변경된 파일이 있어 복구를 중단했습니다: {}. 게임 업데이트 또는 다른 패치를 확인해 주세요",
                    row.path
                );
            }
        }
        let needed: u64 = state
            .manifest
            .files
            .iter()
            .map(|r| r.original_size)
            .sum::<u64>()
            + 16 * 1024 * 1024;
        ensure!(
            fs2::available_space(&self.root)? >= needed,
            "복구를 위한 디스크 공간이 부족합니다"
        );
        for (i, row) in state.manifest.files.iter().enumerate() {
            self.copy_verified(
                &self.checked(&state.backup_path(&row.path))?,
                &Self::stage_path(i),
                &row.original_sha256,
            )?;
        }
        platform::ensure_game_closed()?;
        state.phase = Phase::Restoring;
        self.write_state(&state)?;
        for (i, row) in state.manifest.files.iter().enumerate() {
            progress(&format!(
                "복구 {}/{}: {}",
                i + 1,
                state.manifest.files.len(),
                row.path
            ));
            let target = self.checked(&row.path)?;
            if target.exists() {
                let current = hash_file(&target)?;
                ensure!(
                    current == row.original_sha256 || current == row.patched_sha256,
                    "복구 중 파일이 변경되었습니다: {}",
                    row.path
                );
                if current == row.original_sha256 {
                    continue;
                }
            }
            platform::replace(&self.checked(&Self::stage_path(i))?, &target)?;
            ensure!(
                hash_file(&target)? == row.original_sha256,
                "복구 후 검증 실패: {}",
                row.path
            );
        }
        state.phase = Phase::Restored;
        self.write_state(&state)?;
        progress(
            "원본 복구를 완료했습니다. 원본 백업은 게임 폴더의 .alicenation-korean 폴더에 보관됩니다.",
        );
        Ok(())
    }
}

struct LimitedWriter<'a> {
    inner: &'a mut File,
    remaining: u64,
}
impl Write for LimitedWriter<'_> {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        if buf.len() as u64 > self.remaining {
            return Err(std::io::Error::other("decoded patch exceeds size limit"));
        }
        let n = self.inner.write(buf)?;
        self.remaining -= n as u64;
        Ok(n)
    }
    fn flush(&mut self) -> std::io::Result<()> {
        self.inner.flush()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::package::{self, Guard, PatchFile};

    fn fixture() -> (tempfile::TempDir, Vec<u8>) {
        fixture_for("1.0.5")
    }

    fn fixture_for(version: &str) -> (tempfile::TempDir, Vec<u8>) {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir_all(dir.path().join("alicenation_Data")).unwrap();
        let mut manifest = Manifest {
            format: 1,
            game_version: version.into(),
            patch_version: "v1".into(),
            draft: false,
            guards: vec![],
            files: vec![],
        };
        let guard_data = if version == "1.0.5" {
            b"version fixture".as_slice()
        } else {
            b"version 1.0.6 fixture".as_slice()
        };
        for path in ["alicenation.exe", "alicenation_Data/globalgamemanagers"] {
            fs::write(dir.path().join(path), guard_data).unwrap();
            manifest.guards.push(Guard {
                path: path.into(),
                sha256: package::hash(guard_data),
            });
        }
        let mut payload = Vec::new();
        for path in ["GameAssembly.dll", "alicenation_Data/resources.assets"] {
            let old = if version == "1.0.5" {
                b"Original Japanese language resource".as_slice()
            } else {
                b"Updated Japanese language resource for 1.0.6".as_slice()
            };
            let new = "한국어 번역 리소스 · 원본 복원 검증".as_bytes();
            fs::write(dir.path().join(path), old).unwrap();
            let mut delta = Vec::new();
            qbsdiff::Bsdiff::new(old, new).compare(&mut delta).unwrap();
            manifest.files.push(PatchFile {
                path: path.into(),
                original_sha256: package::hash(old),
                patched_sha256: package::hash(new),
                original_size: old.len() as u64,
                size: new.len() as u64,
                delta_sha256: package::hash(&delta),
                delta_offset: payload.len() as u64,
                delta_size: delta.len() as u64,
            });
            payload.extend(delta);
        }
        (dir, package::encode(&manifest, &payload).unwrap())
    }

    fn check_files(dir: &Path, manifest: &Manifest, patched: bool) {
        for row in &manifest.files {
            assert_eq!(
                hash_file(&dir.join(&row.path)).unwrap(),
                if patched {
                    &row.patched_sha256
                } else {
                    &row.original_sha256
                }
                .to_string()
            );
        }
    }

    #[test]
    fn patch_restore_reinstall_preserves_other_files() {
        let (dir, bytes) = fixture();
        fs::write(dir.path().join("user-save.sav"), b"precious save").unwrap();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        for _ in 0..2 {
            engine.install(&pkg, false, &mut |_| {}).unwrap();
            engine.install(&pkg, false, &mut |_| {}).unwrap();
            check_files(dir.path(), &pkg.manifest, true);
            engine.restore(&mut |_| {}).unwrap();
            check_files(dir.path(), &pkg.manifest, false);
        }
        assert_eq!(
            fs::read(dir.path().join("user-save.sav")).unwrap(),
            b"precious save"
        );
    }

    #[test]
    fn failed_second_swap_rolls_back_first() {
        let (dir, bytes) = fixture();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        let result = engine.install_with_hook(&pkg, false, &mut |_| {}, &mut |i| {
            if i == 1 {
                bail!("simulated access denied");
            }
            Ok(())
        });
        assert!(format!("{:#}", result.unwrap_err()).contains("원본 복구를 완료"));
        check_files(dir.path(), &pkg.manifest, false);
        assert_eq!(engine.state().unwrap().unwrap().phase, Phase::Restored);
    }

    #[test]
    fn interrupted_install_can_restore_without_payload() {
        let (dir, bytes) = fixture();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        engine.install(&pkg, false, &mut |_| {}).unwrap();
        let mut state = engine.state().unwrap().unwrap();
        state.phase = Phase::Applying;
        engine.write_state(&state).unwrap();
        let row = &pkg.manifest.files[0];
        fs::copy(
            engine.checked(&state.backup_path(&row.path)).unwrap(),
            dir.path().join(&row.path),
        )
        .unwrap();
        assert!(engine.install(&pkg, false, &mut |_| {}).is_err());
        drop(engine);
        let engine = Engine::open(dir.path()).unwrap();
        engine.restore(&mut |_| {}).unwrap();
        check_files(dir.path(), &pkg.manifest, false);
    }

    #[test]
    fn wrong_version_and_changed_source_fail_before_mutation() {
        let (dir, bytes) = fixture();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        fs::write(dir.path().join("alicenation.exe"), b"new game version").unwrap();
        assert!(engine.install(&pkg, false, &mut |_| {}).is_err());
        check_files(dir.path(), &pkg.manifest, false);
        fs::write(dir.path().join("alicenation.exe"), b"version fixture").unwrap();
        fs::write(dir.path().join("GameAssembly.dll"), b"other mod").unwrap();
        assert!(engine.install(&pkg, false, &mut |_| {}).is_err());
        assert!(engine.state().unwrap().is_none());
        assert_eq!(
            fs::read(dir.path().join("GameAssembly.dll")).unwrap(),
            b"other mod"
        );
    }

    #[test]
    fn modified_installed_file_and_corrupt_backup_are_preserved() {
        let (dir, bytes) = fixture();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        engine.install(&pkg, false, &mut |_| {}).unwrap();
        let target = dir.path().join("GameAssembly.dll");
        let patched = fs::read(&target).unwrap();
        fs::write(&target, b"updated after patch").unwrap();
        assert!(engine.restore(&mut |_| {}).is_err());
        assert_eq!(fs::read(&target).unwrap(), b"updated after patch");
        fs::write(&target, patched).unwrap();
        fs::write(
            engine
                .checked(
                    &engine
                        .state()
                        .unwrap()
                        .unwrap()
                        .backup_path("GameAssembly.dll"),
                )
                .unwrap(),
            b"broken backup",
        )
        .unwrap();
        assert!(engine.restore(&mut |_| {}).is_err());
        check_files(dir.path(), &pkg.manifest, true);
    }

    #[test]
    fn corrupt_package_and_path_traversal_rejected() {
        let (_, mut bytes) = fixture();
        *bytes.last_mut().unwrap() ^= 1;
        assert!(Package::read(&bytes).is_err());
        for path in [
            "../save.dat",
            "C:/evil",
            "/root",
            "foo\\bar",
            "a//b",
            "file:stream",
            "NUL.txt",
            "a/../b",
            "foo.",
        ] {
            assert!(validate_relative(path).is_err(), "{path}");
        }
    }

    #[test]
    fn lock_prevents_two_installers() {
        let (dir, _) = fixture();
        let _first = Engine::open(dir.path()).unwrap();
        assert!(Engine::open(dir.path()).is_err());
    }

    #[test]
    fn draft_requires_explicit_test_option() {
        let (dir, bytes) = fixture();
        let mut pkg = Package::read(&bytes).unwrap();
        pkg.manifest.draft = true;
        pkg.manifest.patch_version = "v1-draft".into();
        let engine = Engine::open(dir.path()).unwrap();
        assert!(engine.install(&pkg, false, &mut |_| {}).is_err());
        check_files(dir.path(), &pkg.manifest, false);
    }

    #[cfg(windows)]
    #[test]
    fn locked_second_file_rolls_back_without_rewriting_untouched_original() {
        use std::os::windows::fs::OpenOptionsExt;
        let (dir, bytes) = fixture();
        let pkg = Package::read(&bytes).unwrap();
        let engine = Engine::open(dir.path()).unwrap();
        let _locked = OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(dir.path().join("alicenation_Data/resources.assets"))
            .unwrap();
        let error = engine.install(&pkg, false, &mut |_| {}).unwrap_err();
        assert!(format!("{error:#}").contains("원본 복구를 완료"));
        check_files(dir.path(), &pkg.manifest, false);
    }

    #[test]
    fn incorrect_delta_result_does_not_touch_game_files() {
        let (dir, bytes) = fixture();
        let mut pkg = Package::read(&bytes).unwrap();
        pkg.manifest.files[1].patched_sha256 = package::hash(b"wrong expected result");
        let engine = Engine::open(dir.path()).unwrap();
        assert!(engine.install(&pkg, false, &mut |_| {}).is_err());
        check_files(dir.path(), &pkg.manifest, false);
        assert!(engine.state().unwrap().is_none());
    }

    #[test]
    fn version_set_selects_matching_game_and_preserves_old_backups_after_update() {
        let (old_game, old_bytes) = fixture_for("1.0.5");
        let (new_game, new_bytes) = fixture_for("1.0.6");
        let encoded = package::encode_set(&[&old_bytes, &new_bytes]).unwrap();
        let set = PackageSet::read(&encoded).unwrap();
        assert_eq!(
            set.select(old_game.path()).unwrap().manifest.game_version,
            "1.0.5"
        );
        assert_eq!(
            set.select(new_game.path()).unwrap().manifest.game_version,
            "1.0.6"
        );
        let engine = Engine::open(old_game.path()).unwrap();
        engine.install_available(&set, false, &mut |_| {}).unwrap();
        let old_state = engine.state().unwrap().unwrap();
        engine.restore(&mut |_| {}).unwrap();
        // Simulate a game update only after the old patch has been restored.
        let new_pkg = set.select(new_game.path()).unwrap();
        for path in new_pkg
            .manifest
            .guards
            .iter()
            .map(|r| &r.path)
            .chain(new_pkg.manifest.files.iter().map(|r| &r.path))
        {
            fs::copy(new_game.path().join(path), old_game.path().join(path)).unwrap();
        }
        engine.install_available(&set, false, &mut |_| {}).unwrap();
        check_files(old_game.path(), &new_pkg.manifest, true);
        engine.restore(&mut |_| {}).unwrap();
        check_files(old_game.path(), &new_pkg.manifest, false);
        for row in old_state.manifest.files.iter() {
            assert_eq!(
                hash_file(&old_game.path().join(old_state.backup_path(&row.path))).unwrap(),
                row.original_sha256
            );
        }
    }

    #[test]
    fn original_v1_install_record_remains_restorable() {
        let (game, bytes) = fixture();
        let package = Package::read(&bytes).unwrap();
        let engine = Engine::open(game.path()).unwrap();
        engine.install(&package, false, &mut |_| {}).unwrap();
        let modern = engine.state().unwrap().unwrap();
        let legacy = State {
            format: 1,
            ..modern.clone()
        };
        for row in &legacy.manifest.files {
            let from = game.path().join(modern.backup_path(&row.path));
            let to = game.path().join(legacy.backup_path(&row.path));
            fs::create_dir_all(to.parent().unwrap()).unwrap();
            fs::rename(from, to).unwrap();
        }
        engine.write_state(&legacy).unwrap();
        engine.restore(&mut |_| {}).unwrap();
        check_files(game.path(), &package.manifest, false);
    }

    #[test]
    fn version_set_rejects_corruption_duplicate_trailing_and_unknown_game() {
        let (game, a) = fixture_for("1.0.5");
        let (_, b) = fixture_for("1.0.6");
        assert!(package::encode_set(&[&a, &a]).is_err());
        let bytes = package::encode_set(&[&a, &b]).unwrap();
        assert!(PackageSet::read(&bytes[..bytes.len() - 1]).is_err());
        let mut corrupted = bytes.clone();
        *corrupted.last_mut().unwrap() ^= 1;
        assert!(PackageSet::read(&corrupted).is_err());
        let mut trailing = bytes.clone();
        trailing.push(0);
        assert!(PackageSet::read(&trailing).is_err());
        fs::write(
            game.path().join("alicenation_Data/globalgamemanagers"),
            b"unsupported update",
        )
        .unwrap();
        let set = PackageSet::read(&bytes).unwrap();
        let engine = Engine::open(game.path()).unwrap();
        assert!(engine.install_available(&set, false, &mut |_| {}).is_err());
        assert!(engine.state().unwrap().is_none());
        check_files(game.path(), &Package::read(&a).unwrap().manifest, false);
        assert_eq!(PackageSet::read(&a).unwrap().versions(), "1.0.5");
    }
}
