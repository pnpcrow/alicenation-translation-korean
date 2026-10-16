"""Confirm the Rust packer rejects incomplete graphics even with complete text."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKER = ROOT / "installer/target/debug/pack-payload.exe"


def main():
    baseline = json.loads((ROOT / "work/patched/manifest.json").read_text("utf-8"))
    baseline.update(translated=7410, missing=0, patch_version="v1-draft")
    baseline["tutorial"] = {"total": 52, "translated": 24, "preserved": 27, "pending": 1}
    with tempfile.TemporaryDirectory(prefix="pack-gate-", dir=ROOT / "work") as folder:
        folder = Path(folder)
        cases = [("pending graphics", baseline, "incomplete text or tutorial graphics")]
        absent = copy.deepcopy(baseline)
        del absent["tutorial"]
        cases.append(("missing graphics audit", absent, "missing field"))
        wrong = copy.deepcopy(baseline)
        wrong["tutorial"].update(total=53, preserved=29, pending=0)
        wrong["patch_version"] = "v1"
        cases.append(("invalid coverage", wrong, "tutorial coverage count mismatch"))
        for name, manifest, message in cases:
            (folder / "manifest.json").write_text(json.dumps(manifest), "utf-8")
            output = folder / "refused.akp"
            # A nonexistent game path proves rejection happens before reading originals.
            result = subprocess.run([str(PACKER), str(folder / "no-game"), str(folder), str(output)],
                                    capture_output=True, text=True, encoding="utf-8")
            assert result.returncode != 0 and message in result.stderr, (name, result.stderr)
            assert not output.exists(), name
            print("PASS:", name)


if __name__ == "__main__":
    main()
