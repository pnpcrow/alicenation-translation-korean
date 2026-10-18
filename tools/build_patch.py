"""Build modified copies; never writes to the installed game directory."""
from __future__ import annotations
import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path
import UnityPy
from PIL import Image
from inventory import DEFAULT_GAME, digest
from extract_localization import parse_table, build_table
from korean_font import install_font, enable_korean_word_wrapping
from addressables import update_catalog
from validate_translations import validate
from dialogue import load_dialogue
import tutorial_atlas
import static_ui
import game_versions

ROOT = Path(__file__).resolve().parents[1]

def load_translations(version="1.0.5"):
    merged = {}
    for path in sorted((ROOT / "translations/ko").glob("*.json")):
        rows = json.loads(path.read_text("utf-8"))
        overlap = merged.keys() & rows.keys()
        if overlap:
            raise ValueError(f"Duplicate translation keys: {overlap}")
        merged.update(rows)
    dialogue = load_dialogue()
    if merged.keys() & dialogue.keys():
        raise ValueError("Duplicate explicit dialogue keys")
    merged.update(dialogue)
    alias_path = ROOT / "translations/aliases.json"
    if alias_path.exists():
        aliases = json.loads(alias_path.read_text("utf-8"))
        japanese = json.loads((ROOT / "reference/localization/JA.json").read_text("utf-8"))
        for key, target in aliases.items():
            if key in merged:
                raise ValueError(f"Alias also has an explicit translation: {key}")
            if key not in japanese or target not in japanese or japanese[key] != japanese[target]:
                raise ValueError(f"Alias source text differs: {key} -> {target}")
            if target not in merged:
                raise ValueError(f"Alias target is untranslated: {key} -> {target}")
            merged[key] = merged[target]
    return game_versions.adapt_translations(merged, version)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--output", type=Path, default=ROOT / "work/patched")
    parser.add_argument("--draft", action="store_true", help="Allow incomplete translations for local QA only")
    args = parser.parse_args()
    if args.output.resolve() == args.game.resolve() or args.game.resolve() in args.output.resolve().parents:
        raise ValueError("Output must be outside the game directory")
    version = game_versions.detect(args.game)
    inventory = json.loads(game_versions.inventory_path(version).read_text("utf-8"))
    baseline = {r["path"]: r for r in inventory["files"]}
    object_index = json.loads(game_versions.object_index_path(version).read_text("utf-8"))
    records = {}

    def source(rel):
        path = args.game / rel
        if digest(path) != baseline[rel]["sha256"]:
            raise ValueError(f"Original file has changed: {rel}")
        return path

    def save(rel, data):
        path = args.output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        records[rel] = {"path": rel, "original_sha256": baseline[rel]["sha256"],
                        "patched_sha256": digest(path), "size": path.stat().st_size}

    def current_source(rel):
        original = source(rel)
        if rel not in records:
            return original
        current = args.output / rel
        if digest(current) != records[rel]["patched_sha256"]:
            raise ValueError(f"Intermediate patch file has changed: {rel}")
        return current

    version_env = UnityPy.load(str(source("alicenation_Data/globalgamemanagers")))
    version = next(o.read_typetree()["bundleVersion"] for o in version_env.objects if o.type.name == "PlayerSettings")
    if version not in game_versions.SUPPORTED:
        raise ValueError(f"Unsupported game version: {version}")
    translated = load_translations(version)
    font_rel = next(r["path"] for r in inventory["files"] if "/fonts_assets_all_" in r["path"])
    font_env = UnityPy.load(str(source(font_rel)))
    font_objects = {o.path_id: o for o in font_env.objects}
    template = font_objects[-1116400722278560788]

    rel = "alicenation_Data/resources.assets"
    env = UnityPy.load(str(source(rel)))
    objects = {o.path_id: o for o in env.objects}
    header, _ = parse_table(objects[1485].get_raw_data())
    _, japanese = parse_table(objects[1488].get_raw_data())
    problems = validate(dict(japanese), translated)
    if problems:
        raise ValueError("Invalid translations: " + "; ".join(problems))
    missing = [key for key, _ in japanese if key not in translated]
    tutorial = tutorial_atlas.coverage()
    extra = translated.keys() - dict(japanese).keys()
    if extra:
        raise ValueError(f"Unknown keys: {extra}")
    if missing and not args.draft:
        raise ValueError(f"{len(missing)} untranslated keys; use --draft for local QA only")
    if tutorial["pending"] and not args.draft:
        raise ValueError(f"{tutorial['pending']} tutorial images pending; use --draft for local QA only")
    rows = [(key, translated.get(key, value)) for key, value in japanese]
    objects[1485].set_raw_data(build_table(header, rows))
    install_font(objects, template, [objects[1474], objects[1475]], 542)
    enable_korean_word_wrapping(objects)
    save(rel, env.file.save())
    print(f"Text: {len(translated)}/{len(japanese)}", flush=True)

    install_font(font_objects, template,
                 [font_objects[-8044376927816756463], font_objects[-5279115822797500961], template],
                 4402228980017930471)
    save(font_rel, font_env.file.save(packer="lz4"))

    # CN should consult the translation table like EN/JA instead of returning the key.
    rel = "GameAssembly.dll"
    binary = game_versions.patch_localization_branch(source(rel).read_bytes(), version)
    save(rel, binary)

    # Language buttons are serialized text rather than localization table values.
    rel = next(x["source"] for x in object_index if x["id"] == 2505756016587389373)
    env = UnityPy.load(str(source(rel)))
    changed = 0
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        data = obj.read_typetree()
        if data.get("m_text") == "简体中文":
            data["m_text"] = "한국어"
            obj.save_typetree(data)
            changed += 1
    if changed != 2:
        raise ValueError(f"Expected two CN language labels, found {changed}")
    save(rel, env.file.save(packer="lz4"))

    for rel, entries in static_ui.grouped(version).items():
        save(rel, static_ui.build(current_source(rel), entries))

    image_entries = json.loads((ROOT / "assets/images/manifest.json").read_text("utf-8"))
    image_bundles = defaultdict(list)
    for entry in image_entries:
        matches = [x for x in object_index if x["type"] == "Texture2D"
                   and x["id"] == entry["path_id"] and x.get("name") == entry["texture_name"]]
        if len(matches) != 1:
            raise ValueError(f"Ambiguous graphic target: {entry}")
        image_bundles[matches[0]["source"]].append(entry)
    for rel, entries in image_bundles.items():
        # resources.assets also holds the translated table and font fallback.
        # Keep earlier edits when a texture shares their serialized file.
        env = UnityPy.load(str(current_source(rel)))
        for entry in entries:
            obj = next(o for o in env.objects if o.path_id == entry["path_id"])
            data = obj.read()
            image = Image.open(ROOT / "assets/images" / entry["file"]).convert("RGBA")
            # Import-time resampling only; artwork and lettering remain image_gen output.
            data.set_image(image.resize((data.m_Width, data.m_Height), Image.Resampling.LANCZOS), target_format=4)
            data.save()
        data = env.file.save(packer="lz4") if isinstance(env.file, UnityPy.files.BundleFile) else env.file.save()
        save(rel, data)

    rel = tutorial_atlas.bundle_path()
    save(rel, tutorial_atlas.build(current_source(rel)))

    rel = "alicenation_Data/StreamingAssets/aa/catalog.json"
    save(rel, update_catalog(source(rel), args.game, args.output, list(records)))

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps({"game_version": version,
        "patch_version": "v1-draft" if missing or tutorial["pending"] else "v1",
        "translated": len(translated), "total": len(japanese), "missing": len(missing),
        "tutorial": tutorial, "static_ui": len(static_ui.entries()),
        "files": list(records.values())}, ensure_ascii=False, indent=2), "utf-8")
    print(f"Built {len(records)} patched files in {args.output}")

if __name__ == "__main__":
    main()
