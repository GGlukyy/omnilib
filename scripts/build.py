"""Build the library: packs/ -> library/*.blend -> official listing (JSON + previews).

Needs Blender as a Python module:  pip install bpy==5.3.0   (Python 3.13)
Usage:  python scripts/build.py [--public] [--force] [--serve]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--public", action="store_true", help="CC0 assets only (for a hosted library)")
ap.add_argument("--force", action="store_true", help="rebuild every .blend")
ap.add_argument("--serve", action="store_true", help="serve library/ on http://127.0.0.1:8000/")
args = ap.parse_args()

packs, library = ROOT / "packs", ROOT / "library"
library.mkdir(exist_ok=True)

# 1. models -> .blend with marked assets + catalogs (separate process: one clean Blender session)
flags = [f for f, on in (("--public", args.public), ("--force", args.force)) if on]
subprocess.run([sys.executable, str(ROOT / "scripts/mark_assets.py"), "--", str(packs), str(library), *flags],
               check=True)

# 2. library name/contact (the generator keeps an existing meta file)
shutil.copy(ROOT / "library-meta.json", library / "_asset-library-meta.json")

# 3. official Blender listing generator (same as `blender -c asset_listing generate`)
import bpy  # noqa: F401,E402  (makes _bpy_internal importable)
from _bpy_internal.assets.remote_library import cli  # noqa: E402
cli.main(["generate", str(library)])

if args.serve:
    print("\nAdd this online library in Blender: http://127.0.0.1:8000/")
    subprocess.run([sys.executable, "-m", "http.server", "8000", "--bind", "127.0.0.1"], cwd=library)
