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
4. Asset Browser → pick the library → drag an asset into the scene.

## Rebuild after adding packs
Unzip packs into `packs/<pack-name>/`, then either
- `pip install bpy==5.3.0` (Python 3.13) and `python scripts/build.py --serve`, or
- `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Blender "<path to blender.exe>"` (Blender 5.3 required)

Rules for AI agents: `AGENTS.md`. Plan: `docs/MILESTONES.md`. What we learned: `docs/FINDINGS.md`.
