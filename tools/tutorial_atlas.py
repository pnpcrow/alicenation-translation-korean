"""Import generated tutorial artwork into the original, unmodified sprite layout."""
from collections import Counter
import json
from pathlib import Path
import UnityPy
import game_versions
from PIL import Image
from UnityPy.export.SpriteHelper import SpriteSettings

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "assets/images/tutorial"


def load_manifest():
    rows = json.loads((ART / "manifest.json").read_text("utf-8"))
    names = [r["name"] for r in rows]
    if len(names) != 52 or len(set(names)) != 52:
        raise ValueError("Expected 52 unique tutorial sprite decisions")
    for row in rows:
        if row["status"] not in {"pending", "translated", "preserved"} or not row.get("reason"):
            raise ValueError(f"Invalid tutorial decision: {row}")
        if row["status"] == "translated":
            for key in ("file", "prompt_file"):
                path = (ART / row[key]).resolve()
                if ART.resolve() not in path.parents or not path.is_file():
                    raise ValueError(f"Missing tutorial source: {row['name']} {key}")
    return rows


def coverage():
    counts = Counter(r["status"] for r in load_manifest())
    return {"total": 52, "translated": counts["translated"],
            "preserved": counts["preserved"], "pending": counts["pending"]}


def bundle_path(version="1.0.5"):
    index = json.loads(game_versions.object_index_path(version).read_text("utf-8"))
    rel, = {r["source"] for r in index if "teachatlas.spriteatlas_" in r["source"]}
    return rel


def canvases(env):
    """Resampling and packing only. All creative image edits come from image_gen."""
    rows = {r["name"]: r for r in load_manifest()}
    atlas, = [o.read() for o in env.objects if o.type.name == "SpriteAtlas"]
    sprites = [o.read() for o in env.objects if o.type.name == "Sprite"]
    if {s.m_Name for s in sprites} != rows.keys():
        raise ValueError("Tutorial sprite inventory differs from reviewed manifest")
    textures = {o.path_id: o.read() for o in env.objects if o.type.name == "Texture2D"}
    original = {pid: t.image.convert("RGBA") for pid, t in textures.items()}
    output = {pid: im.copy() for pid, im in original.items()}
    occupied = {pid: Image.new("1", im.size) for pid, im in original.items()}
    for sprite in sprites:
        packed, = [v for k, v in atlas.m_RenderDataMap if k == sprite.m_RenderDataKey]
        settings = SpriteSettings(packed.settingsRaw)
        if int(settings.packingMode) != 1 or int(settings.packingRotation) != 0:
            raise ValueError("Unexpected tutorial rotation or mesh packing")
        pid = packed.texture.path_id
        rect = packed.textureRect
        coords = [rect.x, rect.y, rect.width, rect.height]
        if any(int(v) != v for v in coords):
            raise ValueError("Non-integer tutorial rectangle")
        x, y, w, h = map(int, coords)
        im = original[pid]
        box = (x, im.height - y - h, x + w, im.height - y)
        if not (0 <= box[0] < box[2] <= im.width and 0 <= box[1] < box[3] <= im.height):
            raise ValueError("Tutorial rectangle exceeds atlas")
        if occupied[pid].crop(box).getbbox():
            raise ValueError("Overlapping tutorial rectangles")
        occupied[pid].paste(1, box)
        # Ground top/bottom orientation against UnityPy's Sprite decoder.
        if im.crop(box).tobytes() != sprite.image.convert("RGBA").tobytes():
            raise ValueError(f"Unexpected sprite orientation: {sprite.m_Name}")
        row = rows[sprite.m_Name]
        if row["status"] == "translated":
            edited = Image.open(ART / row["file"]).convert("RGBA")
            output[pid].paste(edited.resize((w, h), Image.Resampling.LANCZOS), box)
    return textures, output


def build(path):
    env = UnityPy.load(str(path))
    textures, images = canvases(env)
    for pid, image in images.items():
        textures[pid].set_image(image, target_format=4)
        textures[pid].save()
    return env.file.save(packer="lz4")


def verify(original_path, patched_path):
    original = UnityPy.load(str(original_path))
    patched = UnityPy.load(str(patched_path))
    _, expected = canvases(original)
    before = {o.path_id: o for o in original.objects}
    after = {o.path_id: o for o in patched.objects}
    assert before.keys() == after.keys(), "Tutorial objects changed"
    for pid, obj in before.items():
        if obj.type.name != "Texture2D":
            assert obj.get_raw_data() == after[pid].get_raw_data(), "Sprite or atlas metadata changed"
    for pid, image in expected.items():
        actual = after[pid].read().image.convert("RGBA")
        assert actual.size == image.size and actual.tobytes() == image.tobytes(), "Atlas pixels differ"
    for obj in after.values():
        if obj.type.name == "Sprite":
            sprite = obj.read()
            row, = [r for r in load_manifest() if r["name"] == sprite.m_Name]
            actual = sprite.image.convert("RGBA")
            if row["status"] == "translated":
                target = Image.open(ART / row["file"]).convert("RGBA").resize(actual.size, Image.Resampling.LANCZOS)
            else:
                target = before[obj.path_id].read().image.convert("RGBA")
            assert actual.tobytes() == target.tobytes(), sprite.m_Name
    return coverage()
