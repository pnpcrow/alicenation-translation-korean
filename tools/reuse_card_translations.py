"""Link identical Japanese card names/descriptions to existing Korean entries."""
from collections import defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
    explicit = {}
    for path in sorted((ROOT / "translations/ko").glob("*.json")):
        explicit.update(json.loads(path.read_text("utf-8")))
    groups = defaultdict(list)
    for key, japanese in source.items():
        if key.startswith("CardInfo_"):
            groups[japanese].append(key)
    aliases = {}
    for japanese, keys in groups.items():
        targets = [key for key in keys if key in explicit]
        if not targets or len({explicit[key] for key in targets}) != 1:
            continue
        target = sorted(targets, key=lambda key: ("_name_" not in key, key))[0]
        for key in keys:
            if key not in explicit:
                aliases[key] = target
    path = ROOT / "translations/aliases.json"
    before = json.loads(path.read_text("utf-8")) if path.exists() else {}
    for key, target in aliases.items():
        if before.get(key) != target:
            print(f"{key} -> {target}: {source[key]}")
    path.write_text(json.dumps(aliases, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Linked {len(aliases)} identical card entries")


if __name__ == "__main__":
    main()
