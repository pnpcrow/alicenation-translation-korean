# Rust 인스톨러

## 현재 배포: 게임 1.0.10 / v1 r2 로고 수정판 / 인스톨러 1.2.1

게임 안에서 로고를 잘라내던 Sprite 메시와 textureRect를 수정했다. 로고 이미지의
픽셀, 사각 영역·피벗·배율, 다른 언어 로고는 유지한다. 인스톨러 엔진은 바꾸지 않았다.
패키지 내부 형식·패치 버전은 v1을 유지하며, r2는 배포 리비전이다. 설치 기록의
전체 매니페스트가 다르므로 기존 v1에 덮어쓰기를 거부하며 먼저 원상 복구해야 한다.
수정 인스톨러로 기존 v1의 복구와 r2의 설치·복구를 모두 실행할 수 있다.

아래의 v1 빌드 명령에서 작업 경로를 `work/patched-1.0.10-r2`,
`work/alicenation-1.0.10-korean-v1-r2.akp`로 바꾸고 출력 폴더는
`dist/releases/Alicenation-1.0.10-Korean-v1-r2`로 지정한다. 사용 안내는 다음으로 만든다.

```powershell
python -X utf8 tools/version_release_readme.py 1.0.10 work/public-readme-1.0.10-r2.txt --revision r2
```

`verify_patch.py`는 텍스처뿐 아니라 Sprite로 디코딩한 전체 픽셀과 메시·UV도 검사한다.
기존 잘린 로고는 이 검사를 통과하지 못한다. 자세한 내용은 [로고 수정 기록](title-clipping.md)에 있다.

## 이전 배포: 게임 1.0.10 / v1 / 인스톨러 1.2.1

1.0.10 전용 패치와 7,436개 번역을 담는다. 이변체의 정신 피해 감소 설명 및
짧아진 대사를 반영하며 새 게임 원본과 실행 코드의 해시를 별도로 검증한다.
이전 1.0.5·1.0.6·1.0.9 배포 파일은 변경하지 않았다. 설치·복구 엔진의 동작은
1.2.0과 같으며, 1.0.10 지원과 1.0.9→1.0.10 업데이트 시험을 추가했다.

```powershell
python -X utf8 tools/validate_translations.py --complete --version 1.0.10
python -X utf8 tools/build_patch.py --game work/baseline-1.0.10 --output work/patched-1.0.10
python -X utf8 tools/verify_patch.py --game work/baseline-1.0.10 --patch work/patched-1.0.10
cargo test --manifest-path installer/Cargo.toml --locked
cargo clippy --manifest-path installer/Cargo.toml --locked --all-targets -- -D warnings
cargo build --manifest-path installer/Cargo.toml --locked --release --no-default-features --bin pack-payload
installer/target/release/pack-payload.exe work/baseline-1.0.10 work/patched-1.0.10 work/alicenation-1.0.10-korean-v1.akp
$env:ALICE_PAYLOAD = (Resolve-Path 'work/alicenation-1.0.10-korean-v1.akp').Path
cargo build --manifest-path installer/Cargo.toml --locked --release --bin alicenation-korean
python -X utf8 tools/version_release_readme.py 1.0.10 work/public-readme-1.0.10.txt
python -X utf8 tools/package_release.py --patch work/patched-1.0.10 --payload work/alicenation-1.0.10-korean-v1.akp --readme work/public-readme-1.0.10.txt --output dist/releases/Alicenation-1.0.10-Korean-v1
```

[1.0.10 분석 기록](update-analysis-1.0.10.md)과 `work/analysis-1.0.10/objects.json`을
사용한다. 출력 파일·폴더가 없을 때 위 명령을 실행한다. 15개 Rust 테스트는
1.0.9→1.0.10의 원본 확인, 잔존 패치 거부, 이전 기록·백업 보존, 복구를 포함한다.

## 이전 배포: 게임 1.0.9 / 인스톨러 1.2.0

1.0.9 전용 패치 데이터와 7,436개 번역을 포함한다. 이전 1.0.5·1.0.6 공개 배포 파일은
변경하지 않았다. 1.0.8은 사용자의 최종 요청에 따라 지원 대상에서 제외했다.

1.2.0은 이전 버전의 설치 기록이 남아 있어도 새 원본과 버전 검증 파일이 전부 맞으면
설치를 허용한다. 기존 기록은 `.alicenation-korean/history/<기록 SHA-256>.json`에
보관하고 원본 백업은 버전별 경로에 보존한다. 이전 패치 파일이 남아 있으면 덮어쓰기를
거부하며 Steam 무결성 검사를 안내한다. 중단된 설치·복구 기록은 기존대로 복구가 필요하다.

