"""Bridge verified story key corrections missing from the source language tables."""
import json
from pathlib import Path
import game_versions
from extract_story import parse_story

ROOT = Path(__file__).resolve().parents[1]


def entries(version):
    if version not in game_versions.SUPPORTED:
        raise ValueError(version)
    if version == "1.0.5":
        return []
    overlay = json.loads((ROOT / f"translations/versions/{version}.json").read_text("utf-8"))
    return overlay.get("runtime_aliases", [])


def resolve(version, translated):
    ja = json.loads((game_versions.reference_dir(version) / "JA.json").read_text("utf-8"))
    result = {}
    for row in entries(version):
        key, target = row["key"], row["target"]
        if key in ja or key in translated or key in result:
            raise ValueError(f"Runtime alias collides with an existing key: {key}")
        if not row["ja"] or ja.get(target) != row["ja"] or target not in translated:
            raise ValueError(f"Runtime alias source changed or untranslated: {target}")
        result[key] = translated[target]
    return result


def verify_sources(objects, version):
    for row in entries(version):
        name, blocks = parse_story(objects[row["object_id"]].get_raw_data())
        matches = [b for b in blocks if b["label"] == row["block"]]
        if name != row["script"] or len(matches) != 1:
            raise ValueError("Runtime alias story location changed")
        line = matches[0]["lines"][row["line"]]
        if line != {"command": row["command"], "content": row["prefix"] + row["key"]}:
            raise ValueError("Runtime alias story command changed")
