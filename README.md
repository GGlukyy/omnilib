# omnilib (working name)

Turn any 3D asset source into a native Blender 5.3 online asset library.

## Use the library (already built)
1. Open PowerShell in this folder and run:
   ```
   cd library
   python -m http.server 8000 --bind 127.0.0.1
   ```
   Keep the window open, it is the library server.
2. Blender 5.3 → Edit → Preferences → **System**: enable **Allow Online Access**.
3. Preferences → **Asset Libraries** → add an online library with URL `http://127.0.0.1:8000/`.
4. Asset Browser → pick the library → catalogs are `<source>/<pack>` → drag an asset into the scene.

A ready CC0 build is also produced weekly by GitHub Actions (`build-library` workflow → artifact `omnilib-library`).

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

Rules for AI agents: `AGENTS.md`. Plan: `docs/MILESTONES.md`. What we learned: `docs/FINDINGS.md`.
