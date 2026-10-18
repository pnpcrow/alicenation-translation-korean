"""Build an external clean copy, checking every file against Steam's cached manifest.

Reads only: the installed game and its original patch backups. Does not download
content or modify the Steam installation. Requires a decrypted filename manifest.
Schema: https://github.com/SteamTracking/Protobufs/blob/master/steam/content_manifest.proto
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct


def fields(raw):
    pos = 0

    def varint():
        nonlocal pos
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(raw):
                raise ValueError('Truncated protobuf')
            byte = raw[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value
        raise ValueError('Invalid varint')

    while pos < len(raw):
        tag = varint()
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError('Invalid field')
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            length = varint() if wire == 2 else (8 if wire == 1 else 4)
            if pos + length > len(raw):
                raise ValueError('Truncated field')
            value = raw[pos:pos + length]
            pos += length
        else:
            raise ValueError(f'Unsupported wire type {wire}')
        yield number, value


def read_manifest(path):
    raw = path.read_bytes()
    pos, sections = 0, {}
    while pos + 4 <= len(raw):
        magic, = struct.unpack_from('<I', raw, pos)
        pos += 4
        if magic == 0x32C415AB:
            break
        if magic not in (0x71F617D0, 0x1F4812BE, 0x1B81B817) or magic in sections:
            raise ValueError('Unexpected Steam manifest section')
        size, = struct.unpack_from('<I', raw, pos)
        pos += 4
        if pos + size > len(raw):
            raise ValueError('Truncated manifest section')
        sections[magic] = raw[pos:pos + size]
        pos += size
    if pos != len(raw) or len(sections) != 3 or magic != 0x32C415AB:
        raise ValueError('Incomplete Steam manifest')
    metadata = dict(fields(sections[0x1F4812BE]))
    if metadata.get(4, 0) or metadata[1] != 3755351:
        raise ValueError('Expected decrypted Alicenation Windows depot')
    rows, seen = [], set()
    for number, mapping in fields(sections[0x71F617D0]):
        if number != 1:
            raise ValueError('Unexpected manifest payload field')
        row = dict(fields(mapping))
        if row.get(3, 0) & 64:  # directory
            continue
        relative = row[1].decode('utf-8').replace('\\', '/')
        path = PurePosixPath(relative)
        if path.is_absolute() or any(p in ('', '.', '..') or ':' in p for p in relative.split('/')):
            raise ValueError('Unsafe manifest path')
        if relative.lower() in seen or row.get(7) or len(row[5]) != 20:
            raise ValueError('Duplicate path, link or invalid content hash')
        seen.add(relative.lower())
        rows.append({'path': relative, 'size': row[2], 'sha1': row[5].hex()})
    if sum(r['size'] for r in rows) != metadata[5]:
        raise ValueError('Steam total size mismatch')
    return {'depot': metadata[1], 'manifest': str(metadata[2]), 'files': rows}


def digest(path, algorithm):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    args = parser.parse_args()
    game, output = args.game.resolve(), args.output.resolve()
    if output.exists() or output == game or game in output.parents or args.inventory.exists():
        raise ValueError('Choose new output and inventory paths outside the game')
    manifest = read_manifest(args.manifest)
    backup = game / '.alicenation-korean/backup'
    roots = [game, backup, *[p for p in backup.iterdir() if p.is_dir()]] if backup.exists() else [game]
    selected = []
    for row in manifest['files']:
        source = next((base / row['path'] for base in roots
                       if (base / row['path']).is_file()
                       and (base / row['path']).stat().st_size == row['size']
                       and digest(base / row['path'], 'sha1') == row['sha1']), None)
        if source is None:
            raise ValueError(f"No verified original available: {row['path']}")
        selected.append((row, source))
    # Validate all sources before creating the snapshot.
    output.mkdir(parents=True)
    records, recovered = [], []
    for row, source in selected:
        target = output / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert digest(target, 'sha1') == row['sha1'], row['path']
        records.append({**row, 'sha256': digest(target, 'sha256')})
        if source != game / row['path']:
            recovered.append(row['path'])
    report = {'game_root': str(game), 'baseline_root': str(output),
              'steam_depot': manifest['depot'], 'steam_manifest': manifest['manifest'],
              'recovered_from_verified_backups': recovered, 'files': records}
    args.inventory.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({'files': len(records), 'bytes': sum(r['size'] for r in records),
                      'recovered_from_backups': len(recovered), 'output': str(output)}))


if __name__ == '__main__':
    main()
