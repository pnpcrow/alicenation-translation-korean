"""Read Unity object metadata and extract TextAssets for local analysis."""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import UnityPy
from inventory import DEFAULT_GAME

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=Path("work/analysis"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    sources = [p for p in args.game.rglob("*") if p.suffix in (".bundle", ".assets") or p.name == "globalgamemanagers"]
    for index, path in enumerate(sorted(sources)):
        try:
            env = UnityPy.load(str(path))
            for obj in env.objects:
                row = {"source": path.relative_to(args.game).as_posix(), "file": obj.assets_file.name,
                       "id": obj.path_id, "type": obj.type.name, "size": obj.byte_size}
                if obj.type.name in ("TextAsset", "MonoBehaviour", "MonoScript", "Texture2D", "Sprite", "Font", "AssetBundle", "PlayerSettings"):
                    try:
                        data = obj.read_typetree()
                        row["name"] = data.get("m_Name", "")
                        if obj.type.name in ("MonoBehaviour", "MonoScript", "PlayerSettings"):
                            out = args.output / "trees" / f"{index}_{obj.path_id}.json"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", errors="surrogatepass")
                            row["tree"] = str(out)
                        if obj.type.name == "TextAsset":
                            out = args.output / "texts" / f"{index}_{obj.path_id}.txt"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            out.write_bytes(data.get("m_Script", "").encode("utf-8", "surrogateescape"))
                            row["text"] = str(out)
                    except Exception as exc:
                        row["read_error"] = str(exc)
                records.append(row)
        except Exception as exc:
            errors.append({"source": str(path), "error": str(exc)})
        if index % 50 == 0:
            print(f"{index}/{len(sources)} files, {len(records)} objects", flush=True)
    (args.output / "objects.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"types": dict(collections.Counter(r["type"] for r in records)), "errors": errors}, ensure_ascii=False))

if __name__ == "__main__":
    main()
