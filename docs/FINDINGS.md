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

## Phase 1 (17. 11. 2026)
- **kenney.nl has no scriptable download.** Pack list is public HTML (`/assets/category:3D/page:N`), but the zip
  comes from `/download-link/<hex>` (signed URL, 403 for non-browser clients). Not used: AGENTS.md forbids
  non-public APIs. itch.io only has the paid All-in-1 bundle. 3d-asset-server's Kenney provider still assumes
  a direct zip link (likely broken for the same reason).
- **Poly Pizza API v1.1** (`https://api.poly.pizza/v1.1`, header `x-auth-token`, also for `static.poly.pizza`).
  `/user/{name}` (32 per page, `Page` from 0) returns `models` + `lists`; `/list/{id}` gives `Name` + `Models`;
  `/search/{kw}` has `License=1` (CC0). Model fields: `ID, Title, Download (.glb), Licence, Creator.Username,
  Attribution, Uploaded, Category`. Kenney: 452 models / 9 lists (old Google Poly packs, not the full catalog).
  Quaternius: 1411 models / 48 lists. ToS forbid scraping, the API is the allowed route. API `v1` is deprecated.
- **3d-asset-server**: `GET /v1/search?q=&type=model&free=true&downloadable=true`, result `license.name == "CC0"`;
  `GET /v1/assets/{provider:id}/download?format=` → 302 to a file or a zip. Poly Haven has no `glb` (404) →
  adapter tries glb, gltf, fbx, obj. Runs fine as a GitHub Actions service container, no keys needed.
- **Catalogs in the remote listing**: the generator reads every `*.cats.txt` under the library root and takes
  `catalog_id` from each asset (`_bpy_internal/assets/remote_library/listing_asset_catalogs.py`). Deterministic
  UUIDs (`uuid5`) keep catalogs stable across rebuilds.
- **Incremental build**: the generator re-renders thumbnails only when the .blend mtime changes
  (`<name>_thumbnails/.last_modified`), so skipping unchanged .blend files makes weekly runs cheap.
- `bpy==5.3.0` on `ubuntu-latest` needs `libxrender1 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libgl1 libegl1`.
- `workflow_dispatch` only works once the workflow is on the default branch → a branch tests itself via a `push` trigger.
- **Size is geometry, not textures.** Poly Haven photoscanned trees are 268–958 MB per model even at 1k
  textures (13 "pine tree" hits = 1.2 GB). `asset_server` checks `GET /v1/assets/{id}/files` → `totalBytes`
  and skips assets over 25 MB (GitHub Pages: 100 MB per file, 1 GB per site). Result: 10 assets, 14.8 MB.
- CI verified end-to-end on `ubuntu-latest` (run 4 of `phase-1`): service container, bpy build, listing,
  artifact, all green without `POLY_PIZZA_KEY` (Poly Pizza skipped with a warning).
- **Extensions repository** (verified in `bl_pkg/cli/blender_ext.py`, 5.3): type `asset-library` needs
  `[asset_library] remote_url = "http(s)://..."` (optional `[asset_library.auth]`, method `TOKEN`).
  `id` must be a Python identifier (no `-`, no `__`). Valid tags: Brush, Compositor, Geometry Nodes, Hair,
  Material, Model, Shading, World. `license = ["SPDX:CC0-1.0"]`. `server-generate` drops `[asset_library]` from
  `index.json`: Blender reads it from the downloaded zip and registers the remote library on install.
  The zip only contains `blender_manifest.toml` (421 bytes). `blender_ext.py` is stdlib-only and ships in the bpy wheel.
- Poly Haven Lite (`poly_haven`) and ambientCG (`ambientCG`) already exist as asset-library extensions on
  extensions.blender.org → not duplicated in our repository.
- GitHub Pages via `actions/deploy-pages` does not run Jekyll, so `_v1/` and `_asset-library-meta.json` are served.
- `import bpy` prints to stdout, so never capture `$(python -c "import bpy; ...")` in shell. Locate the
  package with `importlib.util.find_spec('bpy')` instead (`blender_ext.py` is at
  `bpy/5.3/scripts/addons_core/bl_pkg/cli/blender_ext.py` in the wheel).

## Add-on UX: drag & drop prototype (17. 11. 2026) - verdict: plan A works
**Tried (plan A):** search results become *placeholder assets* in a temporary local asset library
(`extensions/omnilib_search/dragdrop.py`). Each placeholder is an Empty marked as asset, with the result's thumbnail
as asset preview and the result (source, id, title, licence, download URL) as JSON in a custom property. The folder
is registered through `preferences.filepaths.asset_libraries.new()` with `import_method = "APPEND"`. A
`depsgraph_update_post` handler notices a new object carrying that property, downloads the model in a thread and a
timer swaps the placeholder for the imported model (same world matrix, placeholder deleted).

**Verified in Blender 5.3 (live, via MCP):**
- `bpy.data.libraries.write()` of asset-marked Empties creates a library the Asset Browser lists; custom previews set
  with `ID.preview_ensure()` + `image_pixels_float` survive the write and show in the browser.
- Appending a placeholder (what a drop does) triggers the handler; the swapped-in model sits exactly at the
  placeholder's location / rotation / scale (checked numerically). Failure (HTTP error) leaves the placeholder
  renamed "... (FAILED: reason)"; deleting the placeholder while downloading cancels the swap.
- Click-to-import uses the same path (placeholder at the 3D cursor), so there is one download code path.

**Gotchas**
- `import_method` must be `APPEND`: a *linked* placeholder is library data and can be neither modified nor deleted.
- The Asset Browser keeps the previously selected catalog id; a new library shows "No items" until the catalog is
  "All"/"Unassigned" again (test artefact, but users may hit it).
- `import` is a Python keyword: the operator `omnilib.import` can only be called as `getattr(bpy.ops.omnilib, "import")`.
- Not verified: a *real mouse drag* (cannot be simulated through MCP). The drop path in Blender's UI appends the
  asset through the same data API as `wm.append`, so the handler should fire identically. **Needs one manual check.**
- Plan B (own viewport strip with raycast) was not needed and was not built.

## Add-on filters (unverified API parameters)
- Sketchfab `animated`, `rigged`, `min_face_count`, `max_face_count`, `license=cc0` are sent as search parameters.
  The official docs page is a JS Swagger shell and could not be read, so **these names are from memory and
  unconfirmed** (a wrong name is silently ignored by the API). Verify with a real token before relying on them.
- Poly Pizza docs URL (`poly.pizza/docs/api`) returns 404; only `License=1` (CC0) is used, as before. Other licence
  filtering (CC-BY) is done client-side by `providers.license_class()` on the licence string.
- The format filter is honoured only by 3d-asset-server (glb/gltf/fbx/obj); Poly Pizza and Sketchfab downloads are
  glTF only, so choosing FBX/OBJ skips them.
