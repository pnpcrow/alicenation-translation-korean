"""Extract graphics and make labeled review sheets (analysis only, not patch art)."""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import UnityPy
from PIL import Image, ImageDraw, ImageFont
from inventory import DEFAULT_GAME

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "reference/graphics-audit"
    (out / "textures").mkdir(parents=True, exist_ok=True)
    (out / "sheets").mkdir(exist_ok=True)
    rows = json.loads((ROOT / "work/analysis/objects.json").read_text("utf-8"))
    groups = defaultdict(list)
    for row in rows:
        if row["type"] == "Texture2D":
            groups[row["source"]].append(row)
    results, seen = [], {}
    for rel, entries in groups.items():
        env = UnityPy.load(str(DEFAULT_GAME / rel))
        objects = {o.path_id: o for o in env.objects}
        for row in entries:
            data = objects[row["id"]].read()
            if not data.image_data and not getattr(data.m_StreamData, "size", 0):
                results.append({**row, "width": data.m_Width, "height": data.m_Height,
                                "image": None, "status": "empty runtime texture"})
                continue
            im = data.image.convert("RGBA")
            checksum = hashlib.sha256(str(im.size).encode() + im.tobytes()).hexdigest()
            if checksum not in seen:
                index = len(seen)
                filename = f"textures/{index:04}.png"
                im.save(out / filename)
                seen[checksum] = filename
            results.append({**row, "width": im.width, "height": im.height,
                            "pixel_sha256": checksum, "image": seen[checksum]})
        print(f"Extracted {len(results)} textures", flush=True)
    (out / "index.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), "utf-8")
    unique = list({r["image"]: r for r in reversed(results) if r["image"]}.values())
    unique.sort(key=lambda r: r["image"])
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 15)
    for start in range(0, len(unique), 30):
        page = Image.new("RGB", (1800, 1300), "#deded8")
        draw = ImageDraw.Draw(page)
        for i, row in enumerate(unique[start:start + 30]):
            x, y = (i % 6) * 300, (i // 6) * 260
            im = Image.open(out / row["image"]).convert("RGBA")
            im.thumbnail((292, 220))
            page.paste(im, (x + (300 - im.width) // 2, y + (220 - im.height) // 2), im)
            draw.text((x + 4, y + 224), f"{Path(row['image']).stem} {row['name'][:28]}", fill="black", font=font)
            draw.text((x + 4, y + 243), f"{row['width']} x {row['height']}", fill="black", font=font)
        page.save(out / f"sheets/{start // 30:02}.jpg", quality=93)
    print(f"Reviewed source: {len(results)} objects, {len(unique)} unique textures; {(len(unique)+29)//30} sheets")


if __name__ == "__main__":
    main()
