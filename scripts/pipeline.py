"""Fetch new assets from every subscribed source, then build the library.

    python scripts/pipeline.py [--public] [--force] [--no-build]

subscriptions.json: {"<adapter>": <subscription>} -> sources/<adapter>.py (see sources/__init__.py).
packs/ is the download cache: packs/.state.json remembers what was fetched (id -> version),
so only new or changed items are downloaded. A failing source warns and is skipped.
"""

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sources import safe, warn  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--public", action="store_true", help="CC0 assets only (passed to build.py)")
ap.add_argument("--force", action="store_true", help="rebuild every .blend (passed to build.py)")
ap.add_argument("--no-build", action="store_true", help="only download")
args = ap.parse_args()

packs = ROOT / "packs"
state_file = packs / ".state.json"
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
subs = json.loads((ROOT / "subscriptions.json").read_text(encoding="utf-8"))

for name, sub in subs.items():
    try:
        adapter = importlib.import_module(f"sources.{name}")
        items = adapter.list(sub)
    except Exception as e:  # one broken source must not stop the others
        warn(f"{name}: skipped ({e})")
        continue
    new = [it for it in items if state.get(f"{name}:{it['id']}") != it.get("version", "")]
    print(f"{name}: {len(items)} subscribed, {len(new)} new", flush=True)
    for it in new:
        dest = packs / name / safe(it["pack"])
        try:
            dest.mkdir(parents=True, exist_ok=True)
            adapter.download(it, dest)
        except Exception as e:
            warn(f"{name}: {it['id']} failed ({e})")
            continue
        state[f"{name}:{it['id']}"] = it.get("version", "")
        state_file.write_text(json.dumps(state, indent=1), encoding="utf-8")  # survive a cancelled run

if not args.no_build:
    flags = [f for f, on in (("--public", args.public), ("--force", args.force)) if on]
    subprocess.run([sys.executable, str(ROOT / "scripts/build.py"), *flags], check=True)
