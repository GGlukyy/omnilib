"""Source adapters. Each module `sources/<name>.py` has:

    list(sub) -> [item]            item = {"id", "pack", "version"?, ...adapter data}
    download(item, dest: Path)     put the model(s) for `item` into `dest` (= packs/<name>/<pack>/)

`sub` is the module's entry from subscriptions.json. An adapter that cannot run
(missing key, server down) warns and returns []: the pipeline must stay green.

Metadata for scripts/mark_assets.py goes next to the model as `<model stem>.json`
(title, author, license, attribution, url, catalog) or as `pack.json` for a whole pack.
"""

import json
import os
import re
import urllib.request

UA = {"User-Agent": "omnilib/0.1 (+https://github.com/GGlukyy/omnilib)"}


def warn(msg: str) -> None:
    # GitHub Actions shows ::warning:: lines as annotations on the run
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"WARNING: {msg}", flush=True)


def fetch(url: str, headers: dict | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url: str, headers: dict | None = None):
    return json.loads(fetch(url, headers))


def safe(name: str) -> str:
    """File/dir name that is also a valid asset-catalog path segment."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name).strip(" .-") or "unnamed"


def write_meta(path, **meta) -> None:
    path.write_text(json.dumps({k: v for k, v in meta.items() if v}, indent=1), encoding="utf-8")
