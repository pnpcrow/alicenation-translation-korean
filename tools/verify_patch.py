"""Read back serialized patch assets, image pixels and Addressables CRC metadata."""
from __future__ import annotations
import argparse
import base64
import json
import io
import struct
from pathlib import Path
import UnityPy
from PIL import Image
from fontTools.ttLib import TTFont
from addressables import bundle_crc
from build_patch import ROOT, load_translations
from extract_localization import parse_table
from inventory import digest
from korean_font import DEFAULT_FONT, FONT_ID, TMP_ID, ATLAS_ID, MATERIAL_ID, pptr, is_hangul
from inventory import DEFAULT_GAME
import tutorial_atlas
import static_ui
import game_versions
import title_sprite


def verify_font(objects, nodes, existing_ids):
    """Regression check: image imports must retain the complete Korean fallback."""
    font_data = objects[FONT_ID].read_typetree()
    assert bytes(font_data["m_FontData"]) == DEFAULT_FONT.read_bytes()
    tmp = objects[TMP_ID].read_typetree(nodes=nodes)
    assert tmp["m_SourceFontFile"] == pptr(FONT_ID)
    assert tmp["m_Material"] == pptr(MATERIAL_ID)
    assert tmp["m_AtlasTextures"] == [pptr(ATLAS_ID)]
    assert tmp["m_AtlasPopulationMode"] == 1
    assert tmp["m_IsMultiAtlasTexturesEnabled"] == 1
    atlas = objects[ATLAS_ID].read_typetree()
    assert atlas["m_Width"] == atlas["m_Height"] == 1024
    assert atlas["m_TextureFormat"] == 1
    for object_id in existing_ids:
        data = objects[object_id].read_typetree(nodes=nodes)
        assert data["m_FallbackFontAssetTable"][0] == pptr(TMP_ID)
        assert not any(is_hangul(c["m_Unicode"]) for c in data["m_CharacterTable"])
        original = objects[data["m_SourceFontFile"]["m_PathID"]].read_typetree()
        ft = TTFont(io.BytesIO(bytes(original["m_FontData"])))
        assert not any(is_hangul(cp) for cp in ft.getBestCmap())
    ft = TTFont(io.BytesIO(bytes(font_data["m_FontData"])))
    assert set(range(0xAC00, 0xD7A4)) <= ft.getBestCmap().keys()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", type=Path, default=ROOT / "work/patched")
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    args = parser.parse_args()
    manifest = json.loads((args.patch / "manifest.json").read_text("utf-8"))
    version = game_versions.detect(args.game)
    assert manifest["game_version"] == version
    assert len({r["path"] for r in manifest["files"]}) == len(manifest["files"]), "Duplicate patch paths"
    for row in manifest["files"]:
        path = args.patch / row["path"]
        assert path.stat().st_size == row["size"], row["path"]
        assert digest(path) == row["patched_sha256"], row["path"]
        assert digest(args.game / row["path"]) == row["original_sha256"], row["path"]
    assert (args.patch / "GameAssembly.dll").read_bytes() == game_versions.patch_localization_branch(
        (args.game / "GameAssembly.dll").read_bytes(), version)
    env = UnityPy.load(str(args.patch / "alicenation_Data/resources.assets"))
    objects = {o.path_id: o for o in env.objects}
    _, cn = parse_table(objects[1485].get_raw_data())
    _, ja = parse_table(objects[1488].get_raw_data())
    translated = load_translations(version)
    assert cn == [(key, translated.get(key, value)) for key, value in ja]
    assert len(translated) == manifest["translated"]
    original_resources = UnityPy.load(str(args.game / "alicenation_Data/resources.assets"))
    original_objects = {o.path_id: o for o in original_resources.objects}
    # Preserve updated gameplay configuration, all scripts and comparison languages.
    for oid in [1477, 1479, 1480, 1486, 1487, 1488, *range(1498, 1515)]:
        assert original_objects[oid].get_raw_data() == objects[oid].get_raw_data(), oid
    settings = next(o for o in original_resources.objects if o.path_id == 1496).get_raw_data()
    assert len(settings) == 300 and settings[296:] == bytes(4)
    assert objects[1496].get_raw_data() == settings[:296] + b"\x01\x00\x00\x00"
    font_rel, = [r["path"] for r in manifest["files"] if "/fonts_assets_all_" in r["path"]]
    font_env = UnityPy.load(str(args.patch / font_rel))
    font_objects = {o.path_id: o for o in font_env.objects}
    template = font_objects[-1116400722278560788]
    verify_font(objects, template.serialized_type.node, [1474, 1475])
    verify_font(font_objects, template.serialized_type.node,
                [-8044376927816756463, -5279115822797500961, template.path_id])
    index = json.loads(game_versions.object_index_path(version).read_text("utf-8"))
    images = json.loads((ROOT / "assets/images/manifest.json").read_text("utf-8"))
    for row in images:
        objrow, = [r for r in index if r["type"] == "Texture2D" and r["id"] == row["path_id"] and r["name"] == row["texture_name"]]
        env = UnityPy.load(str(args.patch / objrow["source"]))
        data = next(o.read() for o in env.objects if o.path_id == row["path_id"])
        actual = data.image.convert("RGBA")
        expected = Image.open(ROOT / "assets/images" / row["file"]).convert("RGBA").resize(actual.size, Image.Resampling.LANCZOS)
        assert actual.tobytes() == expected.tobytes(), row["file"]
        if row["path_id"] == title_sprite.TEXTURE_ID:
            title_sprite.verify(UnityPy.load(str(args.game / objrow["source"])), env)
    tutorial = tutorial_atlas.verify(args.game / tutorial_atlas.bundle_path(version), args.patch / tutorial_atlas.bundle_path(version))
    assert tutorial == manifest["tutorial"]
    static_count = static_ui.verify(args.game, args.patch)
    assert static_count == manifest["static_ui"]
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
    print(f"Verified {len(manifest['files'])} file hashes, {len(cn)} text records, {static_count} static labels, 2 complete Korean font fallbacks, {len(images)} images, 52 tutorial sprite layouts/pixels ({tutorial['translated']} translated), {len(checked)} bundle CRCs")


if __name__ == "__main__":
    main()
