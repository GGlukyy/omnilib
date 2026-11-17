# Milestones

## Phase 0: proof ✅ done 17. 11. 2026
- [x] Download 1 Kenney pack (kenney.nl), unzip into `packs/<pack-name>/`
- [x] `scripts/build.py` runs without errors
- [x] Add `http://127.0.0.1:8000/` as a remote library in Blender 5.3, assets appear with previews
- [x] Append an asset into a scene
- [x] Read the generated `_v1/` JSON: are there per-file hashes? Write the answer into `docs/FINDINGS.md`
- **Stop condition:** if Blender refuses the library, find out why before anything else.

## Phase 1: hosted CC0 game library (weekend) ← CURRENT
- [ ] More packs (Kenney, Quaternius), catalogs per pack
- [ ] CI: headless Blender builds the library on push
- [ ] Hosting: static (GitHub Pages / Cloudflare R2), check size limits first
- [ ] README with "paste this URL into Blender"
- **Stop condition:** am I using it in my own projects? If not, stop.

## Phase 2: local vault (January, after Lucid Walls)
Owned packs (zip, FBX, .unitypackage, Fab download folder) → local library, fix texture paths.

## Phase 3+: dynamic sources
3d-asset-server (Docker, no fork unless we change it), saved searches as catalogs, Sketchfab OAuth.
