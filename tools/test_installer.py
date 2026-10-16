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
    args = parser.parse_args()
    assert GAME.parent == (ROOT / "work").resolve()
    baseline = json.loads((ROOT / "work/inventory.json").read_text("utf-8"))
    patch = json.loads((ROOT / "work/patched/manifest.json").read_text("utf-8"))
    logs = []
    installed = Path(baseline["game_root"])
    installed_before = {p.relative_to(installed).as_posix(): digest(p)
                        for p in installed.rglob("*") if p.is_file()}

    def call(command, *args):
        result = subprocess.run([str(executable), command, "--game", str(GAME), *args], capture_output=True, text=True, encoding="utf-8")
        logs.append({"command": command, "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 0, result.stderr

    executable = args.exe.resolve()
    package_args = [] if args.embedded else ["--package", str(args.package.resolve())]
    for row in baseline["files"]:
        assert digest(GAME / row["path"]) == row["sha256"], row["path"]
    for _ in range(2):
        call("patch", *package_args)
        call("patch", *package_args)
        for row in patch["files"]:
            assert digest(GAME / row["path"]) == row["patched_sha256"], row["path"]
        call("status")
        call("restore")  # No package argument: recovery only needs its original backups.
        for row in baseline["files"]:
            assert digest(GAME / row["path"]) == row["sha256"], row["path"]
        assert (GAME / "qa-preserve.bin").read_bytes() == b"unchanged unrelated file"
    installed_after = {p.relative_to(installed).as_posix(): digest(p)
                       for p in installed.rglob("*") if p.is_file()}
    assert installed_before == installed_after, "Installed game changed during installer QA"
    (ROOT / "work/installer-e2e.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2), "utf-8")
    print(f"PASS: two patch/restore cycles, duplicate-install handling, {len(baseline['files'])} restored hashes, unrelated file preserved, installed original unchanged")


if __name__ == "__main__":
    main()
