"""Read back serialized patch assets, image pixels and Addressables CRC metadata."""
from __future__ import annotations
import argparse
import base64
import json
import struct
from pathlib import Path
import UnityPy
from PIL import Image
from addressables import bundle_crc
from build_patch import ROOT, load_translations
from extract_localization import parse_table
from inventory import digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", type=Path, default=ROOT / "work/patched")
    args = parser.parse_args()
    manifest = json.loads((args.patch / "manifest.json").read_text("utf-8"))
    for row in manifest["files"]:
        path = args.patch / row["path"]
        assert path.stat().st_size == row["size"], row["path"]
        assert digest(path) == row["patched_sha256"], row["path"]
    env = UnityPy.load(str(args.patch / "alicenation_Data/resources.assets"))
    objects = {o.path_id: o for o in env.objects}
    _, cn = parse_table(objects[1485].get_raw_data())
    _, ja = parse_table(objects[1488].get_raw_data())
    translated = load_translations()
    assert cn == [(key, translated.get(key, value)) for key, value in ja]
    assert len(translated) == manifest["translated"]
    index = json.loads((ROOT / "work/analysis/objects.json").read_text("utf-8"))
    images = json.loads((ROOT / "assets/images/manifest.json").read_text("utf-8"))
    for row in images:
        objrow, = [r for r in index if r["type"] == "Texture2D" and r["id"] == row["path_id"] and r["name"] == row["texture_name"]]
        env = UnityPy.load(str(args.patch / objrow["source"]))
        data = next(o.read() for o in env.objects if o.path_id == row["path_id"])
        actual = data.image.convert("RGBA")
        expected = Image.open(ROOT / "assets/images" / row["file"]).convert("RGBA").resize(actual.size, Image.Resampling.LANCZOS)
        assert actual.tobytes() == expected.tobytes(), row["file"]
    catalog = json.loads((args.patch / "alicenation_Data/StreamingAssets/aa/catalog.json").read_text("utf-8"))
    extra = base64.b64decode(catalog["m_ExtraDataString"])
    entries = base64.b64decode(catalog["m_EntryDataString"])
    bundles = {r["path"] for r in manifest["files"] if r["path"].endswith(".bundle")}
    checked = set()
    for i in range(struct.unpack_from("<i", entries)[0]):
        internal, _, _, _, offset, _, _ = struct.unpack_from("<7i", entries, 4 + i * 28)
        for rel in bundles:
            if offset >= 0 and catalog["m_InternalIds"][internal].replace("\\", "/").endswith(rel.split("StreamingAssets/aa/")[1]):
                pos = offset + 1
                for _ in range(2):
                    pos += 1 + extra[pos]
                length, = struct.unpack_from("<i", extra, pos)
                data = json.loads(extra[pos+4:pos+4+length].decode("utf-16-le"))
                assert data["m_Crc"] == bundle_crc(args.patch / rel), rel
                assert data["m_BundleSize"] == (args.patch / rel).stat().st_size, rel
                checked.add(rel)
    assert checked == bundles
    print(f"Verified {len(manifest['files'])} file hashes, {len(cn)} text records, {len(images)} images, {len(checked)} bundle CRCs")


if __name__ == "__main__":
    main()
