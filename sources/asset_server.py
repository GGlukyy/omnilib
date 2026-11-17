"""3d-asset-server (github.com/arielshad/3d-asset-server, Docker image ghcr.io/arielshad/3d-asset-server).

subscriptions.json: "asset_server": ["pine tree", ...]   (saved searches; each one becomes a pack/catalog)
Server URL: env OMNILIB_ASSET_SERVER (default http://localhost:8787). Only CC0 models are taken.
"""

import io
import os
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import UA, get_json, safe, warn, write_meta

URL = os.environ.get("OMNILIB_ASSET_SERVER", "http://localhost:8787").rstrip("/")
MODELS = [".glb", ".gltf", ".fbx", ".obj"]
PER_SEARCH = 24
RESOLUTION = "1k"  # game assets, small downloads
MAX_BYTES = 25_000_000  # per asset; GitHub Pages allows 100 MB per file


def list(sub):
    items = []
    for q in sub:
        query = urllib.parse.urlencode({"q": q, "type": "model", "free": "true", "downloadable": "true",
                                        "limit": PER_SEARCH})
        try:
            res = get_json(f"{URL}/v1/search?{query}")
        except OSError as e:
            warn(f"asset_server: {URL} not reachable ({e}), skipped")
            return []
        for r in res.get("results", []):
            if "CC0" in ((r.get("license") or {}).get("name") or "").upper():
                items.append({"id": r["id"], "pack": safe(q), "title": r.get("title"), "page": r.get("url"),
                              "author": r.get("author") or r["id"].split(":")[0], "catalog": f"asset_server/{safe(q)}",
                              "version": RESOLUTION})
    return items


def download(item, dest: Path):
    base = f"{URL}/v1/assets/{urllib.parse.quote(item['id'], safe=':')}"
    for fmt in ("glb", "gltf", "fbx", "obj"):  # sources offer different formats (Poly Haven: no glb)
        query = f"?resolution={RESOLUTION}&format={fmt}"
        files = get_json(f"{base}/files{query}")
        if not files.get("files"):
            continue
        if (files.get("totalBytes") or 0) > MAX_BYTES:  # photoscans: 100 MB of geometry, too big for Pages
            raise ValueError(f"{files['totalBytes'] / 1e6:.0f} MB, over the {MAX_BYTES / 1e6:.0f} MB limit")
        with urllib.request.urlopen(urllib.request.Request(f"{base}/download{query}", headers=UA), timeout=300) as r:
            data, final_url = r.read(), r.geturl()  # 302 to a single file, or a zip with companions
        break
    else:
        raise ValueError("no glb/gltf/fbx/obj download")
    name = safe(item["id"])
    if data[:2] == b"PK":
        folder = dest / name
        shutil.rmtree(folder, ignore_errors=True)  # drop files of an older download
        zipfile.ZipFile(io.BytesIO(data)).extractall(folder)
        found = [p for p in folder.rglob("*") if p.suffix.lower() in MODELS]
        if not found:
            raise ValueError("zip without a model")
        model = min(found, key=lambda p: (MODELS.index(p.suffix.lower()), len(p.parts)))
    else:
        ext = Path(urllib.parse.urlparse(final_url).path).suffix.lower()
        model = dest / (name + (ext if ext in MODELS else ".glb"))
        model.write_bytes(data)
    write_meta(model.with_suffix(".json"), name=name, title=item["title"], author=item["author"],
               license="CC0-1.0", url=item["page"], catalog=item["catalog"])
