# 2026-10-18 업데이트 사전 분석

사용자는 1.0.8 지원을 요청했으나 현재 Steam 설치본의 PlayerSettings.bundleVersion은
1.0.9다. Steam 빌드 ID는 26025095, Windows depot은 3755351,
manifest는 2064559544390181286이다. 로컬에는 1.0.5·1.0.6 원본과 현재 설치본만
있으며, 캐시된 depot manifest도 1.0.6과 현재 버전 두 개뿐이다.
사용자가 최종적으로 1.0.9만 지원하도록 범위를 확정했다. 1.0.8은 원본을 확보하지
못했으므로 호환성을 주장하거나 해당 버전용 릴리즈를 만들지 않는다.

## 원본 확보

현재 설치본에는 이전 1.0.6 패치 상태 기록과 업데이트되지 않은 패치 파일이 남아 있다.
전체 복구는 1.0.9의 새 게임 파일까지 예전 버전으로 되돌릴 수 있으므로 수행하지 않았다.
`tools/steam_baseline.py`로 설치 파일 또는 기존 백업 중 현재 Steam manifest의
크기·SHA-1과 정확히 일치하는 파일만 선택해 외부 분석 사본을 만들었다.

- 원본 파일 400개, 합계 667,186,497바이트: Steam manifest와 일치
- 이 중 21개는 1.0.6 원본 백업에서 해시가 일치하는 파일을 복사
- 사본: `work/baseline-1.0.9`
- SHA-1·SHA-256 목록 및 출처: `work/inventory-1.0.9.json`
- Steam 설치본과 사용자 저장 데이터는 변경하지 않음

manifest 판독은 [ContentManifest 스키마](https://github.com/SteamTracking/Protobufs/blob/master/steam/content_manifest.proto)와
[SteamKit의 DepotManifest 구현](https://github.com/SteamRE/SteamKit/blob/master/SteamKit2/SteamKit2/Types/DepotManifest.cs)을 참고했다.
설치 파일 또는 백업에 정확한 원본이 없으면 사본 생성을 거부한다.

## 텍스트와 그래픽 차이

현재 일본어·영어·중국어 번체 표는 각각 7,436항목이다. 중국어 간체 표는
대사 키 자체를 원문으로 쓰므로 1,635항목만 수록되어 있다. 네 표 모두 원본 바이트와
추출 후 재조립 결과가 같음을 확인했다.

1.0.6의 일본어 표 대비 22항목 추가, 3항목 삭제, 공통 항목 5개 수정이다.
수정은 Dream5 카드 설명, 임시 보관 제한, 경보기 증거 설명, AspToDo 특성,
데이터 사용 안내이며, 추가 문구에는 다음 장 이동 시 미완료 서브퀘스트 종료 안내와
추리 선택지·피난 안내 등이 포함된다. 새 대사의 화자·분기 문맥도 추출했다.

기존 한글화 그래픽의 원본은 변경되지 않았다. 달라진 IconAtlas를 시각적으로 확인했으며
아이콘·숫자·기호로 구성되어 있어 새 번역 대상 문구는 없다. 공용 UI 번들에 추가된
두 `保存进度` 텍스트는 모두 `Label_Load`를 사용하는 LocalizationText 컴포넌트가 있어
실행 시 기존 번역표의 불러오기 문구로 대체된다. 정적 UI 번역 90개를 새 번들에
다시 적용할 때 원문과 레이아웃을 별도로 검증해야 한다.

현재 분석 결과는 `work/asset-changes-1.0.9.json`, `work/new-text-1.0.9.json`,
`work/new-contexts-1.0.9.json`, `work/analysis-1.0.9/objects.json`에 보관했다.

## 실행 코드 차이

Il2CppDumper로 현재 실행 코드와 metadata를 함께 분석했다. LocalizationText는 여전히
CN에서 키를 그대로 반환하며, 다른 언어는 번역표를 조회한다. 함수의 RVA와 파일 위치는
이전 버전과 달라졌으므로 1.0.5·1.0.6의 패치 위치를 그대로 사용할 수 없다.

- 함수 RVA: `0x51E9F0`, 원본 코드 길이: `0xB3`
- 함수 파일 위치: `0x51D3F0`
- CN 분기 파일 위치: `0x51D449`, 원본 바이트: `75 4A`
- 원본 함수 SHA-256: `449d373593173e7fe6400d9b12f3e7edddb7386b837d391aeb1b36ddef7e62f1`

분석 도구에 원본 경로·출력 경로·metadata 경로 인자를 추가했다. 이 기록은 사전 분석이며,
아직 1.0.9 패치 빌드·실행 검증·배포를 완료했다는 뜻은 아니다.
