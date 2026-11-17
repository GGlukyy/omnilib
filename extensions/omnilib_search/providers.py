"""Search + download for the omnilib add-on. No bpy in here, so it can be tested outside Blender.

Keys come in as arguments and are only ever sent to their own service (never logged, never put into
URLs, never forwarded to a redirect target such as Sketchfab's signed download link).
Item = {"source", "id", "title", "author", "license", "url", "attribution"?, "thumb"?, "dl"?}
"""

import io
import json
import re
import socket
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = {"User-Agent": "omnilib-addon/0.1 (+https://github.com/GGlukyy/omnilib)"}
MODELS = (".glb", ".gltf", ".fbx", ".obj")  # preferred first
PER_SOURCE = 24
PAGE_SIZE = 12  # results per page in the panel
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


# --- filters, paging, cache (pure functions, unit-tested) --------------------------------------------

DEFAULT_FILTERS = {"sources": ("polypizza", "sketchfab", "asset_server"), "license": "all", "format": "any",
                   "animated": False, "rigged": False, "min_faces": 0, "max_faces": 0}
FORMATS = {"polypizza": {"glb"}, "sketchfab": {"glb"}}  # what we can fetch; asset_server offers glb/gltf/fbx/obj


def license_class(lic):
    """'cc0', 'ccby' (attribution only, no NC/ND/SA) or 'other'."""
    s = (lic or "").lower()
    if "cc0" in s or "public domain" in s or "zero" in s:
        return "cc0"
    if re.search(r"\bby\b|attribution", s) and not re.search(r"(^|[\s-])(nc|nd|sa)\b|noncommercial|noderiv|sharealike|share alike", s):
        return "ccby"
    return "other"


def license_ok(lic, want):
    """want: 'all' | 'cc0' | 'ccby' (CC-BY or more permissive)."""
    return want == "all" or license_class(lic) in (("cc0",) if want == "cc0" else ("cc0", "ccby"))


def source_ok(src, flt):
    """Is this source enabled, and can it deliver the wanted file format?"""
    fmt = flt.get("format", "any")
    return src in flt.get("sources", ()) and (fmt == "any" or fmt in FORMATS.get(src, {fmt}))


