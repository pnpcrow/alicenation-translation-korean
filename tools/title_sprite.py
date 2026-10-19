"""Let the Korean title use its full texture instead of the old CN silhouette."""
from copy import deepcopy
import struct

from UnityPy.helpers.MeshHelper import MeshHandler

SPRITE_ID = 8640865309597887
TEXTURE_ID = 2994417245854802111


def replace_mesh(env):
    obj, = [o for o in env.objects if o.type.name == "Sprite" and o.path_id == SPRITE_ID]
    data = obj.read_typetree()
    rd = data["m_RD"]
    assert data["m_Name"] == "Title_CN"
    assert data["m_Rect"] == {"x": 0.0, "y": 0.0, "width": 1024.0, "height": 1024.0}
    assert data["m_Pivot"] == {"x": 0.5, "y": 0.5} and data["m_PixelsToUnits"] == 260.0
    assert data["m_SpriteAtlas"]["m_PathID"] == 0 and not data["m_AtlasTags"]
    assert rd["texture"] == {"m_FileID": 0, "m_PathID": TEXTURE_ID}
    assert rd["settingsRaw"] == 64 and rd["m_VertexData"]["m_VertexCount"] == 151
    assert rd["textureRect"]["width"] < 1024 and rd["textureRect"]["height"] < 1024

    # Keep the original rectangle, pivot and pixels-per-unit, so layout stays fixed.
    # Position and UV streams each start at a 16-byte boundary (48 + 32 bytes).
    half = 512.0 / data["m_PixelsToUnits"]
    positions = [(-half, -half, 0.0), (-half, half, 0.0),
                 (half, half, 0.0), (half, -half, 0.0)]
    uvs = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    rd["m_VertexData"]["m_VertexCount"] = 4
    rd["m_VertexData"]["m_DataSize"] = b"".join(struct.pack("<3f", *p) for p in positions)
    rd["m_VertexData"]["m_DataSize"] += b"".join(struct.pack("<2f", *uv) for uv in uvs)
    channels = rd["m_VertexData"]["m_Channels"]
    assert [(i, c["stream"], c["offset"], c["format"], c["dimension"])
            for i, c in enumerate(channels) if c["dimension"]] == [(0, 0, 0, 0, 3), (4, 1, 0, 0, 2)]
    rd["m_IndexBuffer"] = struct.pack("<6H", 0, 1, 2, 2, 3, 0)
    submesh = deepcopy(rd["m_SubMeshes"][0])
    submesh.update(firstByte=0, indexCount=6, topology=0, baseVertex=0, firstVertex=0, vertexCount=4)
    submesh["localAABB"] = {"m_Center": {"x": 0.0, "y": 0.0, "z": 0.0},
                           "m_Extent": {"x": half, "y": half, "z": 0.0}}
    rd["m_SubMeshes"] = [submesh]
    rd["textureRect"] = dict(data["m_Rect"])
    rd["textureRectOffset"] = {"x": 0.0, "y": 0.0}
    rd["settingsRaw"] = 2  # unpacked, rectangle packing, FullRect mesh
    obj.save_typetree(data)


def verify(original, patched):
    before = {o.path_id: o for o in original.objects}
    after = {o.path_id: o for o in patched.objects}
    assert before.keys() == after.keys()
    for pid, obj in before.items():
        if pid not in (SPRITE_ID, TEXTURE_ID):
            assert obj.get_raw_data() == after[pid].get_raw_data(), f"Unrelated title object changed: {pid}"
    old = before[SPRITE_ID].read_typetree()
    new = after[SPRITE_ID].read_typetree()
    assert {k: v for k, v in old.items() if k != "m_RD"} == {k: v for k, v in new.items() if k != "m_RD"}
    sprite = after[SPRITE_ID].read()
    texture = after[TEXTURE_ID].read().image.convert("RGBA")
    rendered = sprite.image.convert("RGBA")
    # Unlike a texture-only check, this detects cropping by the serialized sprite.
    assert rendered.size == texture.size == (1024, 1024)
    assert rendered.tobytes() == texture.tobytes(), "Title sprite clips the translated texture"
    mesh = MeshHandler(sprite.m_RD, after[SPRITE_ID].version)
    mesh.process()
    assert len(mesh.m_Vertices) == 4
    assert set(tuple(uv) for uv in mesh.m_UV0) == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert sum(len(triangles) for triangles in mesh.get_triangles()) == 2
    for (x, y, z), (u, v) in zip(mesh.m_Vertices, mesh.m_UV0):
        assert abs((x * sprite.m_PixelsToUnits + 512) / 1024 - u) < 1e-6
        assert abs((y * sprite.m_PixelsToUnits + 512) / 1024 - v) < 1e-6
        assert z == 0
