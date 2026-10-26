"""Translate the verified 1.0.11 save-slot chapter format without moving metadata."""
import hashlib
import struct

PATH = "alicenation_Data/il2cpp_data/Metadata/global-metadata.dat"
ORIGINAL_SHA256 = "0804c92ab0f6138db02d540a2a1ae1309ef7307576eafb1e92d2d9c860ee12d0"
ENTRY_OFFSET = 0x6BF0
DATA_OFFSET = 0x38377
ORIGINAL = b"Chapter {0}"
KOREAN = "제{0}장".encode("utf-8")


def literals(raw):
    magic, version, entries, size, data, data_size = struct.unpack_from("<6I", raw)
    if magic != 0xFAB11BAF or version != 31 or size % 8:
        raise ValueError("Unexpected IL2CPP string literal table")
    if entries + size > len(raw) or data + data_size > len(raw):
        raise ValueError("Truncated IL2CPP metadata")
    result = []
    for offset in range(entries, entries + size, 8):
        length, index = struct.unpack_from("<2I", raw, offset)
        if index + length > data_size:
            raise ValueError("Invalid IL2CPP string literal range")
        result.append((offset, data + index, raw[data + index:data + index + length]))
    return result


def patch(raw):
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Runtime text does not match verified 1.0.11 metadata")
    matches = [row for row in literals(raw) if row[2] == ORIGINAL]
    if matches != [(ENTRY_OFFSET, DATA_OFFSET, ORIGINAL)]:
        raise ValueError("Chapter format location changed")
    result = bytearray(raw)
    # Shorten this literal's declared UTF-8 length; all following offsets stay put.
    struct.pack_into("<I", result, ENTRY_OFFSET, len(KOREAN))
    result[DATA_OFFSET:DATA_OFFSET + len(ORIGINAL)] = KOREAN.ljust(len(ORIGINAL), b"\0")
    return bytes(result)


def verify(original, patched):
    assert len(original) == len(patched)
    before, after = literals(original), literals(patched)
    assert len(before) == len(after)
    for old, new in zip(before, after):
        assert old[:2] == new[:2]
        assert new[2] == (KOREAN if old[0] == ENTRY_OFFSET else old[2])
    allowed = set(range(ENTRY_OFFSET, ENTRY_OFFSET + 4)) | set(range(DATA_OFFSET, DATA_OFFSET + len(ORIGINAL)))
    assert all(i in allowed for i, (a, b) in enumerate(zip(original, patched)) if a != b)
    assert patched == patch(original)
    return 1
