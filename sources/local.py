"""Manually downloaded packs: drop a zip (or an unzipped folder) into packs/local/.

subscriptions.json: "local": "all" or a list of pack names.
Zips are unzipped to packs/local/<pack>/ (version suffix like `_1.0` stripped).
Folders are built as they are. License defaults to CC0; override with packs/local/<pack>/pack.json.
"""

import re
import zipfile
from pathlib import Path

from . import write_meta

ROOT = Path(__file__).resolve().parent.parent / "packs" / "local"


def pack_name(zip_path: Path) -> str:
    return re.sub(r"_\d+(\.\d+)*$", "", zip_path.stem)


def list(sub):
    items = []
    for z in sorted(ROOT.glob("*.zip")):
        name = pack_name(z)
        if sub == "all" or name in sub:
            st = z.stat()
            items.append({"id": name, "pack": name, "zip": z, "version": f"{st.st_size}-{int(st.st_mtime)}"})
    return items


def download(item, dest: Path):
    with zipfile.ZipFile(item["zip"]) as zf:
        zf.extractall(dest)  # zipfile strips absolute paths and ".." itself
    if item["pack"].startswith("kenney_") and not (dest / "pack.json").exists():
        write_meta(dest / "pack.json", author="Kenney", license="CC0-1.0", url="https://kenney.nl")
