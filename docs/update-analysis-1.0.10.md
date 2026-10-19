# 2026-10-19: 게임 1.0.10 업데이트 분석

Steam 설치본의 PlayerSettings.bundleVersion은 1.0.10이다. 빌드 ID는 26040541,
Windows depot은 3755351, manifest는 5542513449152500638이다.
`tools/steam_baseline.py`로 Steam manifest의 크기·SHA-1에 맞는 파일만 모아
`work/baseline-1.0.10` 사본과 `work/inventory-1.0.10.json`을 만들었다.
400개 파일, 총 667,186,859바이트를 검증했다. 기존 패치가 남은 23개 파일은
현재 manifest와 정확히 일치하는 원본 백업에서 사본으로 가져왔다.

## 텍스트와 그래픽

JA/EN/CN_TC 각각 7,436개, CN 1,635개이며 네 표 모두 추출·재조립 바이트가 동일하다.
1.0.9 대비 일본어 키 1개 추가·1개 삭제·공통 항목 1개 수정이다.

- 이변체(ASPEnemy): 피안의 현상에서 태어났다는 설명 및 받는 정신 피해 감소를 반영했다.
  `<b>` 강조를 보존하고 영어·중국어의 의미와 대조했다.
- Chapter3_2/script1_1의 Supervisor 대사: 세계수 아래 얼어붙은 영혼과 육체에 관한
  삭제된 내용을 한국어에서도 제거했다. 기존 ‘해요냥’ 말투를 유지했다.

원본 변경은 GameAssembly.dll, metadata, resources.assets, globalgamemanagers,
boot.config, Addressables catalog와 퀘스트 보상 창 번들이다. 보상 창의 객체 ID,
직렬화 텍스트 및 텍스처에는 변경이 없으며, 번역 대상 그래픽도 전부 이전과 같다.
새 번들을 원본 그대로 보존하고 현재 catalog를 기준으로 패치 CRC를 갱신한다.
374개 Unity 리소스의 분석 오류는 0개다.

실행 코드의 새 문자열 `FireflyFox`는 내부 카드 식별자이며 원본의 이름·설명·별칭 키가
이미 존재한다. 한글화 대상의 새 화면 문구가 아니다.

## 실행 코드

현재 GameAssembly와 metadata를 함께 Il2CppDumper로 분석했다. CN에서 키를 반환하고
다른 언어에서 표를 조회하는 LocalizationText의 제어 흐름은 유지되지만 코드 해시는 바뀌었다.

- RVA `0x51E9F0`, 파일 위치 `0x51D3F0`, 검사 길이 `0xB3`
- CN 분기 파일 위치 `0x51D449`, 원본 바이트 `75 4A`
- 함수 SHA-256 `cc982d62da5c95cae4debd8e558568eb5ecd79d247342ad70d6a74ec0182fad5`

번역은 1.0.9를 기준으로 원문을 고정한 별도 파일로 관리하여 이전 릴리즈의 번역을 보존한다.
최종 빌드·설치·복구·화면 검수 결과는 [검증 기록](qa.md)에 기록한다.
