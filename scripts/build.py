"""Build the library: packs/ -> library/*.blend -> official listing (JSON + previews).

Needs Blender as a Python module:  pip install bpy==5.3.0   (Python 3.13)
Usage:  python scripts/build.py [--author Kenney] [--serve]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--author", default="Kenney")
ap.add_argument("--serve", action="store_true", help="serve library/ on http://127.0.0.1:8000/")
args = ap.parse_args()

packs, library = ROOT / "packs", ROOT / "library"

# 1. models -> .blend with marked assets (separate process: one clean Blender session)
subprocess.run([sys.executable, str(ROOT / "scripts/mark_assets.py"), "--",
                str(packs), str(library), "--author", args.author], check=True)

# 2. library name/contact (the generator keeps an existing meta file)
shutil.copy(ROOT / "library-meta.json", library / "_asset-library-meta.json")

# 3. official Blender listing generator (same as `blender -c asset_listing generate`)
import bpy  # noqa: F401  (makes _bpy_internal importable)
from _bpy_internal.assets.remote_library import cli
cli.main(["generate", str(library)])

if args.serve:
    print("\nAdd this online library in Blender: http://127.0.0.1:8000/")
    subprocess.run([sys.executable, "-m", "http.server", "8000", "--bind", "127.0.0.1"], cwd=library)
