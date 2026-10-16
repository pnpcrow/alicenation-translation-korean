"""Prepare version-specific instructions for public release packages."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('version', choices=('1.0.5', '1.0.6'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    text = (ROOT / 'docs/release-readme.txt').read_text('utf-8')
    replacements = {
        'Windows 1.0.5 / 1.0.6': f'Windows {args.version} 전용',
        '게임 1.0.5와 1.0.6의 검증된 원본에 적용합니다.': f'게임 {args.version}의 검증된 원본에 적용합니다.',
        '일본어 기준 텍스트 7,410항목(1.0.5) / 7,417항목(1.0.6)':
            f"일본어 기준 텍스트 {'7,410' if args.version == '1.0.5' else '7,417'}항목",
        '통합 인스톨러로': '인스톨러 1.1.0으로',
        '통합 인스톨러': '인스톨러 1.1.0',
    }
    if args.version == '1.0.5':
        replacements['1.0.6의 템플릿 이름·설명 두 항목은 일본어가 비어 있어 중국어 원문을 참고했습니다.\n'] = ''
    for old, new in replacements.items():
        assert old in text, f'Instructions template changed: {old}'
        text = text.replace(old, new)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


if __name__ == '__main__':
    main()
