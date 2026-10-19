"""Prepare version-specific instructions for public release packages."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', choices=('1.0.5', '1.0.6', '1.0.9', '1.0.10'))
    parser.add_argument('output', type=Path)
    parser.add_argument('--revision', choices=('r2',), help='1.0.10 title-sprite correction')
    args = parser.parse_args()
    text = (ROOT / 'docs/release-readme.txt').read_text('utf-8')
    replacements = {
        'Windows 1.0.5 / 1.0.6': f'Windows {args.version} 전용',
        '게임 1.0.5와 1.0.6의 검증된 원본에 적용합니다.': f'게임 {args.version}의 검증된 원본에 적용합니다.',
        '일본어 기준 텍스트 7,410항목(1.0.5) / 7,417항목(1.0.6)':
            f"일본어 기준 텍스트 {dict(zip(('1.0.5', '1.0.6', '1.0.9', '1.0.10'), ('7,410', '7,417', '7,436', '7,436')))[args.version]}항목",
        '통합 인스톨러로': '인스톨러 1.1.0으로',
        '통합 인스톨러': '인스톨러 1.1.0',
    }
    if args.version == '1.0.5':
        replacements['1.0.6의 템플릿 이름·설명 두 항목은 일본어가 비어 있어 중국어 원문을 참고했습니다.\n'] = ''
    for old, new in replacements.items():
        assert old in text, f'Instructions template changed: {old}'
        text = text.replace(old, new)
    if args.version in ('1.0.9', '1.0.10'):
        text = text.replace('인스톨러 1.1.0', '인스톨러 1.2.0')
        text = text.replace('1.0.6의 템플릿', '템플릿')
        text = text.replace('Steam 파일 무결성 검사로 새 버전 원본을 확보하고 기존 백업을 보존한 채 상태를 확인하세요.',
            'Steam에서 게임 속성 → 설치된 파일 → 게임 파일 무결성 확인을 실행한 뒤 이 인스톨러를 적용하세요.\n'
            '새 버전 원본이 모두 확인되면 이전 설치 기록은 history에, 이전 백업은 기존 위치에 보존합니다.\n'
            '1.0.8은 검증하지 않았으며 이 배포판의 지원 대상이 아닙니다.')
    if args.version == '1.0.10':
        text = text.replace('인스톨러 1.2.0', '인스톨러 1.2.1')
    if args.revision:
        if args.version != '1.0.10':
            parser.error('r2 is only published for game 1.0.10')
        text = text.replace('한국어 패치 v1\n', '한국어 패치 v1 — 로고 수정판 r2\n', 1)
        text = text.replace('설치\n1.',
            'r2 변경 사항\n'
            '메인 화면에서 한글 로고가 잘리는 문제를 수정했습니다. 그림은 그대로 유지하고\n'
            '중국어 로고 윤곽을 따라 잘라내던 표시 영역만 바꾸었습니다.\n\n'
            '기존 1.0.10 v1에서 업데이트\n'
            '게임을 종료하고 이 인스톨러에서 [원상 복구]를 먼저 실행한 뒤\n'
            '[한국어 패치 적용]을 누르세요. 기존 패치 위에 바로 덮어쓰지는 않습니다.\n\n'
            '설치\n1.', 1)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


if __name__ == '__main__':
    main()
