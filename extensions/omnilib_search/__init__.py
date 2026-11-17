"""omnilib: one search over Poly Pizza, Sketchfab and 3d-asset-server.

Import a result by clicking it, or drag it from the Asset Browser ("omnilib search results" library) into the
scene: a placeholder is swapped for the downloaded model at the same place (see dragdrop.py).

Keys live in the add-on preferences (password fields, plain text in userpref.blend like every Blender
add-on setting). They are only sent to their own service and never printed.
"""

import os
import shutil
import tempfile
import threading

import bpy
import bpy.utils.previews

from . import dragdrop, importer, providers

_state = {"items": [], "errors": [], "busy": False, "done": None}
_pcoll = None
_thumbs = None  # temp dir for preview images of the current search

SOURCE_LABELS = {"polypizza": "Poly Pizza", "sketchfab": "Sketchfab", "asset_server": "3d-asset-server"}


def _prefs(context=None):
    return (context or bpy.context).preferences.addons[__package__].preferences


def _keys(context=None):
    p = _prefs(context)
    return {"polypizza": p.polypizza_key, "sketchfab": p.sketchfab_token, "asset_server": p.asset_server_url}


def _cache_dir():
    return bpy.utils.extension_path_user(__package__, path="cache", create=True)


def _library_dir():
    return bpy.utils.extension_path_user(__package__, path="placeholders", create=True)


def _filters(wm):
    return {"sources": tuple(s for s in SOURCE_LABELS if getattr(wm, f"omnilib_src_{s}")),
            "license": wm.omnilib_license, "format": wm.omnilib_format, "animated": wm.omnilib_animated,
            "rigged": wm.omnilib_rigged, "min_faces": wm.omnilib_min_faces, "max_faces": wm.omnilib_max_faces}


def _settings():
    wm = bpy.context.window_manager
    return _keys(), _cache_dir(), wm.omnilib_format


class OmnilibPrefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    polypizza_key: bpy.props.StringProperty(name="Poly Pizza key", subtype="PASSWORD")
    sketchfab_token: bpy.props.StringProperty(name="Sketchfab API token", subtype="PASSWORD")
    asset_server_url: bpy.props.StringProperty(
        name="3d-asset-server URL", description="Optional, e.g. http://localhost:8787. No key needed")
    cache_mb: bpy.props.IntProperty(
        name="Cache limit (MB)", default=1024, min=64, soft_max=8192,
        description="Downloaded models are kept here; the least recently used ones are deleted above this size")

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Only sources with a filled field are searched.")
        col.prop(self, "polypizza_key")
        col.operator("wm.url_open", text="Get a Poly Pizza key", icon="URL").url = "https://poly.pizza/settings/api"
        col.prop(self, "sketchfab_token")
        col.operator("wm.url_open", text="Get a Sketchfab token", icon="URL").url = "https://sketchfab.com/settings/password"
        col.prop(self, "asset_server_url")
        col.separator()
        col.prop(self, "cache_mb")
        col.operator("omnilib.clear_cache", icon="TRASH")


def _poll():
    """Timer: pick up the finished search (previews must be loaded on the main thread)."""
    done = _state["done"]
    if done is None:
        return 0.3
    items, errors = done
    _pcoll.clear()
    for i, it in enumerate(items):
        if it.get("thumb_path"):
            try:
                _pcoll.load(str(i), it["thumb_path"], "IMAGE")
            except Exception:
                pass
    if items:  # placeholders for drag & drop from the Asset Browser
        try:
            dragdrop.build_library(items, _library_dir())
        except Exception as e:
            errors = errors + [f"drag & drop library: {type(e).__name__}"]
    _state.update(items=items, errors=errors, busy=False, done=None)
    bpy.context.window_manager.omnilib_page = 0
    dragdrop._redraw()
    return None


