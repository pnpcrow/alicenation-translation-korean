"""Write coverage from the canonical source table, ignoring old scratch files."""
from datetime import date
import json
import re
from build_patch import ROOT, load_translations


def main():
    ja = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
    ko = load_translations()
    counts = {}
    for key in ja:
        group = key.split("_")[0] if re.match(r"^[A-Za-z0-9]+_", key) else "Dialogue"
        row = counts.setdefault(group, {"translated": 0, "total": 0})
        row["total"] += 1
        row["translated"] += key in ko
    result = {"as_of": date.today().isoformat(), "coverage": counts,
              "translated": len(ko), "total": len(ja), "status": "in_progress",
              "note": "Coverage indicates authored entries, not final linguistic or gameplay QA."}
    (ROOT / "docs/translation-progress.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
