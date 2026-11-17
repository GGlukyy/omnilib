# Findings

## Phase 0 (17. 11. 2026), tested with `bpy 5.3.0` from PyPI
- **Per-file hashes are required.** `_v1/assets-00000.json` lists every .blend with `SHA256` + `size_in_bytes`,
  every thumbnail with `SHA256`. → .blend files must exist before the listing is generated.
  On-demand conversion is not possible; the bridge must pre-build (or cache) .blend files.
- Thumbnails (WebP) are rendered by the generator even in headless mode.
- `_asset-library-meta.json` is kept if it exists → we ship `library-meta.json` as the template.
- Blender 5.3 is installable via `pip install bpy==5.3.0` → CI does not need a Blender download.
- Generator source: `bpy/5.3/scripts/modules/_bpy_internal/assets/remote_library/`
  (incl. `blender_asset_library_openapi.yaml`, the full format spec).
- Kenney ships each model as .glb/.fbx/.obj → mark_assets keeps one per name (GLB preferred).
- Kenney Mini Forest: 22 models → 22 assets, 2.7 MB.
