"""Update catalog CRCs/sizes while preserving all resource and dependency keys."""
import base64
import json
import struct
import zlib
from pathlib import Path
from UnityPy.streams import EndianBinaryReader
from UnityPy.helpers import CompressionHelper

def bundle_crc(path: Path) -> int:
    reader = EndianBinaryReader(path.read_bytes(), endian=">")
    if reader.read_string_to_null() != "UnityFS":
        raise ValueError("Expected UnityFS")
    version = reader.read_u_int()
    reader.read_string_to_null()
    reader.read_string_to_null()
    size = reader.read_long()
    compressed, uncompressed, flags = reader.read_u_int(), reader.read_u_int(), reader.read_u_int()
    if size != reader.Length:
        raise ValueError("Bundle size mismatch")
    if version >= 7:
        reader.align_stream(16)
    start = reader.Position
    if flags & 0x80:
        reader.Position = reader.Length - compressed
    info = reader.read_bytes(compressed)
    if flags & 0x80:
        reader.Position = start
    info = CompressionHelper.DECOMPRESSION_MAP[flags & 63](info, uncompressed)
    blocks = EndianBinaryReader(info, endian=">")
    blocks.read_bytes(16)
    count = blocks.read_int()
    sizes = [(blocks.read_u_int(), blocks.read_u_int(), blocks.read_u_short()) for _ in range(count)]
    if flags & 0x200:
        reader.align_stream(16)
    crc = 0
    for plain_size, compressed_size, kind in sizes:
        raw = reader.read_bytes(compressed_size)
        raw = CompressionHelper.DECOMPRESSION_MAP[kind & 63](raw, plain_size)
        crc = zlib.crc32(raw, crc)
    return crc

def update_catalog(catalog_path: Path, game_root: Path, patched_root: Path, patched_paths: list[str]) -> bytes:
    catalog = json.loads(catalog_path.read_text("utf-8"))
    extra = base64.b64decode(catalog["m_ExtraDataString"])
    entries = bytearray(base64.b64decode(catalog["m_EntryDataString"]))
    count, = struct.unpack_from("<i", entries)
    if len(entries) != count * 28 + 4:
        raise ValueError("Unsupported catalog entries")
    replacements = {}
    for index in range(count):
        fields = struct.unpack_from("<7i", entries, 4 + index * 28)
        internal_id, _, _, _, extra_offset, _, _ = fields
        if extra_offset < 0:
            continue
        internal = catalog["m_InternalIds"][internal_id].replace("\\", "/")
        for path in patched_paths:
            if path.endswith(".bundle") and internal.endswith(path.split("StreamingAssets/aa/", 1)[1]):
                replacements[extra_offset] = path
    if len(replacements) != sum(p.endswith(".bundle") for p in patched_paths):
        raise ValueError("Not all modified bundles mapped to catalog entries")
    pos, rebuilt, offsets = 0, bytearray(), {}
    while pos < len(extra):
        start = pos
        offsets[start] = len(rebuilt)
        if extra[pos] != 7:
            raise ValueError(f"Unsupported catalog extra type {extra[pos]}")
        pos += 1
        for _ in range(2):
            length = extra[pos]
            pos += 1 + length
        length_pos = pos
        length, = struct.unpack_from("<i", extra, pos)
        pos += 4
        raw = extra[pos:pos+length]
        pos += length
        if start in replacements:
            rel = replacements[start]
            data = json.loads(raw.decode("utf-16-le"))
            original_crc = bundle_crc(game_root / rel)
            if original_crc != data["m_Crc"]:
                raise ValueError(f"Original catalog CRC differs for {rel}: {original_crc} != {data['m_Crc']}")
            data["m_Crc"] = bundle_crc(patched_root / rel)
            data["m_BundleSize"] = (patched_root / rel).stat().st_size
            raw = json.dumps(data, separators=(",", ":")).encode("utf-16-le")
        rebuilt.extend(extra[start:length_pos])
        rebuilt.extend(struct.pack("<i", len(raw)))
        rebuilt.extend(raw)
    for index in range(count):
        at = 4 + index * 28 + 16
        old, = struct.unpack_from("<i", entries, at)
        if old >= 0:
            struct.pack_into("<i", entries, at, offsets[old])
    catalog["m_ExtraDataString"] = base64.b64encode(rebuilt).decode("ascii")
    catalog["m_EntryDataString"] = base64.b64encode(entries).decode("ascii")
    return json.dumps(catalog, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
