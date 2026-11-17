"""omnilib: one search over Poly Pizza, Sketchfab and 3d-asset-server, click = import one model.

Keys live in the add-on preferences (password fields, plain text in userpref.blend like every Blender
add-on setting). They are only sent to their own service and never printed.
"""

import shutil
import tempfile
import threading
from pathlib import Path

import bpy
import bpy.utils.previews

from . import importer, providers

_state = {"items": [], "errors": [], "busy": False, "done": None}
_pcoll = None
_thumbs = None  # temp dir for preview images of the current search


def _keys(context):
    p = context.preferences.addons[__package__].preferences
    return {"polypizza": p.polypizza_key, "sketchfab": p.sketchfab_token, "asset_server": p.asset_server_url}


class OmnilibPrefs(bpy.types.AddonPreferences):
    bl_idname = __package__

    polypizza_key: bpy.props.StringProperty(name="Poly Pizza key", subtype="PASSWORD")
    sketchfab_token: bpy.props.StringProperty(name="Sketchfab API token", subtype="PASSWORD")
    asset_server_url: bpy.props.StringProperty(
        name="3d-asset-server URL", description="Optional, e.g. http://localhost:8787. No key needed")

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Only sources with a filled field are searched.")
        col.prop(self, "polypizza_key")
        col.operator("wm.url_open", text="Get a Poly Pizza key", icon="URL").url = "https://poly.pizza/settings/api"
        col.prop(self, "sketchfab_token")
        col.operator("wm.url_open", text="Get a Sketchfab token", icon="URL").url = "https://sketchfab.com/settings/password"
        col.prop(self, "asset_server_url")


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
    _state.update(items=items, errors=errors, busy=False, done=None)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
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
        cc0, thumbs = wm.omnilib_cc0, _thumbs

        def work():
            try:
                _state["done"] = providers.search(q, cc0, keys, thumbs)
            except Exception as e:
                _state["done"] = ([], [type(e).__name__])

        threading.Thread(target=work, daemon=True).start()
        bpy.app.timers.register(_poll, first_interval=0.3)
        return {"FINISHED"}


class OMNILIB_OT_import(bpy.types.Operator):
    bl_idname = "omnilib.import"
    bl_label = "Import"
    bl_description = "Download this model and import it into the scene"

    index: bpy.props.IntProperty()

    def execute(self, context):
        item = _state["items"][self.index]
        tmp = tempfile.mkdtemp(prefix="omnilib_")
        try:
            path = providers.download(item, tmp, _keys(context))
            coll = importer.import_model(path, item)
        except Exception as e:  # message only: never echo request details
            self.report({"ERROR"}, f'{item["title"]}: {providers._err(item["source"], e)}')
            return {"CANCELLED"}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.report({"INFO"}, f'Imported "{coll.name}" ({item["license"]}), credit in text "{importer.TEXT}"')
        return {"FINISHED"}


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
        layout.prop(wm, "omnilib_cc0")
        if _state["busy"]:
            layout.label(text="Searching...", icon="TIME")
        for err in _state["errors"]:
            layout.label(text=err, icon="ERROR")
        for i, it in enumerate(_state["items"]):
            box = layout.box()
            if str(i) in _pcoll:
                box.template_icon(icon_value=_pcoll[str(i)].icon_id, scale=5)
            box.operator("omnilib.import", text=it["title"], icon="IMPORT").index = i
            box.label(text=f'{it["author"]} | {it["license"]} | {it["source"]}')


classes = (OmnilibPrefs, OMNILIB_OT_search, OMNILIB_OT_import, OMNILIB_PT_panel)


def register():
    global _pcoll
    _pcoll = bpy.utils.previews.new()
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.omnilib_query = bpy.props.StringProperty(name="Search", default="")
    bpy.types.WindowManager.omnilib_cc0 = bpy.props.BoolProperty(name="CC0 only", default=False)


def unregister():
    global _thumbs
    del bpy.types.WindowManager.omnilib_query, bpy.types.WindowManager.omnilib_cc0
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    bpy.utils.previews.remove(_pcoll)
    if _thumbs:
        shutil.rmtree(_thumbs, ignore_errors=True)
        _thumbs = None
