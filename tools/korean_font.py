"""Inject an independent dynamic TMP Korean fallback, retaining other languages."""
from __future__ import annotations
import copy
import io
from pathlib import Path
from fontTools.ttLib import TTFont

FONT_ID, TMP_ID, ATLAS_ID, MATERIAL_ID = 91000001, 91000002, 91000003, 91000004

def pptr(path_id):
    return {"m_FileID": 0, "m_PathID": path_id}

def is_hangul(cp):
    return 0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F

def clone_object(obj, path_id):
    clone = copy.copy(obj)
    clone.path_id = path_id
    if path_id in obj.assets_file.objects:
        raise ValueError(f"Path ID collision: {path_id}")
    obj.assets_file.objects[path_id] = clone
    return clone

DEFAULT_FONT = Path(__file__).resolve().parents[1] / "assets/fonts/HakgyoansimGeurimilgi-Regular.ttf"


def install_font(objects, tmp_template, tmp_objects, source_font_id, font_file=DEFAULT_FONT):
    ft = TTFont(font_file)
    family = ft["name"].getDebugName(1)
    style = ft["name"].getDebugName(2)
    missing = set(range(0xAC00, 0xD7A4)) - ft.getBestCmap().keys()
    if missing:
        raise ValueError(f"Korean font is missing {len(missing)} Hangul syllables")
    nodes = tmp_template.serialized_type.node
    template = tmp_objects[-1]
    tdata = template.read_typetree(nodes=nodes)
    atlas_src = objects[tdata["m_AtlasTextures"][0]["m_PathID"]]
    material_src = objects[tdata["m_Material"]["m_PathID"]]
    font_obj = clone_object(objects[source_font_id], FONT_ID)
    font_data = font_obj.read_typetree()
    font_data["m_Name"] = family
    font_data["m_FontData"] = list(font_file.read_bytes())
    font_data["m_FontNames"] = [family]
    font_data["m_FallbackFonts"] = []
    font_obj.save_typetree(font_data)

    atlas = clone_object(atlas_src, ATLAS_ID)
    atlas_data = atlas.read_typetree()
    atlas_data["m_Name"] = "Korean dynamic atlas"
    atlas_data["image data"] = bytes(1024 * 1024)
    atlas_data["m_StreamData"] = {"offset": 0, "size": 0, "path": ""}
    atlas_data["m_Width"] = atlas_data["m_Height"] = 1024
    atlas_data["m_CompleteImageSize"] = 1024 * 1024
    atlas_data["m_TextureFormat"] = 1  # Alpha8, TMP SDF
    atlas_data["m_MipCount"] = 1
    atlas_data["m_IsReadable"] = True
    atlas.save_typetree(atlas_data)

    material = clone_object(material_src, MATERIAL_ID)
    mdata = material.read_typetree()
    mdata["m_Name"] = "Korean atlas material"
    for key, value in mdata["m_SavedProperties"]["m_TexEnvs"]:
        if key == "_MainTex":
            value["m_Texture"] = pptr(ATLAS_ID)
    material.save_typetree(mdata)

    tmp = clone_object(template, TMP_ID)
    tdata["m_Name"] = family + " SDF"
    tdata["m_SourceFontFile"] = pptr(FONT_ID)
    tdata["m_SourceFontFileGUID"] = ""
    tdata["m_Material"] = pptr(MATERIAL_ID)
    tdata["m_AtlasTextures"] = [pptr(ATLAS_ID)]
    tdata["m_AtlasTextureIndex"] = 0
    tdata["m_AtlasPopulationMode"] = 1
    tdata["m_IsMultiAtlasTexturesEnabled"] = 1
    tdata["m_GlyphTable"] = []
    tdata["m_CharacterTable"] = []
    tdata["m_UsedGlyphRects"] = []
    tdata["m_FreeGlyphRects"] = [{"m_X": 0, "m_Y": 0, "m_Width": 1023, "m_Height": 1023}]
    tdata["m_FallbackFontAssetTable"] = []
    tdata["m_FontFeatureTable"] = {k: [] for k in tdata["m_FontFeatureTable"]}
    units = ft["head"].unitsPerEm
    scale = 90 / units
    face = tdata["m_FaceInfo"]
    face.update(m_FamilyName=family, m_StyleName=style, m_UnitsPerEM=units,
                m_LineHeight=(ft["hhea"].ascent - ft["hhea"].descent + ft["hhea"].lineGap) * scale,
                m_AscentLine=ft["hhea"].ascent * scale, m_DescentLine=ft["hhea"].descent * scale,
                m_CapLine=getattr(ft["OS/2"], "sCapHeight", ft["hhea"].ascent) * scale,
                m_MeanLine=getattr(ft["OS/2"], "sxHeight", ft["hhea"].ascent) * scale)
    tmp.save_typetree(tdata, nodes=nodes)

    for existing in tmp_objects:
        data = existing.read_typetree(nodes=nodes)
        data["m_FallbackFontAssetTable"].insert(0, pptr(TMP_ID))
        data["m_CharacterTable"] = [c for c in data["m_CharacterTable"] if not is_hangul(c["m_Unicode"])]
        existing.save_typetree(data, nodes=nodes)
        # Lolita contains only 2,350 Korean syllables. Remove its Korean cmap so
        # every Korean syllable consistently uses the complete fallback font.
        source = objects[data["m_SourceFontFile"]["m_PathID"]]
        fdata = source.read_typetree()
        font = TTFont(io.BytesIO(bytes(fdata["m_FontData"])), recalcTimestamp=False)
        changed = False
        for table in font["cmap"].tables:
            if table.isUnicode():
                remove = [cp for cp in table.cmap if is_hangul(cp)]
                for cp in remove:
                    del table.cmap[cp]
                changed |= bool(remove)
        if changed:
            buf = io.BytesIO()
            font.save(buf)
            fdata["m_FontData"] = list(buf.getvalue())
            source.save_typetree(fdata)