```powershell
python -X utf8 tools/validate_translations.py --complete --version 1.0.9
python -X utf8 tools/build_patch.py --game work/baseline-1.0.9 --output work/patched-1.0.9
python -X utf8 tools/verify_patch.py --game work/baseline-1.0.9 --patch work/patched-1.0.9
cargo test --manifest-path installer/Cargo.toml --locked
cargo clippy --manifest-path installer/Cargo.toml --locked --all-targets -- -D warnings
cargo build --manifest-path installer/Cargo.toml --locked --release --no-default-features --bin pack-payload
installer/target/release/pack-payload.exe work/baseline-1.0.9 work/patched-1.0.9 work/alicenation-1.0.9-korean-v1.akp
$env:ALICE_PAYLOAD = (Resolve-Path 'work/alicenation-1.0.9-korean-v1.akp').Path
cargo build --manifest-path installer/Cargo.toml --locked --release --bin alicenation-korean
python -X utf8 tools/version_release_readme.py 1.0.9 work/public-readme-1.0.9.txt
python -X utf8 tools/package_release.py --patch work/patched-1.0.9 --payload work/alicenation-1.0.9-korean-v1.akp --readme work/public-readme-1.0.9.txt --output dist/releases/Alicenation-1.0.9-Korean-v1
```

원본 확보는 [업데이트 분석](update-analysis-1.0.9.md)을 참고한다. 1.0.9는 별도의
객체 목록 `work/analysis-1.0.9/objects.json`을 사용하며, 이름이 달라진 번들도 객체 ID,
원문, 레이아웃을 다시 확인한 뒤 수정한다. 일본어 변경은 이전 버전을 기준으로 한
추가·삭제·수정 목록을 정확히 대조한다. 실행 코드 위치와 함수 해시는 버전마다 고정한다.

14개 Rust 테스트에는 Steam 업데이트 후 남은 이전 패치 파일의 적용 거부,
새 원본 검증 후 설치, 이전 기록·백업 보존, 1.0.9 원상 복구가 포함된다.

## 이전 배포: 게임 1.0.5·1.0.6 / 인스톨러 1.1.0

게임 1.0.5와 1.0.6을 지원하는 한국어 패치 v1, 인스톨러 버전 1.1.0이다.
`dist/Alicenation-1.0.5-1.0.6-Korean-v1.zip`에 실행 파일·사용 안내·라이선스 고지를 담는다.
기존 1.0.5 전용 ZIP과 그 안의 실행 파일은 그대로 보존한다.

## 설치와 복구

한국어 GUI에서 게임 폴더를 고르고 패치 적용·원상 복구·상태 확인을 실행한다.
실행 파일과 globalgamemanagers의 SHA-256으로 버전을 판별한다. 각 버전의 모든 수정
대상을 다시 검사하고, 백업과 델타 결과를 검증한 뒤 같은 드라이브에서 원자적으로 교체한다.
설치 도중 실패하면 자동 복구를 시도하며, 중단된 기록은 다음 실행에서 복구할 수 있다.

통합 인스톨러의 백업 경로는 `.alicenation-korean/backup/<게임 버전>/...`이다.
설치 기록 형식 2가 이 경로를 사용한다. 기존 v1의 형식 1 기록도 읽으며,
그 백업은 기존 `.alicenation-korean/backup/...`에서 찾는다.
복구에는 내장 패치 데이터가 필요 없다. 설치 기록과 검증된 백업만 사용한다.
통합판으로 설치한 패치는 통합판으로 복구해야 한다.

게임 업데이트 전 먼저 복구한다. 업데이트 후 새 버전용 패치를 적용하면 이전 버전의
백업은 그대로 보존한다. 패치된 상태에서 게임 파일이 업데이트되면 원본 덮어쓰기를
거부한다. 손상된 백업, 경로 이탈·정션, 실행 중인 게임, 동시 인스톨러도 차단한다.
저장 데이터는 변경하지 않으며 관리자 권한을 자동 요구하지 않는다.

## 리소스 재빌드

로컬 원본 목록은 `work/inventory.json`(1.0.5), `work/inventory-1.0.6.json`이다.
일본어 비교 자료는 `reference/localization`, `reference/localization-1.0.6`에 있다.
공통 리소스 객체 목록은 `work/analysis/objects.json`을 사용한다. 바뀐 폰트 번들은
각 버전의 원본 목록에서 찾으며, 새 번역은 원문을 고정한 버전별 추가 파일로 관리한다.