class OMNILIB_OT_search(bpy.types.Operator):
    bl_idname = "omnilib.search"
    bl_label = "Search"

    def execute(self, context):
        global _thumbs
        wm, keys = context.window_manager, _keys(context)
        q = wm.omnilib_query.strip()
        if _state["busy"] or not q:
            return {"CANCELLED"}
        if not any(keys.values()):
            self.report({"ERROR"}, "Fill in a key in the add-on preferences first")
            return {"CANCELLED"}
        if _thumbs:
            shutil.rmtree(_thumbs, ignore_errors=True)
        _thumbs = tempfile.mkdtemp(prefix="omnilib_thumbs_")
        _state.update(busy=True, items=[], errors=[], done=None)
        flt, thumbs = _filters(wm), _thumbs

        def work():
            try:
                _state["done"] = providers.search(q, flt, keys, thumbs)
            except Exception as e:
                _state["done"] = ([], [providers.error_text(e)])

        threading.Thread(target=work, daemon=True).start()
        bpy.app.timers.register(_poll, first_interval=0.3)
        return {"FINISHED"}


class OMNILIB_OT_import(bpy.types.Operator):
    bl_idname = "omnilib.import"
    bl_label = "Import"
    bl_description = "Download this model (cached) and place it at the 3D cursor. You can also drag it from the Asset Browser"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = _state["items"][self.index]
        if providers.item_key(item) in dragdrop.status and dragdrop.status[providers.item_key(item)] == "downloading":
            return {"CANCELLED"}
        # same path as a drop: a placeholder at the cursor, the handler downloads and swaps it
        dragdrop.spawn_placeholder(item, context.scene.cursor.location)
        return {"FINISHED"}


class OMNILIB_OT_page(bpy.types.Operator):
    bl_idname = "omnilib.page"
    bl_label = "Page"
    bl_options = {"INTERNAL"}

    step: bpy.props.IntProperty()

    def execute(self, context):
        wm = context.window_manager
        wm.omnilib_page = providers.page_slice(_state["items"], wm.omnilib_page + self.step)[0] // providers.PAGE_SIZE
        return {"FINISHED"}


class OMNILIB_OT_clear_cache(bpy.types.Operator):
    bl_idname = "omnilib.clear_cache"
    bl_label = "Clear model cache"
    bl_description = "Delete all downloaded models kept by omnilib"

    def execute(self, context):
        providers.clear_cache(_cache_dir())
        dragdrop.status.clear()
        self.report({"INFO"}, "omnilib cache cleared")
        return {"FINISHED"}


def _status_row(layout, item):
    st = dragdrop.status.get(providers.item_key(item), "")
    if st == "downloading":
        layout.label(text="Downloading...", icon="TIME")
    elif st in ("done", "cached"):
        layout.label(text="Imported" + (" (from cache)" if st == "cached" else ""), icon="CHECKMARK")
    elif st.startswith("error"):
        layout.label(text=st[7:], icon="ERROR")


class OMNILIB_PT_panel(bpy.types.Panel):
    bl_label = "omnilib"
    bl_idname = "OMNILIB_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "omnilib"

    def draw(self, context):
        wm, layout = context.window_manager, self.layout
        row = layout.row(align=True)
        row.prop(wm, "omnilib_query", text="")
        row.operator("omnilib.search", text="", icon="VIEWZOOM")
        if _state["busy"]:
            layout.label(text="Searching...", icon="TIME")
        for err in _state["errors"]:
            layout.label(text=err, icon="ERROR")
        items = _state["items"]
        if not items:
            return
        offset, shown = providers.page_slice(items, wm.omnilib_page)
        pages = providers.page_count(len(items))
        row = layout.row(align=True)
        row.operator("omnilib.page", text="", icon="TRIA_LEFT").step = -1
        row.label(text=f"{offset // providers.PAGE_SIZE + 1} / {pages}  ({len(items)} results)")
        row.operator("omnilib.page", text="", icon="TRIA_RIGHT").step = 1
        layout.prop(wm, "omnilib_thumb_size", slider=True)
        layout.label(text="Drag from the shelf below the viewport", icon="INFO")
        grid = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
        for n, it in enumerate(shown):
            i = offset + n
            box = grid.box().column(align=True)
            if str(i) in _pcoll:
                box.template_icon(icon_value=_pcoll[str(i)].icon_id, scale=wm.omnilib_thumb_size)
            box.operator("omnilib.import", text=it["title"], icon="IMPORT").index = i
            box.label(text=f'{it["author"]} | {it["license"]}')
            box.label(text=SOURCE_LABELS.get(it["source"], it["source"]))
            _status_row(box, it)


