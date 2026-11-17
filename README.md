# omnilib (working name)

Turn any 3D asset source into a native Blender 5.3 online asset library.

## Install in Blender 5.3 (recommended)
1. Preferences → **System**: enable **Allow Online Access**.
2. Preferences → **Get Extensions** → **Repositories** (▾ top right) → **+ Add Remote Repository** →
   `https://gglukyy.github.io/omnilib/`
3. Get Extensions → search **omnilib** → **Install**. The library appears in the Asset Browser
   (catalogs `<source>/<pack>`), rebuilt weekly. CC0 only.

Poly Haven Lite and ambientCG are not in this repository: install them from Blender's official
repository (extensions.blender.org, enabled by default), search "Poly Haven" / "ambientCG".

## Use a locally built library
1. Open PowerShell in this folder and run:
   ```
   cd library
   python -m http.server 8000 --bind 127.0.0.1
   ```
   Keep the window open, it is the library server.
2. Blender 5.3 → Edit → Preferences → **System**: enable **Allow Online Access**.
3. Preferences → **Asset Libraries** → add an online library with URL `http://127.0.0.1:8000/`.
4. Asset Browser → pick the library → catalogs are `<source>/<pack>` → drag an asset into the scene.

The weekly GitHub Actions build (`build-library`) publishes the same CC0 library at `https://gglukyy.github.io/omnilib/library/`.

## Sources (`subscriptions.json`)
| Source | Subscription | Needs |
|---|---|---|
| `local` | `"all"` or pack names | zips or folders you downloaded yourself, in `packs/local/` |
| `polypizza` | `{"users": [...], "search": [...]}` | env `POLY_PIZZA_KEY` (poly.pizza → Settings → create app). Skipped without it. |
| `asset_server` | list of searches | a running [3d-asset-server](https://github.com/arielshad/3d-asset-server): `docker run -p 8787:8787 ghcr.io/arielshad/3d-asset-server` (env `OMNILIB_ASSET_SERVER` for another URL). Skipped if not reachable. |

Override license/author of a local pack with `packs/local/<pack>/pack.json`, e.g. `{"author": "Quaternius", "license": "CC0-1.0"}`.

## Build
`pip install bpy==5.3.0` (Python 3.13), then
```
python scripts/pipeline.py            # download new assets + build (CC0 and CC-BY, with ATTRIBUTION.txt)
python scripts/pipeline.py --public   # CC0 only, what CI publishes
python scripts/build.py --serve       # build only, then serve
```
With an installed Blender instead of `bpy`: `python scripts/pipeline.py --no-build`, then
`powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Blender "<path to blender.exe>"`.

Extensions repository: `extensions/<id>/blender_manifest.toml`, built in CI by Blender's own
`blender_ext.py build` + `server-generate`.

Rules for AI agents: `AGENTS.md`. Plan: `docs/MILESTONES.md`. What we learned: `docs/FINDINGS.md`.
