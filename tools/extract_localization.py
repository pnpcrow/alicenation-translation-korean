"""Extract the game's length-prefixed, aligned localization tables losslessly."""
from __future__ import annotations
import collections
import json
import re
import struct
from pathlib import Path
import UnityPy
from inventory import DEFAULT_GAME

def read_string(raw: bytes, pos: int) -> tuple[str, int]:
    length, = struct.unpack_from("<i", raw, pos)
    if length < 0 or pos + 4 + length > len(raw):
        raise ValueError(f"Invalid string length {length} at {pos}")
    end = pos + 4 + length
    return raw[pos + 4:end].decode("utf-8"), (end + 3) & ~3

def write_string(text: str) -> bytes:
    value = text.encode("utf-8")
    data = struct.pack("<i", len(value)) + value
    return data + bytes((-len(data)) % 4)

def parse_table(raw: bytes) -> tuple[bytes, list[tuple[str, str]]]:
    name, pos = read_string(raw, 28)
    if not name.startswith("LocalizationConfig_"):
        raise ValueError(name)
    header = raw[:pos]
    count, = struct.unpack_from("<i", raw, pos)
    pos += 4
    rows = []
    for _ in range(count):
        key, pos = read_string(raw, pos)
        value, pos = read_string(raw, pos)
        rows.append((key, value))
    if pos != len(raw):
        raise ValueError(f"Unparsed tail: {len(raw) - pos}")
    return header, rows

def build_table(header: bytes, rows: list[tuple[str, str]]) -> bytes:
    return header + struct.pack("<i", len(rows)) + b"".join(write_string(k) + write_string(v) for k, v in rows)

def main() -> None:
    out = Path("reference/localization")
    out.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(DEFAULT_GAME / "alicenation_Data/resources.assets"))
    langs = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        data = obj.read_typetree(check_read=False)
        name = data.get("m_Name", "")
        if name.startswith("LocalizationConfig_"):
            raw = obj.get_raw_data()
            header, rows = parse_table(raw)
            assert build_table(header, rows) == raw, "Round-trip differs"
            lang = name.removeprefix("LocalizationConfig_")
            langs[lang] = dict(rows)
            assert len(langs[lang]) == len(rows), "Duplicate keys"
            (out / f"{lang}.json").write_text(json.dumps(dict(rows), ensure_ascii=False, indent=2), encoding="utf-8")
            print(lang, obj.path_id, len(rows), sum(len(v) for _, v in rows), "characters")
    groups = collections.defaultdict(list)
    for key, ja in langs["JA"].items():
        group = key.split("_")[0] if re.match(r"^[A-Za-z0-9]+_", key) else "Dialogue"
        groups[group].append({"key": key, "ja": ja, "en": langs["EN"].get(key), "zh_hans": langs["CN"].get(key), "zh_hant": langs["CN_TC"].get(key)})
    for group, rows in groups.items():
        (out / f"compare_{group}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: len(v) for k, v in groups.items()}, ensure_ascii=False))

if __name__ == "__main__":
    main()
