# 리소스 조사 기록

## 확인한 버전과 구조

- `PlayerSettings.bundleVersion`: `1.0.5`
- Unity IL2CPP, metadata v31. 게임 설치 파일 398개, 총 650,352,652바이트.
- Addressables 번들 370개. SHA-256 원본 목록: `work/inventory.json`.
- `resources.assets`의 LocalizationConfig 테이블은 4바이트 정렬 UTF-8 key/value 문자열 배열이다.
- 일본어·영어·번체 각각 7,410항목, 간체 1,632항목. 일본어 179,539자.
- 그룹: CardInfo 1,033 / CardBuffInfo 188 / EventInfo 79 / CommandInfo 88 / Label 100 / TaskInfo 94 / Scan 8 / Dialogue 5,780 / HelpInfo 40.
- 중국어 원문 자체를 키로 사용하는 대사 5,780개는 키를 변경하지 않아야 한다.
- 각 언어 테이블의 추출→재직렬화 결과가 원본 바이트와 동일함을 확인했다.

## 간체 슬롯 대사 분기

`LocalizationManager.LocalizationText`는 CurrentLanguage가 CN이면 번역표를 조회하지 않고 원문 키를 반환한다.
RVA `0x51D879`의 `jne`를 통과시키는 최소 수정과 전체 한국어 CN 테이블이 필요하다.
`ApplyLanguage`는 CN을 포함하여 `Datas/LocalizationConfig_{language}`를 정상 로드한다.
패치 시 원본 SHA-256과 해당 명령 바이트를 모두 검증해야 한다.

## 글꼴과 그림

- WinkySans SDF → Lolita SDF → OPPOSans-MSDF 폴백 연결.
- 동적 TMP 글꼴이므로 한글 소스 폰트와 초기 글리프 테이블/아틀라스의 일관성을 맞춰야 한다.
- 타이틀은 Title_CN/Title_CN_TC/Title_EN/Title_JA 별도 이미지.
- Help1~Help10은 중국어 텍스트가 구워진 1280×720 스크린샷.
- 다른 삽화와 아틀라스에도 문자 포함 여부를 전수 확인해야 한다.

## 제작 도구 출처

- [UnityPy](https://github.com/K0lb3/UnityPy), 로컬 설치 1.25.3
- [Il2CppDumper](https://github.com/Perfare/Il2CppDumper/releases/tag/v6.7.46), 읽기 전용 구조 분석
- [학교안심 그림일기](https://copyright.keris.or.kr/wft/fntDwnldView?fntGrpId=GFT202408200000000000001), 사용자 제공 TTF 원본, KERIS / 헤움디자인, SIL OFL 1.1 (라이선스 동봉). 현대 한글 11,172자 지원을 cmap으로 확인했다.

## 후속 결과

1.0.5의 전체 번역·그래픽·인스톨러 제작과 주요 화면 검증을 완료했다.
상세 결과와 전체 분기 플레이 검수의 한계는 `qa.md`에 기록했다.

## 1.0.6 호환성 조사

Steam build 25993259, `PlayerSettings.bundleVersion` 1.0.6.
설치 파일 398개, 650,296,412바이트를 `work/baseline-1.0.6`에 고정하고 해시를 기록했다.
기존 경로 8개가 변경/교체되었다. 리소스·카탈로그·코드·글꼴과 선택창 두 번들이 바뀌었다.
선택창의 텍스트와 객체 ID는 이전과 같으며 기존 동적 번역을 사용한다.
텍스트가 구워진 그림은 추가 변경이 없어 검증된 image_gen 결과를 재사용한다.

일본어 표는 7,417항목이다. 오타가 있던 중국어 대사 키 1개가 제거되고 수정 키 1개,
새 대사 5개, TaskCommon 이름·설명 2개가 추가되었다. 공통 키의 일본어 본문은 동일하다.
TaskCommon은 일본어·영어·번체가 비어 있어 중국어 ‘任务系统模板’를 참고했다.
새 대사는 CardMeet/ChapterHelp의 화자와 맥락을 대조했으며,
번역 및 원문 검증 조건은 `translations/versions/1.0.6.json`에 기록했다.

LocalizationText의 함수와 분기는 이전 RVA를 유지한다. RIP 상대 데이터 참조가 달라
함수 전체 바이트 SHA-256을 버전별로 별도 고정하고, CN 원문 반환 분기의 2바이트만 바꾼다.
TMP Settings의 전체 300바이트는 이전과 같으며 한국어 줄바꿈 설정을 동일하게 적용한다.
업데이트된 게임 설정과 이야기 스크립트, 다른 언어 표는 원본 바이트를 보존하는지 검사한다.
