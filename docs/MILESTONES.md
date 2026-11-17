# Milestones

## Phase 0: proof ✅ done 17. 11. 2026
- [x] Download 1 Kenney pack (kenney.nl), unzip into `packs/<pack-name>/`
- [x] `scripts/build.py` runs without errors
- [x] Add `http://127.0.0.1:8000/` as a remote library in Blender 5.3, assets appear with previews
- [x] Append an asset into a scene
- [x] Read the generated `_v1/` JSON: are there per-file hashes? Write the answer into `docs/FINDINGS.md`
- **Stop condition:** if Blender refuses the library, find out why before anything else.

## Phase 1: hosted CC0 game library (weekend) ← CURRENT
Done (branch `phase-1`, verified in CI on `ubuntu-latest`, 6 green runs):
- [x] Source adapters `sources/<name>.py` (`list()` + `download()`), chosen in `subscriptions.json`
- [x] `local`: zips/folders in `packs/local/`
- [x] `asset_server`: 3d-asset-server as CI service container, CC0 only, saved searches, 1k, max 25 MB/asset
- [x] `polypizza`: official API v1.1 (authors Kenney, Quaternius + searches); skipped with a warning without key
- [x] `scripts/pipeline.py`: download only new items (cache `packs/.state.json`) → `build.py`
- [x] Catalogs `<source>/<pack>`, author/license/attribution per asset, `--public` = CC0 only, `ATTRIBUTION.txt` locally
- [x] CI `build-library`: manual + weekly, `bpy==5.3.0`, cache of `packs/` + `library/`
- [x] Blender extensions repository (`extensions/omnilib`, type `asset-library`), built with Blender's `blender_ext.py`
- [x] GitHub Pages deploy from `master`: `/index.json` + `/library/`, size check (1 GB site, 100 MB file)
- [x] README: "add this repository URL in Get Extensions"; Poly Haven Lite / ambientCG → official repository

Waiting for verification:
- [ ] Enable Pages (Settings → Pages → Source: GitHub Actions), merge, first deploy from `master`
- [ ] Blender 5.3: add `https://gglukyy.github.io/omnilib/` in Get Extensions → install omnilib → assets visible + append works
- [ ] Add `POLY_PIZZA_KEY` secret → first real Poly Pizza run (only mocked so far): time, size, CC0 count vs 1 GB Pages limit
- [ ] Previews: thumbnails rendered on headless Linux look right (only verified on Windows in phase 0)
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
