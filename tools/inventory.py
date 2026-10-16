"""Read-only baseline inventory. Original assets stay outside version control."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
from pathlib import Path

DEFAULT_GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\alicenation")

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=Path("work/inventory.json"))
    args = parser.parse_args()
    rows = [{"path": p.relative_to(args.game).as_posix(), "size": p.stat().st_size,
             "sha256": digest(p)} for p in sorted(args.game.rglob("*")) if p.is_file()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"game_root": str(args.game), "files": rows},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(rows), "bytes": sum(r["size"] for r in rows),
                      "extensions": dict(collections.Counter(Path(r["path"]).suffix for r in rows))}))

if __name__ == "__main__":
    main()
