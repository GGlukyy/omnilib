"""3d-asset-server (github.com/arielshad/3d-asset-server, Docker image ghcr.io/arielshad/3d-asset-server).

subscriptions.json: "asset_server": ["pine tree", ...]   (saved searches; each one becomes a pack/catalog)
Server URL: env OMNILIB_ASSET_SERVER (default http://localhost:8787). Only CC0 models are taken.
"""

import io
import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import UA, get_json, safe, warn, write_meta

URL = os.environ.get("OMNILIB_ASSET_SERVER", "http://localhost:8787").rstrip("/")
MODELS = [".glb", ".gltf", ".fbx", ".obj"]
PER_SEARCH = 24


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
                              "author": r.get("author") or r["id"].split(":")[0], "catalog": f"asset_server/{safe(q)}"})
    return items


def download(item, dest: Path):
    url = f"{URL}/v1/assets/{urllib.parse.quote(item['id'], safe=':')}/download?format=glb"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        data, final_url = r.read(), r.geturl()  # 302 to a single file, or a zip with companions
    name = safe(item["id"])
    if data[:2] == b"PK":
        folder = dest / name
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
