"""Collect the self-contained installer, instructions and dependency notices."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    parser.add_argument("--patch", type=Path, default=ROOT / "work/patched")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Alicenation-1.0.5-Korean-v1")
    args = parser.parse_args()
    manifest = json.loads((args.patch / "manifest.json").read_text("utf-8"))
    assert manifest["patch_version"] == "v1" and manifest["missing"] == 0
    assert manifest["tutorial"]["pending"] == 0 and manifest["static_ui"] == 90
    args.output.mkdir(parents=True, exist_ok=False)
    exe = args.output / "Alicenation-Korean-v1.exe"
    shutil.copy2(args.exe, exe)
    count = notices(args.output / "licenses")
    shutil.copy2(ROOT / "docs/release-readme.txt", args.output / "사용안내.txt")
    info = {"game_version": manifest["game_version"], "patch_version": "v1",
            "text_entries": manifest["translated"], "static_labels": manifest["static_ui"],
            "tutorial": manifest["tutorial"], "modified_files": len(manifest["files"]),
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
