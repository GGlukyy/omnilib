"""Import one downloaded model into the scene and record author / licence / source."""

import bpy

TEXT = "omnilib_attribution"
POLY_NOTICE = "Provided by Poly Pizza (https://poly.pizza)"


def attribution_line(item):
    # Poly Pizza ships a ready-made attribution string per model; use it when present
    return item.get("attribution") or (
        f'"{item["title"]}" by {item["author"] or "unknown"} ({item["license"]}), {item["url"]} [{item["source"]}]')


def _add_text(item):
    text = bpy.data.texts.get(TEXT) or bpy.data.texts.new(TEXT)
    body = text.as_string()
    lines = [attribution_line(item)] + ([POLY_NOTICE] if item["source"] == "polypizza" else [])
    add = [ln for ln in lines if ln not in body]
    if add:
        text.from_string(body + "".join(ln + "\n" for ln in add))


def import_model(path, item):
    """Import `path`, put the result into its own collection. Returns the collection."""
    objects, images = set(bpy.data.objects), set(bpy.data.images)
    ext = path.suffix.lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.wm.obj_import(filepath=str(path))

    for img in bpy.data.images:  # the temp folder is deleted afterwards: keep textures inside the .blend
        if img not in images and img.source == "FILE" and not img.packed_file:
            try:
                img.pack()
            except RuntimeError:
                pass

    coll = bpy.data.collections.new(item["title"])
    bpy.context.scene.collection.children.link(coll)
    for obj in [o for o in bpy.data.objects if o not in objects]:
        for c in obj.users_collection:
            c.objects.unlink(obj)
        coll.objects.link(obj)

    meta = {"omnilib_source": item["source"], "omnilib_author": item["author"],
            "omnilib_license": item["license"], "omnilib_url": item["url"]}
    for k, v in meta.items():
        coll[k] = v
    try:  # asset metadata, so the import shows up in the Asset Browser (Current File) with its origin
        coll.asset_mark()
        coll.asset_data.author = item["author"]
        coll.asset_data.description = f'{item["title"]} - {item["url"]} ({item["license"]})'
        for field in ("license", "copyright"):  # only in newer Blender versions
            if hasattr(coll.asset_data, field):
                setattr(coll.asset_data, field, item["license"] if field == "license" else attribution_line(item))
    except (RuntimeError, AttributeError):
        pass
    _add_text(item)
    return coll
