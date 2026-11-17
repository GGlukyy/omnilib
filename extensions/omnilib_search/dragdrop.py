"""Drag & drop from the Asset Browser: search results become placeholder assets in a temporary local asset
library. When a placeholder is dropped into the scene, a handler downloads the real model and swaps it in at
the same transform (placeholder = Empty with a preview and the item stored in a custom property)."""

import json
import shutil
import tempfile
import threading
from pathlib import Path

import bpy

from . import importer, providers

PROP = "omnilib_item"  # JSON of the search item, set on the placeholder
LIB_NAME = "omnilib search results"
CATALOG_FILE = "results.blend"

_keys_getter = lambda: {}  # set by register(); returns the keys dict from the add-on preferences
_jobs = {}  # placeholder object name -> {"thread", "result", "tmp"}
_queue = []  # placeholder names seen by the depsgraph handler, picked up by the timer
status = {}  # item id -> "downloading" | "done" | "error: ..."  (shown in the panel)


# --- placeholder library ----------------------------------------------------------------------------

def _set_preview(ob, thumb_path):
    img = bpy.data.images.load(thumb_path)
    try:
        img.scale(128, 128)
        pv = ob.preview_ensure()
        pv.image_size = (128, 128)
        pv.image_pixels_float = list(img.pixels)
    finally:
        bpy.data.images.remove(img)


def build_library(items, folder):
    """Write one placeholder Empty per item into folder/results.blend and register the folder as an asset
    library. Returns the .blend path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    for it in items:
        ob = bpy.data.objects.new(f'{it["title"]} [{it["source"]}]', None)
        ob.empty_display_type, ob.empty_display_size = "CUBE", 0.5
        ob[PROP] = json.dumps({k: v for k, v in it.items() if k != "thumb_path"})
        ob.asset_mark()
        ob.asset_data.author = it.get("author", "")
        ob.asset_data.description = f'{it["title"]} - {it["license"]} - {it["url"]}'
        if it.get("thumb_path"):
            try:
                _set_preview(ob, it["thumb_path"])
            except Exception:
                pass  # no preview, still draggable
        made.append(ob)
    path = folder / CATALOG_FILE
    bpy.data.libraries.write(str(path), set(made), fake_user=True)
    for ob in made:
        bpy.data.objects.remove(ob)
    libs = bpy.context.preferences.filepaths.asset_libraries
    if LIB_NAME not in libs:
        libs.new(name=LIB_NAME, directory=str(folder))
    libs[LIB_NAME].import_method = "APPEND"  # a linked placeholder could not be replaced
    return path


def remove_library():
    libs = bpy.context.preferences.filepaths.asset_libraries
    if LIB_NAME in libs:
        libs.remove(libs[LIB_NAME])


# --- swap placeholder for the real model ------------------------------------------------------------

def _on_depsgraph(scene, depsgraph):
    for u in depsgraph.updates:
        ob = u.id.original if isinstance(u.id, bpy.types.Object) else None
        if ob is not None and ob.library is None and PROP in ob and ob.name not in _jobs and ob.name not in _queue:
            if not ob.get("omnilib_started"):
                ob["omnilib_started"] = True  # a copy of this object (duplicate) must not start a second job
                _queue.append(ob.name)
    if _queue and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.0)


def _start(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return
    item = json.loads(ob[PROP])
    job = {"result": None, "tmp": tempfile.mkdtemp(prefix="omnilib_"), "item": item}
    keys = _keys_getter()

    def work():
        try:
            job["result"] = ("ok", providers.download(item, job["tmp"], keys))
        except Exception as e:  # message only: never echo request details
            job["result"] = ("error", providers._err(item["source"], e))

    job["thread"] = threading.Thread(target=work, daemon=True)
    job["thread"].start()
    _jobs[name] = job
    status[item["id"]] = "downloading"
    ob.name = f'{item["title"]} (downloading)'
    _jobs[ob.name] = _jobs.pop(name)


def _finish(name, job):
    ob = bpy.data.objects.get(name)
    kind, value = job["result"]
    item = job["item"]
    try:
        if ob is None:
            return  # user deleted the placeholder while it was downloading
        if kind == "error":
            status[item["id"]] = f"error: {value}"
            ob.name = f'{item["title"]} (FAILED: {value})'
            return
        try:
            coll = importer.import_model(value, item)
        except Exception as e:
            status[item["id"]] = f"error: import failed ({type(e).__name__})"
            ob.name = f'{item["title"]} (FAILED: import)'
            return
        m = ob.matrix_world.copy()
        for o in coll.objects:
            if o.parent is None:
                o.matrix_world = m @ o.matrix_world
        bpy.data.objects.remove(ob)
        status[item["id"]] = "done"
    finally:
        shutil.rmtree(job["tmp"], ignore_errors=True)


def _tick():
    while _queue:
        _start(_queue.pop(0))
    for name, job in list(_jobs.items()):
        if job["result"] is not None:
            del _jobs[name]
            _finish(name, job)
    return 0.3 if (_jobs or _queue) else None


def register(keys_getter):
    global _keys_getter
    _keys_getter = keys_getter
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    _jobs.clear()
    _queue.clear()
    remove_library()
