"""End-to-end tests against a real game copy, never the installed original."""
import json
from pathlib import Path
import subprocess
from inventory import digest

ROOT = Path(__file__).resolve().parents[1]
GAME = (ROOT / "work/installer-qa-game").resolve()
EXE = ROOT / "work/alicenation-korean-cli.exe"
PACKAGE = ROOT / "work/installer-qa-v1-draft.akp"


def main():
    assert GAME.parent == (ROOT / "work").resolve()
    baseline = json.loads((ROOT / "work/inventory.json").read_text("utf-8"))
    patch = json.loads((ROOT / "work/patched/manifest.json").read_text("utf-8"))
    logs = []

    def call(command, *args):
        result = subprocess.run([str(EXE), command, "--game", str(GAME), *args], capture_output=True, text=True, encoding="utf-8")
        logs.append({"command": command, "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 0, result.stderr

    for row in baseline["files"]:
        assert digest(GAME / row["path"]) == row["sha256"], row["path"]
    for _ in range(2):
        call("patch", "--package", str(PACKAGE), "--allow-draft")
        call("patch", "--package", str(PACKAGE), "--allow-draft")
        for row in patch["files"]:
            assert digest(GAME / row["path"]) == row["patched_sha256"], row["path"]
        call("status")
        call("restore")  # No package argument: recovery only needs its original backups.
        for row in baseline["files"]:
            assert digest(GAME / row["path"]) == row["sha256"], row["path"]
        assert (GAME / "qa-preserve.bin").read_bytes() == b"unchanged unrelated file"
    for row in baseline["files"]:
        assert digest(Path(baseline["game_root"]) / row["path"]) == row["sha256"], "Original installation changed"
    (ROOT / "work/installer-e2e.json").write_text(json.dumps(logs, ensure_ascii=False, indent=2), "utf-8")
    print(f"PASS: two patch/restore cycles, duplicate-install handling, {len(baseline['files'])} restored hashes, unrelated file preserved, installed original unchanged")


if __name__ == "__main__":
    main()