class OMNILIB_PT_filters(bpy.types.Panel):
    bl_label = "Filters"
    bl_idname = "OMNILIB_PT_filters"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "omnilib"
    bl_parent_id = "OMNILIB_PT_panel"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        wm, layout = context.window_manager, self.layout
        col = layout.column(align=True)
        col.label(text="Stores")
        for s, label in SOURCE_LABELS.items():
            col.prop(wm, f"omnilib_src_{s}", text=label)
        layout.prop(wm, "omnilib_license")
        layout.prop(wm, "omnilib_format")
        box = layout.box()
        box.label(text="Sketchfab only")
        box.prop(wm, "omnilib_animated")
        box.prop(wm, "omnilib_rigged")
        row = box.row(align=True)
        row.prop(wm, "omnilib_min_faces", text="Min polys")
        row.prop(wm, "omnilib_max_faces", text="Max polys")
        layout.label(text="Filters apply to the next search")


class OMNILIB_AST_results(bpy.types.AssetShelf):
    """Search results as a shelf at the bottom of the 3D viewport: drag a preview into the scene."""
    bl_space_type = "VIEW_3D"
    bl_idname = "OMNILIB_AST_results"
    bl_options = {"DEFAULT_VISIBLE"}
    bl_default_preview_size = 96

    @classmethod
    def poll(cls, context):
        return bool(_state["items"]) and context.mode == "OBJECT"

    @classmethod
    def asset_poll(cls, asset):  # only our placeholders, whichever library the shelf is set to
        return asset.id_type == "OBJECT" and os.path.normcase(os.path.dirname(asset.full_library_path)) ==             os.path.normcase(os.path.normpath(_library_dir()))


classes = (OmnilibPrefs, OMNILIB_OT_search, OMNILIB_OT_import, OMNILIB_OT_page, OMNILIB_OT_clear_cache,
           OMNILIB_PT_panel, OMNILIB_PT_filters, OMNILIB_AST_results)

_wm_props = {
    "omnilib_query": bpy.props.StringProperty(name="Search", default=""),
    "omnilib_page": bpy.props.IntProperty(default=0, min=0),
    "omnilib_thumb_size": bpy.props.FloatProperty(name="Preview size", default=6.0, min=3.0, max=12.0),
    "omnilib_license": bpy.props.EnumProperty(name="License", items=[
        ("all", "All", "Any licence (the licence is shown on each result)"),
        ("cc0", "CC0 only", "Public domain, no credit needed"),
        ("ccby", "CC0 + CC-BY", "Credit required for CC-BY (written to the omnilib_attribution text)")]),
    "omnilib_format": bpy.props.EnumProperty(name="Format", items=[
        ("any", "Any", "Best available: glb, gltf, fbx, obj"),
        ("glb", "glTF / GLB", "Offered by all stores"),
        ("fbx", "FBX", "Only 3d-asset-server offers it"),
        ("obj", "OBJ", "Only 3d-asset-server offers it")]),
    "omnilib_animated": bpy.props.BoolProperty(name="Animated", default=False),
    "omnilib_rigged": bpy.props.BoolProperty(name="Rigged", default=False),
    "omnilib_min_faces": bpy.props.IntProperty(name="Min polys", default=0, min=0),
    "omnilib_max_faces": bpy.props.IntProperty(name="Max polys", default=0, min=0, description="0 = no limit"),
    **{f"omnilib_src_{s}": bpy.props.BoolProperty(name=label, default=True) for s, label in SOURCE_LABELS.items()},
}


def register():
    global _pcoll
    _pcoll = bpy.utils.previews.new()
    for c in classes:
        bpy.utils.register_class(c)
    for name, prop in _wm_props.items():
        setattr(bpy.types.WindowManager, name, prop)
    dragdrop.register(_settings)
    try:
        providers.trim_cache(_cache_dir(), _prefs().cache_mb)
    except Exception:
        pass  # prefs not ready yet: trimmed on the next start


def unregister():
    global _thumbs
    dragdrop.unregister()
    for name in _wm_props:
        delattr(bpy.types.WindowManager, name)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    bpy.utils.previews.remove(_pcoll)
    if _thumbs:
        shutil.rmtree(_thumbs, ignore_errors=True)
        _thumbs = None
