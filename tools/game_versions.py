"""Version-specific source pins; never infer compatibility from file size."""
from pathlib import Path
import hashlib
import json
import re
import UnityPy

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = ("1.0.5", "1.0.6", "1.0.9", "1.0.10", "1.0.10-b26075487", "1.0.10-b26123177")
# Steam can publish different content without changing bundleVersion.
BUILD_IDENTITIES = {
    "1.0.10": {
        "b279c11c1d3a4ff01942a52e4fe56013db0c3a1481b3d588e29dc28b00c30565": "1.0.10",
        "1e40fc19fb6bda399b8f778913c1c5fd2c549ef459f41325fd334ecb99818d05": "1.0.10-b26075487",
    }
}
# Content-only updates can also retain the same globalgamemanagers file.
CONTENT_BUILD_IDENTITIES = {
    "1.0.10-b26075487": {
        "419c934fb56bd1815d8aa65b8825603d0f5c865aa3344402e13aadaee446d99a": "1.0.10-b26075487",
        "02a720f4e431be900805d95bc0b0ce7970f99f98be3a30b69e8b6bd296b97998": "1.0.10-b26123177",
    }
}
FUNCTION_HASHES = {
    "1.0.5": "03c2448e9e4b1002cf2b1fd9874f0698c17236523ed274844e91b1e8bb7e2dd5",
    "1.0.6": "48b71927697242f4e0cecbb86f0ddd9a7309930ea8a3531092867c7511fe1456",
    "1.0.9": "449d373593173e7fe6400d9b12f3e7edddb7386b837d391aeb1b36ddef7e62f1",
    "1.0.10": "cc982d62da5c95cae4debd8e558568eb5ecd79d247342ad70d6a74ec0182fad5",
    "1.0.10-b26075487": "0dac98c594a2b814aa3bcf3ca595abeaa4454397e8e7d40650c39c4f2d3111a8",
    "1.0.10-b26123177": "0dac98c594a2b814aa3bcf3ca595abeaa4454397e8e7d40650c39c4f2d3111a8",
}
FUNCTION_OFFSETS = {"1.0.5": 0x51CA20, "1.0.6": 0x51CA20, "1.0.9": 0x51D3F0, "1.0.10": 0x51D3F0}
FUNCTION_OFFSETS["1.0.10-b26075487"] = 0x51CC50
FUNCTION_OFFSETS["1.0.10-b26123177"] = 0x51CC50


def detect(game):
    env = UnityPy.load(str(game / "alicenation_Data/globalgamemanagers"))
    version, = [o.read_typetree()["bundleVersion"] for o in env.objects if o.type.name == "PlayerSettings"]
    if version in BUILD_IDENTITIES:
        fingerprint = hashlib.sha256((game / "alicenation_Data/globalgamemanagers").read_bytes()).hexdigest()
        profile = BUILD_IDENTITIES[version].get(fingerprint)
        if profile is None:
            raise ValueError(f"Unverified build for game {version}: {fingerprint}")
        if profile in CONTENT_BUILD_IDENTITIES:
            settings = hashlib.sha256((game / "alicenation_Data/StreamingAssets/aa/settings.json").read_bytes()).hexdigest()
            profile = CONTENT_BUILD_IDENTITIES[profile].get(settings)
            if profile is None:
                raise ValueError(f"Unverified content build for game {version}: {settings}")
        return profile
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


def object_index_path(version):
    if version not in SUPPORTED:
        raise ValueError(version)
    return ROOT / ("work/analysis/objects.json" if version in ("1.0.5", "1.0.6") else f"work/analysis-{version}/objects.json")


def resolve_bundle(relative, version):
    """Resolve a renamed Addressables bundle, retaining object/text/layout checks."""
    paths = {r["path"] for r in json.loads(inventory_path(version).read_text("utf-8"))["files"]}
    if relative in paths:
        return relative
    normalize = lambda p: re.sub(r"_[0-9a-f]{32}\.bundle$", ".bundle", p)
    matches = [p for p in paths if normalize(p) == normalize(relative)]
    if len(matches) != 1:
        raise ValueError(f"No unique {version} bundle for {relative}: {matches}")
    return matches[0]


def adapt_translations(base, version):
    if version == "1.0.5":
        return base
    if version not in SUPPORTED:
        raise ValueError(version)
    changes = json.loads((ROOT / f"translations/versions/{version}.json").read_text("utf-8"))
    ja = json.loads((reference_dir(version) / "JA.json").read_text("utf-8"))
    cn = json.loads((reference_dir(version) / "CN.json").read_text("utf-8"))
    parent = changes["base_version"]
    if parent not in SUPPORTED[:SUPPORTED.index(version)]:
        raise ValueError(f"Invalid translation base: {parent}")
    old_ja = json.loads((reference_dir(parent) / "JA.json").read_text("utf-8"))
    result = dict(adapt_translations(base, parent))
    expected_removed = old_ja.keys() - ja.keys()
    expected_added = ja.keys() - old_ja.keys()
    expected_changed = {k for k in old_ja.keys() & ja.keys() if old_ja[k] != ja[k]}
    if (set(changes["removed"]) != expected_removed or set(changes["added"]) != expected_added
            or set(changes.get("changed", {})) != expected_changed):
        raise ValueError(f"Translation overlay does not match {parent} -> {version} source changes")
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
    for key, row in changes.get("changed", {}).items():
        if old_ja[key] != row["previous_ja"] or ja[key] != row["ja"]:
            raise ValueError(f"Changed Japanese source mismatch: {key}")
        result[key] = row["ko"]
    return result


def patch_localization_branch(raw, version):
    start = FUNCTION_OFFSETS[version]
    if hashlib.sha256(raw[start:start + 0xB3]).hexdigest() != FUNCTION_HASHES[version]:
        raise ValueError(f"LocalizationText does not match verified {version} code")
    offset = start + 0x59
    if raw[offset:offset + 2] != b"\x75\x4a":
        raise ValueError("LocalizationText CN branch mismatch")
    result = bytearray(raw)
    result[offset:offset + 2] = b"\x90\x90"
    return result
