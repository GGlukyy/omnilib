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
