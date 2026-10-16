"""End-to-end tests against a real game copy, never the installed original."""
import json
from pathlib import Path
import subprocess
import argparse
from inventory import digest

ROOT = Path(__file__).resolve().parents[1]
GAME = (ROOT / "work/installer-qa-game").resolve()
EXE = ROOT / "work/alicenation-korean-cli.exe"
PACKAGE = ROOT / "work/alicenation-1.0.5-korean-v1-final.akp"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--exe", type=Path, default=EXE)
    parser.add_argument("--embedded", action="store_true", help="Test the release executable's embedded payload")
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--patch", type=Path, default=ROOT / "work/patched")
    parser.add_argument("--inventory", type=Path, default=ROOT / "work/inventory.json")
    parser.add_argument("--report", type=Path, default=ROOT / "work/installer-e2e.json")
    parser.add_argument("--legacy-exe", type=Path, help="Also verify recovery from the original 1.0.5-only installer")
    args = parser.parse_args()
    game = args.game.resolve()
    assert game.parent == (ROOT / "work").resolve()
    baseline = json.loads(args.inventory.read_text("utf-8"))
    patch = json.loads((args.patch / "manifest.json").read_text("utf-8"))
    logs = []
    installed = Path(baseline["game_root"])
    installed_before = {p.relative_to(installed).as_posix(): digest(p)
                        for p in installed.rglob("*") if p.is_file()}

    def call(command, *options, exe=None):
        result = subprocess.run([str(exe or executable), command, "--game", str(game), *options], capture_output=True, text=True, encoding="utf-8")
        logs.append({"command": command, "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 0, result.stderr

    executable = args.exe.resolve()
    package_args = [] if args.embedded else ["--package", str(args.package.resolve())]
    for row in baseline["files"]:
        assert digest(game / row["path"]) == row["sha256"], row["path"]
    if args.legacy_exe:
        call("patch", exe=args.legacy_exe.resolve())
        call("restore")
        for row in baseline["files"]:
            assert digest(game / row["path"]) == row["sha256"], row["path"]
    for _ in range(2):
        call("patch", *package_args)
        call("patch", *package_args)
        for row in patch["files"]:
            assert digest(game / row["path"]) == row["patched_sha256"], row["path"]
        call("status")
        call("restore")  # No package argument: recovery only needs its original backups.
        for row in baseline["files"]:
            assert digest(game / row["path"]) == row["sha256"], row["path"]
        assert (game / "qa-preserve.bin").read_bytes() == b"unchanged unrelated file"
    installed_after = {p.relative_to(installed).as_posix(): digest(p)
                       for p in installed.rglob("*") if p.is_file()}
    assert installed_before == installed_after, "Installed game changed during installer QA"
    args.report.write_text(json.dumps({"game_version": patch["game_version"], "exe_sha256": digest(executable),
                                     "legacy_recovery": bool(args.legacy_exe), "logs": logs}, ensure_ascii=False, indent=2), "utf-8")
    print(f"PASS: two patch/restore cycles, duplicate-install handling, {len(baseline['files'])} restored hashes, unrelated file preserved, installed original unchanged")


if __name__ == "__main__":
    main()