```powershell
python -X utf8 tools/validate_translations.py --complete --version 1.0.5
python -X utf8 tools/validate_translations.py --complete --version 1.0.6
python -X utf8 tools/build_patch.py --game work/baseline-1.0.6 --output work/patched-1.0.6
python -X utf8 tools/verify_patch.py --game work/baseline-1.0.6 --patch work/patched-1.0.6
```

1.0.5도 같은 명령에서 원본·출력 경로를 지정하여 빌드할 수 있다. 통합 배포에는
기존 최종 1.0.5 패키지를 바이트 그대로 포함하여 이전 설치와 호환한다.

## Rust 빌드와 패키징

인스톨러 디렉터리에서 실행한다. 출력 `.akp`는 덮어쓰지 않으므로 재생성 시 새 이름을 쓴다.

```powershell
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
cargo build --locked --release --no-default-features --bin pack-payload --bin pack_versions
target/release/pack-payload.exe ../work/baseline-1.0.6 ../work/patched-1.0.6 ../work/alicenation-1.0.6-korean-v1.akp
target/release/pack_versions.exe ../work/alicenation-1.0.5-korean-v1-final.akp ../work/alicenation-1.0.6-korean-v1.akp ../work/alicenation-1.0.5-1.0.6-korean-v1.akp
$env:ALICE_PAYLOAD = (Resolve-Path '../work/alicenation-1.0.5-1.0.6-korean-v1.akp').Path
cargo build --locked --release --bin alicenation-korean
```

각 버전은 기존 ALICKO1/BSDIFF40 형식으로 독립 검증한다. ALICKO2는 길이가 명시된
두 패키지를 보관한다. 중복 버전, 잘린 데이터, 뒤에 붙은 내용, 잘못된 델타 해시를 거부한다.
코드의 `static` 데이터로 내장하여 불필요한 페이로드 복제를 피한다.

저장소 루트에서 `python -X utf8 tools/package_release.py`로 ZIP을 만든다.
패키저는 실행 파일에 정확한 통합 데이터가 한 번 들어 있고 각 버전의 파일 목록·해시가
리소스 빌드와 일치하는지 확인한다. 기존 배포 폴더는 덮어쓰지 않는다.

```text
Alicenation-Korean-v1.exe status --game <폴더>
Alicenation-Korean-v1.exe patch --game <폴더>
Alicenation-Korean-v1.exe restore --game <폴더>
```

## 검증과 의존성

13개 Rust 테스트에 실패 시 롤백, 잠금, 손상 데이터, 미지원 버전, 버전 자동 선택,
업데이트 전후 백업 보존, 기존 형식 1 복구를 포함한다.
`tools/test_installer.py`는 전용 사본에서 두 차례 설치·중복 설치·복구를 수행한다.
`--game`, `--patch`, `--inventory`, `--report`로 버전을 지정하며 `--embedded`로
배포 실행 파일의 내장 데이터를 테스트한다. `--legacy-exe`로 이전 인스톨러 복구도 검사한다.

GUI는 eframe/egui 0.33.3, 폴더 선택은 rfd 0.15.4, 델타는 qbsdiff 1.4.4를 사용한다.
배포 ZIP에는 학교안심 그림일기 OFL, GUI 기본 글꼴 고지와 Windows 빌드에 사용한
Rust 의존성 156개 고지를 포함한다. 출처는 `assets/licenses/upstream/sources.json`에 있다.

## 공개 릴리즈용 버전별 패키지

공개 릴리즈 `v1-game-1.0.5`, `v1-game-1.0.6`에는 인스톨러 1.1.0과 해당 버전의
ALICKO1 패키지만 포함한다. 게임 리소스는 앞서 검증한 통합판과 동일하다.
각 실행 파일의 내장 데이터가 하나의 버전만 지원하므로 다른 버전의 원본에는 적용하지 않는다.

다음은 저장소 루트에서 실행하는 1.0.6용 예시다. 출력 폴더·파일이 없을 때 실행한다.
1.0.5용은 `work/alicenation-1.0.5-korean-v1-final.akp`, `work/patched`를 사용한다.

