"""Source-pinned, numbered dialogue batches without altering in-game keys."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def source_rows():
    ja = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
    return [(key, value) for key, value in ja.items() if not re.match(r"^[A-Za-z0-9]+_", key)]


def source_hash(rows):
    canonical = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_dialogue():
    rows = source_rows()
    expected = source_hash(rows)
    result = {}
    for path in sorted((ROOT / "translations/dialogue").glob("*.json")):
        batch = json.loads(path.read_text("utf-8"))
        if batch["source_sha256"] != expected:
            raise ValueError(f"Dialogue source changed: {path.name}")
        start, lines = batch["start"], batch["lines"]
        if type(start) is not int or not isinstance(lines, list) or not lines or start < 0 or start + len(lines) > len(rows):
            raise ValueError(f"Invalid dialogue range: {path.name}")
        for index, line in enumerate(lines, start):
            key = rows[index][0]
            if key in result:
                raise ValueError(f"Overlapping dialogue batch at index {index}")
            result[key] = line
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("start", type=int)
    parser.add_argument("count", type=int, nargs="?", default=100)
    parser.add_argument("--compact", action="store_true", help="Show JA/EN and speaker/scene without repeating source keys")
    args = parser.parse_args()
    rows = source_rows()
    en = json.loads((ROOT / "reference/localization/EN.json").read_text("utf-8"))
    context_path = ROOT / "reference/story/contexts.json"
    contexts = json.loads(context_path.read_text("utf-8")) if context_path.exists() else {}
    print(f"source_sha256: {source_hash(rows)}")
    for index in range(args.start, min(args.start + args.count, len(rows))):
        key, ja = rows[index]
        if args.compact:
            locations = []
            for context in contexts.get(key, []):
                speaker = re.search(r"(?:^| )char:(\S+)", context["content"])
                locations.append(f'{context["script"]}/{context["block"]}:{speaker[1] if speaker else "narrator"}')
            print(json.dumps([index, ja, en[key], locations], ensure_ascii=False))
            continue
        print(json.dumps({"index": index, "ja": ja, "en": en[key],
                          "contexts": contexts.get(key, [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
