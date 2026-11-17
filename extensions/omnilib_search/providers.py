"""Search + download for the omnilib add-on. No bpy in here, so it can be tested outside Blender.

Keys come in as arguments and are only ever sent to their own service (never logged, never put into
URLs, never forwarded to a redirect target such as Sketchfab's signed download link).
Item = {"source", "id", "title", "author", "license", "url", "attribution"?, "thumb"?, "dl"?}
"""

import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = {"User-Agent": "omnilib-addon/0.1 (+https://github.com/GGlukyy/omnilib)"}
MODELS = (".glb", ".gltf", ".fbx", ".obj")  # preferred first
PER_SOURCE = 12
POLY_API = "https://api.poly.pizza/v1.1"
SKETCHFAB_API = "https://api.sketchfab.com/v3"


def _open(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def _json(url, headers=None):
    return json.loads(_open(url, headers)[0])


def _place(data, final_url, dest: Path, name):
    """Write a download (single model file or zip) into dest, return the model path."""
    name = re.sub(r"[^\w.-]+", "_", name)
    if data[:2] == b"PK":
        folder = dest / name
        zipfile.ZipFile(io.BytesIO(data)).extractall(folder)  # zipfile strips ../ and absolute paths
        found = [p for p in folder.rglob("*") if p.suffix.lower() in MODELS]
        if not found:
            raise ValueError("no model in the download")
        return min(found, key=lambda p: (MODELS.index(p.suffix.lower()), len(p.parts)))
    ext = Path(urllib.parse.urlparse(final_url).path).suffix.lower()
    path = dest / (name + (ext if ext in MODELS else ".glb"))
    path.write_bytes(data)
    return path


# --- Poly Pizza (official API v1.1, the user's own key) ---------------------------------------------

def polypizza_search(q, key, cc0):
    params = {"Limit": PER_SOURCE, **({"License": 1} if cc0 else {})}
    res = _json(f"{POLY_API}/search/{urllib.parse.quote(q)}?{urllib.parse.urlencode(params)}", {"x-auth-token": key})
    return [{"source": "polypizza", "id": m["ID"], "title": m.get("Title") or m["ID"],
             "author": (m.get("Creator") or {}).get("Username", ""), "license": m.get("Licence", ""),
             "url": f"https://poly.pizza/m/{m['ID']}", "attribution": m.get("Attribution"),
             "thumb": m.get("Thumbnail"), "dl": m.get("Download")}
            for m in res.get("results") or []]


def polypizza_download(item, dest, keys):
    data, url = _open(item["dl"], {"x-auth-token": keys["polypizza"]}, timeout=300)
    return _place(data, url, dest, item["id"])


# --- Sketchfab (API token; download = signed link, fetched WITHOUT the token) -----------------------

def sketchfab_search(q, token, cc0):
    params = {"type": "models", "q": q, "downloadable": "true", "count": PER_SOURCE, **({"license": "cc0"} if cc0 else {})}
    res = _json(f"{SKETCHFAB_API}/search?{urllib.parse.urlencode(params)}", {"Authorization": f"Token {token}"})
    items = []
    for m in res.get("results") or []:
        images = (m.get("thumbnails") or {}).get("images") or []
        thumb = min(images, key=lambda i: abs(i.get("width", 0) - 256))["url"] if images else None
        items.append({"source": "sketchfab", "id": m["uid"], "title": m.get("name") or m["uid"],
                      "author": (m.get("user") or {}).get("displayName", ""),
                      "license": (m.get("license") or {}).get("label") or "unknown, see URL",
                      "url": m.get("viewerUrl") or f"https://sketchfab.com/3d-models/{m['uid']}", "thumb": thumb})
    return items


def sketchfab_download(item, dest, keys):
    info = _json(f"{SKETCHFAB_API}/models/{item['id']}/download", {"Authorization": f"Token {keys['sketchfab']}"})
    data, url = _open(info["gltf"]["url"], timeout=300)  # signed S3 link: no token
    return _place(data, url, dest, item["id"])


# --- 3d-asset-server (github.com/arielshad/3d-asset-server, URL from preferences, no key) ----------

def asset_server_search(q, base, cc0):
    query = urllib.parse.urlencode({"q": q, "type": "model", "free": "true", "downloadable": "true", "limit": PER_SOURCE})
    res = _json(f"{base.rstrip('/')}/v1/search?{query}")
    items = []
    for r in res.get("results", []):
        lic = (r.get("license") or {}).get("name") or ""
        if cc0 and "CC0" not in lic.upper():
            continue
        items.append({"source": "asset_server", "id": r["id"], "title": r.get("title") or r["id"],
                      "author": r.get("author") or r["id"].split(":")[0], "license": lic or "unknown, see URL",
                      "url": r.get("url") or "", "thumb": r.get("thumbnail") or r.get("thumbnailUrl")})
    return items


def asset_server_download(item, dest, keys):
    base = f"{keys['asset_server'].rstrip('/')}/v1/assets/{urllib.parse.quote(item['id'], safe=':')}"
    for fmt in ("glb", "gltf", "fbx", "obj"):  # sources offer different formats (Poly Haven: no glb)
        query = f"?resolution=1k&format={fmt}"
        if _json(f"{base}/files{query}").get("files"):
            data, url = _open(f"{base}/download{query}", timeout=300)
            return _place(data, url, dest, item["id"])
    raise ValueError("no glb/gltf/fbx/obj download")


SOURCES = {  # name -> (search, download); the key (or URL) lives in keys[name]
    "polypizza": (polypizza_search, polypizza_download),
    "sketchfab": (sketchfab_search, sketchfab_download),
    "asset_server": (asset_server_search, asset_server_download),
}


def _err(src, e):
    # only the type / HTTP status: an exception text could echo a URL, never a key
    return f"{src}: HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else f"{src}: {type(e).__name__}"


def search(q, cc0, keys, thumb_dir):
    """Search every source with a filled key. Returns (items, errors); items with a preview get "thumb_path"."""
    def one(src):
        try:
            items = SOURCES[src][0](q, keys[src], cc0)
        except Exception as e:
            return [], _err(src, e)
        for i, it in enumerate(items):
            if it.get("thumb"):
                try:
                    headers = {"x-auth-token": keys[src]} if src == "polypizza" else None  # static.poly.pizza wants it
                    path = Path(thumb_dir) / f"{src}_{i}.img"
                    path.write_bytes(_open(it["thumb"], headers)[0])
                    it["thumb_path"] = str(path)
                except Exception:
                    pass  # no preview, still usable
        return items, None

    active = [s for s in SOURCES if keys.get(s)]
    with ThreadPoolExecutor(max(1, len(active))) as pool:
        results = list(pool.map(one, active))
    return [it for items, _ in results for it in items], [e for _, e in results if e]


def download(item, dest, keys):
    return SOURCES[item["source"]][1](item, Path(dest), keys)
