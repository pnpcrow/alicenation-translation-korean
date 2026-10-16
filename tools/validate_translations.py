"""Check key coverage, placeholders, markup, and Japanese leftovers."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from build_patch import load_translations

def placeholders(text):
    return Counter(re.findall(r"\{\d+(?:[^{}]*)\}", text))

def tags(text):
    return Counter(re.findall(r"</?[^<>]+>|\[br\]", text))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", action="store_true")
    args = parser.parse_args()
    ja = json.loads(Path("reference/localization/JA.json").read_text("utf-8"))
    translated = load_translations()
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
        if tags(ko) != tags(ja[key]):
            problems.append(f"Markup mismatch: {key}")
        if re.search(r"[\u3041-\u3096\u30a1-\u30fa\u30fc-\u30ff]", ko):
            problems.append(f"Japanese remains: {key}")
    missing = sorted(ja.keys() - translated.keys())
    if args.complete and missing:
        problems.append(f"Untranslated: {len(missing)}")
    print(json.dumps({"translated": len(translated), "total": len(ja), "missing": len(missing), "problems": problems}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
