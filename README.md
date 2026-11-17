# omnilib (working name)

Turn any 3D asset source into a native Blender 5.3 online asset library.

## Phase 0 quick start (Windows)
1. Download a Kenney 3D pack and unzip it into `packs/<pack-name>/`.
2. Run:
   ```powershell
   .\scripts\build.ps1 -Blender "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
   ```
3. Blender → Preferences → Asset Libraries → add online library `http://127.0.0.1:8000/`.

Rules for AI agents: `AGENTS.md`. Plan: `docs/MILESTONES.md`.