def page_count(n, size=PAGE_SIZE):
    return max(1, -(-n // size))


def page_slice(items, page, size=PAGE_SIZE):
    """(offset, items) of a page; the page is clamped into range."""
    page = min(max(page, 0), page_count(len(items), size) - 1)
    return page * size, items[page * size:(page + 1) * size]


def safe_name(s):
    return re.sub(r"[^\w.-]+", "_", s)


def item_key(item):
    return f"{item['source']}:{item['id']}"


def cache_folder(cache_dir, item):
    return Path(cache_dir) / safe_name(f"{item['source']}_{item['id']}")


def _pick_model(folder):
    found = [p for p in folder.rglob("*") if p.suffix.lower() in MODELS]
    return min(found, key=lambda p: (MODELS.index(p.suffix.lower()), len(p.parts))) if found else None


def trim_cache(cache_dir, max_mb):
    """Delete the least recently used model folders until the cache fits into max_mb. Returns the size in bytes."""
    root = Path(cache_dir)
    folders = [d for d in root.iterdir() if d.is_dir()] if root.is_dir() else []
    def size(d):
        return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
    sizes = {d: size(d) for d in folders}
    total = sum(sizes.values())
    for d in sorted(folders, key=lambda d: d.stat().st_mtime):
        if total <= max_mb * 1024 * 1024:
            break
        shutil.rmtree(d, ignore_errors=True)
        total -= sizes[d]
    return total


def clear_cache(cache_dir):
    shutil.rmtree(cache_dir, ignore_errors=True)


# --- Poly Pizza (official API v1.1, the user's own key) ---------------------------------------------

def polypizza_search(q, key, flt):
    params = {"Limit": PER_SOURCE, **({"License": 1} if flt["license"] == "cc0" else {})}
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

def sketchfab_search(q, token, flt):
    params = {"type": "models", "q": q, "downloadable": "true", "count": PER_SOURCE}
    if flt["license"] == "cc0":
        params["license"] = "cc0"
    for name in ("animated", "rigged"):  # sketchfab-only filters, sent as search parameters
        if flt[name]:
            params[name] = "true"
    for name, param in (("min_faces", "min_face_count"), ("max_faces", "max_face_count")):
        if flt[name]:
            params[param] = flt[name]
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

def asset_server_search(q, base, flt):
    query = urllib.parse.urlencode({"q": q, "type": "model", "free": "true", "downloadable": "true", "limit": PER_SOURCE})
    res = _json(f"{base.rstrip('/')}/v1/search?{query}")
    items = []
    for r in res.get("results", []):
        lic = (r.get("license") or {}).get("name") or ""
        items.append({"source": "asset_server", "id": r["id"], "title": r.get("title") or r["id"],
                      "author": r.get("author") or r["id"].split(":")[0], "license": lic or "unknown, see URL",
                      "url": r.get("url") or "", "thumb": r.get("thumbnail") or r.get("thumbnailUrl")})
    return items


def asset_server_download(item, dest, keys, fmt="any"):
    base = f"{keys['asset_server'].rstrip('/')}/v1/assets/{urllib.parse.quote(item['id'], safe=':')}"
    for f in ((fmt,) if fmt != "any" else ("glb", "gltf", "fbx", "obj")):  # sources offer different formats (Poly Haven: no glb)
        query = f"?resolution=1k&format={f}"
        if _json(f"{base}/files{query}").get("files"):
            data, url = _open(f"{base}/download{query}", timeout=300)
            return _place(data, url, dest, item["id"])
    raise ValueError("no download in the wanted format")


SOURCES = {  # name -> (search, download); the key (or URL) lives in keys[name]
    "polypizza": (polypizza_search, polypizza_download),
    "sketchfab": (sketchfab_search, sketchfab_download),
    "asset_server": (asset_server_search, asset_server_download),
}


HTTP_TEXT = {400: "bad request", 401: "invalid or missing key/token", 403: "access denied (check key, plan or licence)",
             404: "model not found or not downloadable", 429: "rate limit reached, try again later"}


def error_text(e):
    """Short human message from an exception. Never the exception text itself: it could echo a URL or key."""
    if isinstance(e, urllib.error.HTTPError):
        return HTTP_TEXT.get(e.code) or ("server error, try again later" if e.code >= 500 else f"HTTP {e.code}")
    if isinstance(e, (TimeoutError, socket.timeout)):
        return "timed out"
    if isinstance(e, urllib.error.URLError):
        return "cannot connect (offline or server down)"
    if isinstance(e, (zipfile.BadZipFile, ValueError, KeyError)):
        return "unexpected response or no usable model in the download"
    return type(e).__name__


def _err(src, e):
    return f"{src}: {error_text(e)}"


def search(q, flt, keys, thumb_dir):
    """Search every enabled source with a filled key. Returns (items, errors); items with a preview get "thumb_path"."""
    flt = {**DEFAULT_FILTERS, **flt}

    def one(src):
        try:
            items = [it for it in SOURCES[src][0](q, keys[src], flt) if license_ok(it["license"], flt["license"])]
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

    active = [s for s in SOURCES if keys.get(s) and source_ok(s, flt)]
    if not active:
        return [], ["no source enabled for these filters (a key is missing, or the format is not offered)"]
    with ThreadPoolExecutor(max(1, len(active))) as pool:
        results = list(pool.map(one, active))
    return [it for items, _ in results for it in items], [e for _, e in results if e]


def download(item, cache_dir, keys, fmt="any"):
    """Model path for item, from the cache when present. Returns (path, from_cache)."""
    folder = cache_folder(cache_dir, item)
    hit = _pick_model(folder) if folder.is_dir() else None
    if hit:
        folder.touch()  # most recently used
        return hit, True
    folder.mkdir(parents=True, exist_ok=True)
    try:
        fn = SOURCES[item["source"]][1]
        path = fn(item, folder, keys, fmt) if item["source"] == "asset_server" else fn(item, folder, keys)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)  # never leave a half-downloaded folder that looks like a hit
        raise
    return path, False
