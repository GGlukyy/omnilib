"""Convert packs/<source>/<pack>/** (GLB/GLTF/FBX/OBJ) into library/<source>/<pack>/*.blend with marked assets.

Run headless (or via `pip install bpy`):
    blender -b --factory-startup -P scripts/mark_assets.py -- <packs_dir> <library_dir> [--public] [--force]

One .blend per model. A single mesh is marked as an object asset, several objects become a marked collection.
Metadata: defaults <- packs/<source>/<pack>/pack.json <- <model stem>.json (written by sources/*).
Catalog: meta "catalog" or "<source>/<pack>"; written to <library>/blender_assets.cats.txt.
--public keeps CC0 only. .blend files without a (kept) source are deleted, so the library mirrors packs/.
Incremental: a .blend newer than its model and metadata is not rebuilt (--force rebuilds all).
"""

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

import bpy

IMPORTERS = {
    ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    ".obj": lambda p: bpy.ops.wm.obj_import(filepath=p),
}
PREFERENCE = [".glb", ".gltf", ".fbx", ".obj"]
DEFAULTS = {"license": "CC0-1.0", "author": ""}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--public", action="store_true", help="CC0 only")
    ap.add_argument("--force", action="store_true", help="rebuild every .blend")
    return ap.parse_args(argv)


def read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def is_cc0(license: str) -> bool:
    return "CC0" in license.upper().replace(" ", "") or "PUBLIC DOMAIN" in license.upper()


def cat_uuid(path: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "omnilib:" + path))


def find_models(src_root: Path):
    """-> {(source, pack, name): (model_path, meta, deps)}, one model per name (GLB preferred)."""
    best = {}
    for p in src_root.rglob("*"):
        ext = p.suffix.lower()
        if ext not in IMPORTERS or len(p.relative_to(src_root).parts) < 3:
            continue
        source, pack = p.relative_to(src_root).parts[:2]
        pack_json = src_root / source / pack / "pack.json"
        sidecar = p.with_suffix(".json")
        # a folder with sidecars only builds models that have one (skips LODs/extras in downloaded zips)
        if not sidecar.exists() and any(j.name != "pack.json" for j in p.parent.glob("*.json")):
            continue
        meta = {**DEFAULTS, **read_json(pack_json), **read_json(sidecar)}
        meta.setdefault("catalog", f"{source}/{pack}")
        name = meta.get("name") or p.stem
        key = (source, pack, name.lower())
        if key not in best or PREFERENCE.index(ext) < PREFERENCE.index(best[key][0].suffix.lower()):
            best[key] = (p, meta, [p, sidecar, pack_json])
    return best


def fill_metadata(asset_data, meta, source, pack):
    asset_data.author = meta["author"]
    asset_data.catalog_id = cat_uuid(meta["catalog"])
    asset_data.description = meta.get("attribution") or meta.get("url", "")
    if hasattr(asset_data, "license"):  # copyright/license fields exist on newer Blender versions only
        asset_data.license = meta["license"]
    for tag in (source, pack):
        asset_data.tags.new(tag, skip_if_exists=True)


def convert(src: Path, out: Path, meta, source, pack) -> bool:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        IMPORTERS[src.suffix.lower()](str(src))
    except Exception as e:  # a broken file must not stop the whole build
        print(f"[skip] {src}: {e}")
        return False

    objs = [o for o in bpy.context.scene.objects if o.type in {"MESH", "CURVE", "ARMATURE", "EMPTY"}]
    if not objs:
        print(f"[skip] {src}: nothing imported")
        return False

    name = meta.get("title") or src.stem
    meshes = [o for o in objs if o.type == "MESH"]
    if len(objs) == 1 and meshes:
        target = meshes[0]
        target.name = name
    else:
        target = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(target)
        for o in objs:
            for c in o.users_collection:
                c.objects.unlink(o)
            target.objects.link(o)

    target.asset_mark()
    fill_metadata(target.asset_data, meta, source, pack)
    try:
        target.asset_generate_preview()
    except Exception:
        pass  # the listing generator renders previews too

    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()  # textures inside the .blend, no broken paths
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    return True


def write_catalogs(out_root: Path, paths):
    every = set()
    for p in paths:  # parents too, so the tree shows up even for empty levels
        parts = p.split("/")
        every.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    lines = ["# Asset catalogs written by omnilib scripts/mark_assets.py", "VERSION 1", ""]
    lines += [f"{cat_uuid(p)}:{p}:{p.replace('/', '-').replace(' ', '_')}" for p in sorted(every)]
    (out_root / "blender_assets.cats.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    src_root, out_root = Path(args.src), Path(args.out)
    keep, catalogs, ok, skipped = set(), set(), 0, 0
    attributions = []
    for (source, pack, _), (src, meta, deps) in sorted(find_models(src_root).items()):
        if args.public and not is_cc0(meta["license"]):
            continue
        out = out_root / source / pack / f"{meta.get('name') or src.stem}.blend"
        newest = max(d.stat().st_mtime for d in deps if d.exists())
        if args.force or not out.exists() or out.stat().st_mtime < newest:
            if not convert(src, out, meta, source, pack):
                continue
            ok += 1
        else:
            skipped += 1
        keep.add(out.resolve())
        catalogs.add(meta["catalog"])
        if not is_cc0(meta["license"]):
            attributions.append(meta.get("attribution") or f"{meta.get('title', src.stem)} by {meta['author']} ({meta['license']})")

    # library mirrors packs/: drop .blend files (and their thumbnails) whose source is gone or filtered out
    for blend in out_root.rglob("*.blend"):
        if blend.resolve() not in keep:
            print(f"[remove] {blend.relative_to(out_root)}")
            blend.unlink()
            shutil.rmtree(blend.with_name(blend.stem + "_thumbnails"), ignore_errors=True)

    out_root.mkdir(parents=True, exist_ok=True)
    write_catalogs(out_root, catalogs)
    attribution_file = out_root / "ATTRIBUTION.txt"
    if attributions:
        attribution_file.write_text("\n".join(sorted(attributions)) + "\n", encoding="utf-8")
    elif attribution_file.exists():
        attribution_file.unlink()
    print(f"done: {ok} converted, {skipped} up to date, {len(keep)} in library")


main()
