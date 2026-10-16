"""Read story commands to retain speaker and scene context during translation."""
from collections import defaultdict
import json
from pathlib import Path
import struct
import UnityPy
from extract_localization import read_string, write_string
from inventory import DEFAULT_GAME

ROOT = Path(__file__).resolve().parents[1]


def parse_story(raw):
    name, pos = read_string(raw, 28)
    header = raw[:pos]
    count, = struct.unpack_from("<i", raw, pos)
    pos += 4
    blocks = []
    rebuilt = bytearray(header + struct.pack("<i", count))
    for _ in range(count):
        label, pos = read_string(raw, pos)
        info, pos = read_string(raw, pos)
        lines_count, = struct.unpack_from("<i", raw, pos)
        pos += 4
        rebuilt += write_string(label) + write_string(info) + struct.pack("<i", lines_count)
        lines = []
        for _ in range(lines_count):
            command, pos = read_string(raw, pos)
            content, pos = read_string(raw, pos)
            lines.append({"command": command, "content": content})
            rebuilt += write_string(command) + write_string(content)
        blocks.append({"label": label, "info": info, "lines": lines})
    if pos != len(raw) or rebuilt != raw:
        raise ValueError(f"Story round-trip mismatch: {name}")
    return name, blocks


def main():
    ja = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
    env = UnityPy.load(str(DEFAULT_GAME / "alicenation_Data/resources.assets"))
    contexts = defaultdict(list)
    out = ROOT / "reference/story"
    out.mkdir(parents=True, exist_ok=True)
    scripts = 0
    for obj in env.objects:
        if obj.path_id not in range(1498, 1515):
            continue
        name, blocks = parse_story(obj.get_raw_data())
        (out / (name + ".json")).write_text(json.dumps(blocks, ensure_ascii=False, indent=2), "utf-8")
        scripts += 1
        for block in blocks:
            for line_index, line in enumerate(block["lines"]):
                candidate = line["content"]
                # Parameters precede localized text; consume only complete tokens.
                while candidate:
                    if candidate in ja:
                        contexts[candidate].append({"script": name, "block": block["label"],
                            "line": line_index, "command": line["command"], "content": line["content"]})
                        break
                    _, sep, candidate = candidate.partition(" ")
                    if not sep:
                        break
    (out / "contexts.json").write_text(json.dumps(contexts, ensure_ascii=False, indent=2), "utf-8")
    print(f"{scripts} scripts round-tripped; {len(contexts)} localized texts have scene context")


if __name__ == "__main__":
    main()