```powershell
$env:ALICE_PAYLOAD = (Resolve-Path 'work/alicenation-1.0.6-korean-v1.akp').Path
cargo build --manifest-path installer/Cargo.toml --locked --release --bin alicenation-korean
python -X utf8 tools/version_release_readme.py 1.0.6 work/public-readme-1.0.6.txt
python -X utf8 tools/package_release.py --patch work/patched-1.0.6 --payload work/alicenation-1.0.6-korean-v1.akp --readme work/public-readme-1.0.6.txt --output dist/releases/Alicenation-1.0.6-Korean-v1
```

다른 버전용 빌드 전에 실행 파일을 별도 경로에 보관하고 `--exe`로 지정할 수도 있다.
공개 ZIP의 실행 파일로 `test_installer.py`를 실행해 검증한다. 초기 1.0.5 전용
인스톨러 복구를 시험할 때는 format 2 설치 기록이 없는 새 게임 사본을 사용한다.
Windows의 긴 경로 제한을 피하려면 검증 사본 경로를 짧게 잡는다.

공개 ZIP과 릴리즈 설명에는 GPT Astra를 사용한 AI 번역이라는 사실을 명시한다.
GitHub 릴리즈 설명 원본은 `docs/releases/`에 보관하며 ZIP과 `.sha256`을 첨부한다.

## 1.0.10 Steam 빌드 26075487

인스톨러 1.2.2는 `1.0.10-b26075487`을 별도 지원 프로필로 추가한다.
실행 파일과 bundleVersion은 이전 1.0.10과 같지만 globalgamemanagers의 해시가 달라
정확히 구분할 수 있다. 새 백업은 `backup/1.0.10-b26075487/`에 보관하며 이전
`backup/1.0.10/`을 덮어쓰지 않는다. 16번째 Rust 테스트는 이 업데이트 경로를 검증한다.

```powershell
cargo build --manifest-path installer/Cargo.toml --locked --release --no-default-features --bin pack-payload
installer/target/release/pack-payload.exe work/b26075487 work/p26075487 work/alicenation-b26075487-v1.akp
$env:ALICE_PAYLOAD = (Resolve-Path 'work/alicenation-b26075487-v1.akp').Path
cargo build --manifest-path installer/Cargo.toml --locked --release --bin alicenation-korean
python -X utf8 tools/version_release_readme.py 1.0.10-b26075487 work/readme-26075487.txt
python -X utf8 tools/package_release.py --patch work/p26075487 --payload work/alicenation-b26075487-v1.akp --readme work/readme-26075487.txt --output dist/releases/Alicenation-1.0.10-b26075487-Korean-v1
```

출력 경로가 이미 있으면 새 경로를 지정한다. 자세한 원본·번역 변경은
[빌드 분석 기록](update-26075487.md)을 참고한다.

## 1.0.10 Steam 빌드 26123177

인스톨러 1.2.3은 `1.0.10-b26123177`을 추가한다. 기존 두 검증 파일에
`alicenation_Data/StreamingAssets/aa/settings.json`을 추가해 실행 파일·버전 파일이
같은 콘텐츠 업데이트도 구분한다. 새 프로필은 세 파일이 모두 필수이며, 파일별
원본 해시 검사도 그대로 유지한다. 백업은 `backup/1.0.10-b26123177/`에 보관한다.
기존 두 검증 파일을 사용하는 설치 기록도 계속 읽고 복구할 수 있다.

```powershell
cargo build --manifest-path installer/Cargo.toml --locked --release --no-default-features --bin pack-payload
installer/target/release/pack-payload.exe work/b26123177 work/p26123177 work/alicenation-b26123177-v1.akp
$env:ALICE_PAYLOAD = (Resolve-Path 'work/alicenation-b26123177-v1.akp').Path
cargo build --manifest-path installer/Cargo.toml --locked --release --bin alicenation-korean
python -X utf8 tools/version_release_readme.py 1.0.10-b26123177 work/readme-26123177.txt
python -X utf8 tools/package_release.py --patch work/p26123177 --payload work/alicenation-b26123177-v1.akp --readme work/readme-26123177.txt --output dist/releases/Alicenation-1.0.10-b26123177-Korean-v1
```

18개 Rust 테스트에는 콘텐츠 업데이트 선택 순서, 추가 검증 파일 누락·중복,
설정 파일 변경 후 설치·복구 거부, 이전 형식 백업 보존을 포함한다.
원본 구성·E2E 도구는 Windows 확장 경로로 긴 빌드별 백업 경로를 읽는다.
분석·리소스 빌드 명령은 [이번 빌드 기록](update-26123177.md)을 참고한다.
