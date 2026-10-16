"""Collect the self-contained installer, instructions and dependency notices."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_manifests(data):
    if data[:8] == b"ALICKO2\n":
        count, = struct.unpack_from("<Q", data, 8)
        assert 1 <= count <= 2
        result, cursor = [], 16
        for _ in range(count):
            size, = struct.unpack_from("<Q", data, cursor)
            cursor += 8
            chunk = data[cursor:cursor + size]
            assert len(chunk) == size and chunk[:8] == b"ALICKO1\n"
            result.extend(payload_manifests(chunk))
            cursor += size
        assert cursor == len(data)
        return result
    assert data[:8] == b"ALICKO1\n"
    size, = struct.unpack_from("<Q", data, 8)
    return [json.loads(data[16:16 + size])]


def notices(destination):
    metadata = json.loads(subprocess.check_output([
        "cargo", "metadata", "--format-version", "1", "--locked",
        "--filter-platform", "x86_64-pc-windows-msvc"], cwd=ROOT / "installer"))
    resolved = {node["id"] for node in metadata["resolve"]["nodes"]}
    egui = {"ecolor", "eframe", "egui", "egui-winit", "egui_glow", "emath", "epaint", "epaint_default_fonts"}
    fallback = {name: "egui" for name in egui}
    fallback.update({"clipboard-win": "clipboard", "gl_generator": "gl_generator",
                     "khronos_api": "khronos", "profiling": "profiling", "sacabase": "sacabase"})
    index = []
    for package in sorted(metadata["packages"], key=lambda p: (p["name"], p["version"])):
        if not package.get("source") or package["id"] not in resolved:
            continue
        source = Path(package["manifest_path"]).parent
        output = destination / f"{package['name']}-{package['version']}"
        output.mkdir(parents=True)
        files = [p for p in source.iterdir() if p.is_file() and p.name.upper().startswith(
            ("LICENSE", "LICENCE", "COPYING", "NOTICE", "UNLICENSE", "COPYRIGHT"))]
        for file in files:
            shutil.copy2(file, output / file.name)
        if package["name"] in fallback:
            upstream = ROOT / "assets/licenses/upstream" / fallback[package["name"]]
            for file in upstream.iterdir():
                if file.is_file():
                    shutil.copy2(file, output / file.name)
        if package["name"] == "epaint_default_fonts":
            for file in (source / "fonts").glob("*.txt"):
                shutil.copy2(file, output / file.name)
        if not any(output.iterdir()):
            raise ValueError(f"Missing license notice: {package['name']}")
        index.append({k: package.get(k) for k in ("name", "version", "license", "authors", "repository")})
    (destination / "dependencies.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", "utf-8")
    shutil.copy2(ROOT / "assets/licenses/upstream/sources.json", destination / "upstream-sources.json")
    shutil.copy2(ROOT / "assets/fonts/HakgyoansimGeurimilgi-OFL.txt", destination / "HakgyoansimGeurimilgi-OFL.txt")
    shutil.copy2(ROOT / "assets/fonts/provenance.json", destination / "font-provenance.json")
    return len(index)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=ROOT / "installer/target/release/alicenation-korean.exe")
    parser.add_argument("--patch", type=Path, action="append", help="Repeat for each supported game version")
    parser.add_argument("--payload", type=Path, default=ROOT / "work/alicenation-1.0.5-1.0.6-korean-v1.akp")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Alicenation-1.0.5-1.0.6-Korean-v1")
    parser.add_argument("--readme", type=Path, default=ROOT / "docs/release-readme.txt",
                        help="Instructions matching this distribution's supported game versions")
    args = parser.parse_args()
    patches = args.patch or [ROOT / "work/patched", ROOT / "work/patched-1.0.6"]
    manifests = [json.loads((patch / "manifest.json").read_text("utf-8")) for patch in patches]
    payload = args.payload.read_bytes()
    assert args.exe.read_bytes().count(payload) == 1, "Executable does not contain this exact payload once"
    embedded = {m["game_version"]: m for m in payload_manifests(payload)}
    assert set(embedded) == {m["game_version"] for m in manifests}
    for manifest in manifests:
        assert manifest["patch_version"] == "v1" and manifest["missing"] == 0
        assert manifest["tutorial"]["pending"] == 0 and manifest["static_ui"] == 90
        packed = embedded[manifest["game_version"]]
        assert not packed["draft"] and packed["patch_version"] == "v1"
        fields = ("path", "original_sha256", "patched_sha256", "size")
        assert [{k: r[k] for k in fields} for r in packed["files"]] == [{k: r[k] for k in fields} for r in manifest["files"]]
    args.output.mkdir(parents=True, exist_ok=False)
    exe = args.output / "Alicenation-Korean-v1.exe"
    shutil.copy2(args.exe, exe)
    count = notices(args.output / "licenses")
    shutil.copy2(args.readme, args.output / "사용안내.txt")
    info = {"patch_version": "v1", "game_versions": [{"game_version": m["game_version"],
            "text_entries": m["translated"], "static_labels": m["static_ui"],
            "tutorial": m["tutorial"], "modified_files": len(m["files"])} for m in manifests],
            "payload_sha256": sha(args.payload),
            "installer_sha256": sha(exe), "dependency_notices": count}
    (args.output / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", "utf-8")
    archive = Path(str(args.output) + ".zip")
    temporary = Path(str(archive) + ".tmp")
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=False) as z:
        for file in sorted(args.output.rglob("*")):
            if file.is_file():
                z.write(file, f"{args.output.name}/{file.relative_to(args.output).as_posix()}")
    temporary.rename(archive)
    Path(str(archive) + ".sha256").write_text(f"{sha(archive)}  {archive.name}\n", "utf-8")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size, **info}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
