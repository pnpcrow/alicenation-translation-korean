"""Version-specific source pins; never infer compatibility from file size."""
from pathlib import Path
import hashlib
import json
import UnityPy

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = ("1.0.5", "1.0.6")
FUNCTION_HASHES = {
    "1.0.5": "03c2448e9e4b1002cf2b1fd9874f0698c17236523ed274844e91b1e8bb7e2dd5",
    "1.0.6": "48b71927697242f4e0cecbb86f0ddd9a7309930ea8a3531092867c7511fe1456",
}


def detect(game):
    env = UnityPy.load(str(game / "alicenation_Data/globalgamemanagers"))
    version, = [o.read_typetree()["bundleVersion"] for o in env.objects if o.type.name == "PlayerSettings"]
    if version not in SUPPORTED:
        raise ValueError(f"Unsupported game version: {version}")
    return version


def inventory_path(version):
    if version not in SUPPORTED:
        raise ValueError(version)
    return ROOT / ("work/inventory.json" if version == "1.0.5" else f"work/inventory-{version}.json")


def reference_dir(version):
    if version not in SUPPORTED:
        raise ValueError(version)
    return ROOT / ("reference/localization" if version == "1.0.5" else f"reference/localization-{version}")


def adapt_translations(base, version):
    if version == "1.0.5":
        return base
    if version not in SUPPORTED:
        raise ValueError(version)
    changes = json.loads((ROOT / f"translations/versions/{version}.json").read_text("utf-8"))
    ja = json.loads((reference_dir(version) / "JA.json").read_text("utf-8"))
    cn = json.loads((reference_dir(version) / "CN.json").read_text("utf-8"))
    old_ja = json.loads((reference_dir("1.0.5") / "JA.json").read_text("utf-8"))
    result = dict(base)
    for key in changes["removed"]:
        if key in ja or key not in result:
            raise ValueError(f"Removed key mismatch: {key}")
        del result[key]
    for key, row in changes["added"].items():
        if key in result or ja.get(key) != row["ja"]:
            raise ValueError(f"Added key mismatch: {key}")
        if not row["ja"] and cn.get(key) != row["cn"]:
            raise ValueError(f"Chinese fallback source changed: {key}")
        result[key] = row["ko"]
    for key in old_ja.keys() & ja.keys():
        if old_ja[key] != ja[key]:
            raise ValueError(f"Existing Japanese text changed: {key}")
    return result


def patch_localization_branch(raw, version):
    # Same method RVA in both IL2CPP builds; RIP-relative data references differ.
    if hashlib.sha256(raw[0x51CA20:0x51CAD3]).hexdigest() != FUNCTION_HASHES[version]:
        raise ValueError(f"LocalizationText does not match verified {version} code")
    offset = 0x51CA79
    if raw[offset:offset + 2] != b"\x75\x4a":
        raise ValueError("LocalizationText CN branch mismatch")
    result = bytearray(raw)
    result[offset:offset + 2] = b"\x90\x90"
    return result
