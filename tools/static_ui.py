"""Verified serialized labels outside the game's localization dictionary."""
from __future__ import annotations
import json
import struct
from collections import defaultdict
from pathlib import Path
import UnityPy
import game_versions

ROOT = Path(__file__).resolve().parents[1]


def serialized_value(value):
    return struct.unpack("<f", struct.pack("<f", value))[0] if isinstance(value, float) else value


def entries():
    rows = json.loads((ROOT / "translations/static-ui.json").read_text("utf-8"))
    targets = [(r["source"], r["path_id"]) for r in rows]
    if len(targets) != len(set(targets)):
        raise ValueError("Duplicate static UI target")
    return rows


def grouped(version="1.0.5"):
    groups = defaultdict(list)
    for row in entries():
        groups[game_versions.resolve_bundle(row["source"], version)].append(row)
    return groups


def build(path, rows):
    env = UnityPy.load(str(path))
    objects = {o.path_id: o for o in env.objects}
    for row in rows:
        obj = objects[row["path_id"]]
        data = obj.read_typetree()
        if data.get("m_text") != row["original"]:
            raise ValueError(f"Static UI source changed: {row['path_id']}")
        data["m_text"] = row["korean"]
        for field, change in row.get("layout", {}).items():
            if data[field] != change["original"]:
                raise ValueError(f"Static UI layout changed: {row['path_id']}/{field}")
            data[field] = serialized_value(change["patched"])
        obj.save_typetree(data)
    return env.file.save(packer="lz4")


def verify(original_root, patched_root):
    count = 0
    for rel, rows in grouped(game_versions.detect(original_root)).items():
        original = UnityPy.load(str(original_root / rel))
        patched = UnityPy.load(str(patched_root / rel))
        before = {o.path_id: o for o in original.objects}
        after = {o.path_id: o for o in patched.objects}
        assert before.keys() == after.keys()
        for row in rows:
            expected = before[row["path_id"]].read_typetree()
            assert expected["m_text"] == row["original"]
            expected["m_text"] = row["korean"]
            for field, change in row.get("layout", {}).items():
                assert expected[field] == change["original"]
                expected[field] = serialized_value(change["patched"])
            assert after[row["path_id"]].read_typetree() == expected, row["path_id"]
            count += 1
    return count
