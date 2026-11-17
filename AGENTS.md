# AGENTS.md: shared rules for every AI tool in this repo

Claude Code (`CLAUDE.md`), Copilot (`.github/copilot-instructions.md`) and Antigravity read this file. Rules live **only here**.

## Project
Turns any 3D asset source into a **native Blender 5.3 Remote Asset Library** (.blend + JSON listing + previews).
It is a translator, not an aggregator. Current phase: see `docs/MILESTONES.md`.

## Hard rules
- Use Blender's official listing generator (`blender -c asset_listing generate`). Never hand-write listing JSON.
- Minimal code (ponytail mindset): stdlib first, no new dependency without a reason in the PR.
- Python 3.11, `bpy` only inside scripts run by Blender.
- Never commit `packs/` or `library/` (assets are build output).
- Only CC0 assets may be published in a hosted library. Anything else stays local.
- No reverse engineering of non-public APIs (Fab, Poliigon, Superhive). Proposals go to an issue first.
- Code from `docs/REFERENCES.md` may only be copied where the license column says so.

## Workflow
Plan first, then implement. One milestone = one PR. A PR needs: what changed, how it was tested, which model wrote it.
Review is done by a model from a different family than the author.
