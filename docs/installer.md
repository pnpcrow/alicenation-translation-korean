# Rust 인스톨러 개발 기록

Windows 게임 1.0.5용 한국어 패치 v1이다. 배포 파일은
`dist/Alicenation-1.0.5-Korean-v1.zip`이며 Rust 실행 파일, 사용 안내와 라이선스 고지를 포함한다.
Steam의 현재 1.0.6 설치본에는 이 패치를 적용하지 않는다.

## 기능

- 한국어 GUI: 게임 폴더 선택, 패치 적용, 원상 복구, 상태 확인.
- 원본 실행 파일과 globalgamemanagers 해시로 지원하는 게임 1.0.5를 확인한다.
- 모든 수정 대상의 SHA-256을 검증한 뒤 원본을 백업한다.
- BSDIFF40 델타를 적용하고 결과 해시를 검증한다. 완성된 파일만 게임 폴더로 교체한다.
- 설치·복구 상태를 매번 디스크에 기록하며, 개별 파일은 같은 드라이브에서 원자적으로 교체한다.
- 설치 도중 실패하면 자동으로 원본 복구를 시도한다. 중단된 작업은 다음 실행에서 복구할 수 있다.
- 원상 복구에는 패치 패키지가 필요 없다. 게임 안의 설치 기록과 원본 백업을 사용한다.
- `.alicenation-korean/backup`의 원본을 보존한다. 저장 데이터나 다른 게임 파일을 수정하지 않는다.
- 다른 게임 버전, 변경된 파일, 손상된 백업, 실행 중인 게임, 동시 인스톨러, 경로 이탈을 차단한다.
- 관리자 권한을 자동 요구하지 않는다. 쓰기 권한 오류는 화면에 표시한다.

## 빌드

저장소 루트에서 검증된 1.0.5 원본 사본으로 리소스를 빌드한다.
`reference`의 추출 자료와 `work/inventory.json`, `work/analysis/objects.json`은 로컬 분석 산출물이다.
현재 Steam 설치본을 기본 경로로 사용하면 원본 버전/해시 검사에서 거부된다.

```powershell
python -X utf8 tools/validate_translations.py --complete
python -X utf8 tools/build_patch.py --game work/baseline-1.0.5
python -X utf8 tools/verify_patch.py --game work/baseline-1.0.5
```

인스톨러 폴더에서 델타 생성 도구를 빌드한다.

```powershell
cargo build --release --no-default-features --bin pack-payload
```

`pack-payload <원본 게임 폴더> <패치 폴더> <새 출력 파일.akp>`로 패키지를 만든다.
완성본에는 `--allow-draft`를 사용하지 않는다.
기존 출력 패키지는 덮어쓰지 않으므로 새 출력 이름을 지정한다.

```powershell
target/release/pack-payload.exe ../work/baseline-1.0.5 ../work/patched ../work/alicenation-1.0.5-korean-v1-final.akp
$env:ALICE_PAYLOAD = (Resolve-Path '../work/alicenation-1.0.5-korean-v1-final.akp').Path
cargo build --locked --release --bin alicenation-korean
```

GUI 실행 파일에 델타 패키지와 한국어 글꼴이 포함된다. 별도 런타임 설치는 필요하지 않다.
패키지 없이 빌드하면 복구 전용 개발 화면이 뜬다. 시험본에서는 미완성 표시와 별도 확인란을 표시한다.

CLI 전용 빌드는 `--no-default-features`를 붙인다.

```text
alicenation-korean status --game <폴더>
alicenation-korean patch --game <폴더>
alicenation-korean restore --game <폴더>
```

## 검증

`cargo test --locked`: 실제 파일 교체와 장애 복구를 포함한 10개 테스트.
`cargo clippy --all-targets -- -D warnings`: 경고 없이 통과.
`tools/test_installer.py`: 원본 게임을 복제한 전용 폴더에서 두 차례 설치·복구와 중복 설치 확인.
복구 후 398개 원본 해시 일치, 관계없는 파일 보존, 원래 Steam 설치 폴더 무변경을 확인했다.

최종 델타 패키지는 59,005,336바이트, 실행 파일은 70,506,496바이트다.
`static`으로 페이로드를 공유하며 실행 파일 안에 패키지가 정확히 한 번 들어가는지 확인한다.

게임과 GUI를 종료한 뒤 저장소 루트에서 최종 실행 파일의 내장 패키지를 검사하고 배포한다.

```powershell
python -X utf8 tools/test_installer.py --embedded --exe installer/target/release/alicenation-korean.exe
python -X utf8 tools/package_release.py
```

시험 폴더 `work/installer-qa-game`은 1.0.5 원본 전체와 보존 검사용 파일을 준비해야 한다.
패키저는 기존 배포 폴더를 덮어쓰지 않는다. 재빌드에는 새 `--output` 경로를 지정할 수 있다.

## 구현 참고

[qbsdiff 공식 문서](https://docs.rs/qbsdiff/1.4.4/qbsdiff/)의 BSDIFF40 생성·적용 API를 사용한다.
패키지 및 백업 경로에 포함된 심볼릭 링크·Windows 정션은 허용하지 않는다.
인스톨러의 자체 파일 잠금은 [fs2](https://docs.rs/fs2/0.4.3/fs2/)를 사용한다.
GUI는 eframe/egui 0.33.3, 폴더 선택은 rfd 0.15.4를 사용한다.

배포 ZIP에는 학교안심 그림일기 OFL, GUI 기본 글꼴 고지와 Windows 빌드에 사용한
Rust 의존성 156개 고지를 포함한다. 원본 출처는 `assets/licenses/upstream/sources.json`에 기록했다.
