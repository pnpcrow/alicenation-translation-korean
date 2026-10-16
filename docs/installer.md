# Rust 인스톨러 개발 기록

현재는 시험본이다. 전체 번역과 그래픽 검증이 끝난 뒤 v1 배포 파일을 만든다.

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

저장소 루트에서 리소스를 빌드한다. 미번역이 있는 동안은 `--draft`를 붙여야 한다.

```powershell
python -X utf8 tools/build_patch.py --draft
python -X utf8 tools/verify_patch.py
```

인스톨러 폴더에서 델타 생성 도구를 빌드한다.

```powershell
cargo build --release --no-default-features --bin pack-payload
```

`pack-payload <원본 게임 폴더> <패치 폴더> <새 출력 파일.akp> --allow-draft`로
시험 패키지를 만든다. 완성본에는 `--allow-draft`를 사용하지 않는다.
기존 출력 패키지는 덮어쓰지 않으므로 새 출력 이름을 지정한다.

```powershell
$env:ALICE_PAYLOAD = (Resolve-Path '../work/installer-qa-v1-draft.akp').Path
cargo build --release --bin alicenation-korean
```

GUI 실행 파일에 델타 패키지와 한국어 글꼴이 포함된다. 별도 런타임 설치는 필요하지 않다.
패키지 없이 빌드하면 복구 전용 개발 화면이 뜬다. 시험본에서는 미완성 표시와 별도 확인란을 표시한다.

CLI 전용 빌드는 `--no-default-features`를 붙인다.

```text
alicenation-korean status --game <폴더>
alicenation-korean patch --game <폴더> --package <파일.akp> --allow-draft
alicenation-korean restore --game <폴더>
```

## 검증

`cargo test --no-default-features`: 실제 파일 교체와 장애 복구를 포함한 10개 테스트.
`cargo clippy --all-targets -- -D warnings`: 경고 없이 통과.
`tools/test_installer.py`: 원본 게임을 복제한 전용 폴더에서 두 차례 설치·복구와 중복 설치 확인.
복구 후 398개 원본 해시 일치, 관계없는 파일 보존, 원래 Steam 설치 폴더 무변경을 확인했다.

1,755개 번역을 담은 첫 시험 델타 패키지는 24,932,136바이트다. 정식 배포 크기는 달라진다.

## 구현 참고

[qbsdiff 공식 문서](https://docs.rs/qbsdiff/1.4.4/qbsdiff/)의 BSDIFF40 생성·적용 API를 사용한다.
패키지 및 백업 경로에 포함된 심볼릭 링크·Windows 정션은 허용하지 않는다.
인스톨러의 자체 파일 잠금은 [fs2](https://docs.rs/fs2/0.4.3/fs2/)를 사용한다.
GUI는 eframe/egui 0.33.3, 폴더 선택은 rfd 0.15.4를 사용한다.

최종 배포 시 폰트 OFL 및 Rust 의존성 고지를 함께 포함해야 한다.
