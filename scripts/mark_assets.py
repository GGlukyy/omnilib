"""Convert a folder of 3D models (GLB/GLTF/FBX/OBJ) into .blend files with marked assets.

Run headless:
    blender -b --factory-startup -P scripts/mark_assets.py -- <src_dir> <out_dir> [--author NAME] [--license NAME] [--tag TAG]

One .blend per source file. A single mesh is marked as an object asset,
several objects are grouped into a collection and the collection is marked.
"""

import argparse
import sys
from pathlib import Path

import bpy

IMPORTERS = {
    ".glb": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".gltf": lambda p: bpy.ops.import_scene.gltf(filepath=p),
    ".fbx": lambda p: bpy.ops.import_scene.fbx(filepath=p),
    ".obj": lambda p: bpy.ops.wm.obj_import(filepath=p),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--author", default="")
    ap.add_argument("--license", default="CC0-1.0")
    ap.add_argument("--tag", action="append", default=[])
    return ap.parse_args(argv)


def fill_metadata(asset_data, args, pack):
    asset_data.author = args.author
    # copyright/license fields exist on newer Blender versions only
    if hasattr(asset_data, "license"):
        asset_data.license = args.license
    for tag in [pack, *args.tag]:
        if tag:
            asset_data.tags.new(tag, skip_if_exists=True)


def convert(src: Path, out_dir: Path, args, pack: str) -> bool:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        IMPORTERS[src.suffix.lower()](str(src))
    except Exception as e:  # broken file must not stop the whole pack
        print(f"[skip] {src.name}: {e}")
        return False

    objs = [o for o in bpy.context.scene.objects if o.type in {"MESH", "CURVE", "ARMATURE", "EMPTY"}]
    if not objs:
        print(f"[skip] {src.name}: nothing imported")
        return False

    name = src.stem
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
    fill_metadata(target.asset_data, args, pack)
    try:
        target.asset_generate_preview()
    except Exception:
        pass  # listing generator renders previews too

    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()  # textures inside the .blend, no broken paths
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / f"{name}.blend"), compress=True)
    return True


def main():
    args = parse_args()
    src_root, out_root = Path(args.src), Path(args.out)
    files = [p for p in src_root.rglob("*") if p.suffix.lower() in IMPORTERS]
    ok = 0
    for f in sorted(files):
        pack = f.relative_to(src_root).parts[0] if f.parent != src_root else src_root.name
        ok += convert(f, out_root / pack, args, pack)
    print(f"done: {ok}/{len(files)} converted")


main()
