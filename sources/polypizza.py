"""Poly Pizza, official API v1.1 (https://poly.pizza/docs/api/v1.1). Key: env POLY_PIZZA_KEY.

subscriptions.json: "polypizza": {"users": ["Kenney", "Quaternius"], "search": ["chair"]}
A user's lists become packs (catalog polypizza/<user>/<list>); models outside lists go to <user>/misc.
Search results go to polypizza/search/<term>. Licence, author and attribution are kept per model
(CC-BY models stay local: build.py --public drops them).
Without POLY_PIZZA_KEY the source is skipped with a warning.
"""

import os
import urllib.parse
from pathlib import Path

from . import fetch, get_json, safe, warn, write_meta

API = "https://api.poly.pizza/v1.1"
PAGE = 32  # API maximum


def _get(path, key, **params):
    return get_json(f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}", {"x-auth-token": key})


def _pages(path, key, field):
    page = 0
    while True:
        res = _get(path, key, Limit=PAGE, Page=page)
        models = res.get(field) or []
        yield res, models
        if len(models) < PAGE:
            return
        page += 1


def _item(m, catalog):
    creator = (m.get("Creator") or {}).get("Username", "")
    return {"id": m["ID"], "pack": catalog.split("/", 1)[1].replace("/", " - "), "catalog": catalog,
            "title": m.get("Title"), "author": creator, "license": m.get("Licence", ""),
            "attribution": m.get("Attribution"), "download": m.get("Download"),
            "url": f"https://poly.pizza/m/{m['ID']}", "version": m.get("Uploaded", "")}


def list(sub):
    key = os.environ.get("POLY_PIZZA_KEY")
    if not key:
        warn("polypizza: POLY_PIZZA_KEY not set, skipped")
        return []
    items = {}
    for user in sub.get("users", []):
        models, list_ids = [], []
        for res, page in _pages(f"/user/{urllib.parse.quote(user)}", key, "models"):
            models += page
            list_ids = list_ids or res.get("lists") or []
        in_list = {}
        for lid in list_ids:
            lst = _get(f"/list/{lid}", key)
            for m in lst.get("Models") or []:
                in_list.setdefault(m["ID"], safe(lst.get("Name") or lid))
        for m in models:
            items[m["ID"]] = _item(m, f"polypizza/{safe(user)}/{in_list.get(m['ID'], 'misc')}")
    for term in sub.get("search", []):
        for _, page in _pages(f"/search/{urllib.parse.quote(term)}", key, "results"):
            for m in page:
                items.setdefault(m["ID"], _item(m, f"polypizza/search/{safe(term)}"))
    return [*items.values()]


def download(item, dest: Path):
    key = os.environ["POLY_PIZZA_KEY"]
    (dest / f"{item['id']}.glb").write_bytes(fetch(item["download"], {"x-auth-token": key}, timeout=300))
    write_meta(dest / f"{item['id']}.json", **{k: item[k] for k in
               ("title", "author", "license", "attribution", "url", "catalog")})
