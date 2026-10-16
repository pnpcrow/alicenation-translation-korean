"""Check key coverage, placeholders, markup, and Japanese leftovers."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def placeholders(text):
    return Counter(re.findall(r"\{\d+(?:[^{}]*)\}", text))

def tags(text):
    return Counter(re.findall(r"</?[^<>]+>|\[br\]", text))

def validate(ja, translated):
    fixes_path = ROOT / "translations/markup_fixes.json"
    fixes = json.loads(fixes_path.read_text("utf-8")) if fixes_path.exists() else {}
    problems = []
    for key, ko in translated.items():
        if key not in ja:
            problems.append(f"Unknown key: {key}")
            continue
        if not isinstance(ko, str) or not ko.strip():
            problems.append(f"Empty or non-string translation: {key}")
            continue
        if placeholders(ko) != placeholders(ja[key]):
            problems.append(f"Placeholder mismatch: {key}")
        expected = tags(ja[key])
        if key in fixes:
            fix = fixes[key]
            if expected != Counter(fix["original_tags"]):
                problems.append(f"Markup correction source changed: {key}")
            expected = Counter(fix["corrected_tags"])
        if tags(ko) != expected:
            problems.append(f"Markup mismatch: {key}")
        if re.search(r"[\u3041-\u3096\u30a1-\u30fa\u30fc-\u30ff]", ko):
            problems.append(f"Japanese remains: {key}")
    return problems


def main():
    from build_patch import load_translations
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    ja = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
    translated = load_translations()
    problems = validate(ja, translated)
    missing = sorted(ja.keys() - translated.keys())
    if args.complete and missing:
        problems.append(f"Untranslated: {len(missing)}")
    print(json.dumps({"translated": len(translated), "total": len(ja), "missing": len(missing), "problems": problems}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
