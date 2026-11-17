# Milestones

## Phase 0: proof ✅ done 17. 11. 2026
- [x] Download 1 Kenney pack (kenney.nl), unzip into `packs/<pack-name>/`
- [x] `scripts/build.py` runs without errors
- [x] Add `http://127.0.0.1:8000/` as a remote library in Blender 5.3, assets appear with previews
- [x] Append an asset into a scene
- [x] Read the generated `_v1/` JSON: are there per-file hashes? Write the answer into `docs/FINDINGS.md`
- **Stop condition:** if Blender refuses the library, find out why before anything else.

## Phase 1: hosted CC0 game library (weekend) ← CURRENT
- [x] Source adapters `sources/<name>.py` (`list()` + `download()`), chosen in `subscriptions.json`
- [x] `local` (zips/folders in `packs/local/`), `asset_server` (3d-asset-server, CC0, saved searches)
- [x] `polypizza` (official API v1.1: Kenney, Quaternius by author + searches); skipped without `POLY_PIZZA_KEY`
- [x] `scripts/pipeline.py`: download only new items (cache `packs/.state.json`) → `build.py`
- [x] Catalogs `<source>/<pack>`, author/license/attribution per asset, `--public` = CC0 only
- [x] CI: manual + weekly, `bpy==5.3.0`, library as artifact (`build-library` workflow)
- [ ] Add `POLY_PIZZA_KEY` secret, check first full Kenney + Quaternius build (time, size)
- [ ] Remove the temporary `push` trigger from the workflow before merging `phase-1`
- [x] Blender extensions repository (`extensions/omnilib`, type `asset-library`) = entry point for users
- [x] Hosting on GitHub Pages: `/index.json` (extensions) + `/library/`, size check (1 GB site, 100 MB file)
- [ ] Enable Pages (Settings → Pages → Source: GitHub Actions), merge, check install from Get Extensions
- [x] README with "add this repository URL in Get Extensions"
- **Stop condition:** am I using it in my own projects? If not, stop.

## Phase 2: addon "omnilib" (in the same extensions repository)
N panel in the 3D View:
- Sketchfab: search + import (OAuth, attribution; `sketchfab/blender-plugin` is Apache-2.0)
- Poly Pizza: search + import (official API v1.1, user's own key)
- Fab: open the asset in the Epic Launcher + receive it over a local socket.
  Only with a documented/public protocol; otherwise an issue first (AGENTS.md: no reverse engineering).

## Phase 3: local vault
Owned packs (zip, FBX, .unitypackage, Fab download folder) → local library, fix texture paths.

## Phase 4+: dynamic sources
Saved searches as catalogs (partly done via `asset_server`), more 3d-asset-server sources, Sketchfab in CI.
