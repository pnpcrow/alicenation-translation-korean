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
- [Gowun Dodum](https://github.com/google/fonts/tree/main/ofl/gowundodum), SIL OFL (라이선스 파일 동봉)

## 미완료

전체 번역, 그래픽 전수 점검·번역, 폰트 표시, 실제 게임 QA, 패치/복구 인스톨러, v1 배포.
