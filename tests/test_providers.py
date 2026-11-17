"""python -m unittest discover tests   (no Blender needed: providers.py has no bpy)"""

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extensions" / "omnilib_search"))
import providers  # noqa: E402

POLY = {"results": [{"ID": "abc", "Title": "Chair", "Creator": {"Username": "Kenney"}, "Licence": "CC0 1.0",
                     "Attribution": "", "Thumbnail": "https://static.poly.pizza/abc.webp",
                     "Download": "https://static.poly.pizza/abc.glb"}]}
SKETCH = {"results": [{"uid": "u1", "name": "Tree", "user": {"displayName": "Anna"}, "license": {"label": "CC Attribution"},
                       "viewerUrl": "https://sketchfab.com/3d-models/tree-u1",
                       "thumbnails": {"images": [{"url": "big", "width": 1024}, {"url": "mid", "width": 200}]}}]}
SERVER = {"results": [{"id": "polyhaven:rock", "title": "Rock", "license": {"name": "CC0"}, "url": "https://x/rock"},
                      {"id": "x:y", "title": "Paid-ish", "license": {"name": "CC-BY 4.0"}}]}


def fake_open(routes):
    calls = []

    def _open(url, headers=None, timeout=30):
        calls.append((url, headers))
        for prefix, body in routes.items():
            if url.startswith(prefix):
                return (body if isinstance(body, bytes) else json.dumps(body).encode()), url
        raise OSError("unrouted " + url)
    return _open, calls


class Providers(unittest.TestCase):
    def test_polypizza_search_maps_fields_and_filters_cc0_server_side(self):
        op, calls = fake_open({"https://api.poly.pizza": POLY})
        with mock.patch.object(providers, "_open", op):
            (it,) = providers.polypizza_search("chair", "KEY", True)
        self.assertEqual((it["author"], it["license"], it["url"]), ("Kenney", "CC0 1.0", "https://poly.pizza/m/abc"))
        self.assertIn("License=1", calls[0][0])
        self.assertEqual(calls[0][1], {"x-auth-token": "KEY"})
        self.assertNotIn("KEY", calls[0][0])  # never in the URL

    def test_sketchfab_picks_thumb_near_256_and_downloads_without_token(self):
        op, calls = fake_open({"https://api.sketchfab.com/v3/search": SKETCH})
        with mock.patch.object(providers, "_open", op):
            (it,) = providers.sketchfab_search("tree", "TOK", False)
        self.assertEqual((it["thumb"], it["license"]), ("mid", "CC Attribution"))
        self.assertEqual(calls[0][1], {"Authorization": "Token TOK"})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("scene.gltf", "{}")
            z.writestr("../evil.txt", "x")
        op, calls = fake_open({"https://api.sketchfab.com/v3/models/u1/download": {"gltf": {"url": "https://s3/z.zip"}},
                               "https://s3/z.zip": buf.getvalue()})
        with mock.patch.object(providers, "_open", op), tempfile.TemporaryDirectory() as d:
            path = providers.download(it, d, {"sketchfab": "TOK"})
            self.assertEqual(path.name, "scene.gltf")
            self.assertFalse((Path(d).parent / "evil.txt").exists())
        self.assertIsNone(calls[1][1])  # signed link: no Authorization header

    def test_asset_server_cc0_filter(self):
        op, _ = fake_open({"http://srv/v1/search": SERVER})
        with mock.patch.object(providers, "_open", op):
            self.assertEqual([i["id"] for i in providers.asset_server_search("rock", "http://srv", True)], ["polyhaven:rock"])
            self.assertEqual(len(providers.asset_server_search("rock", "http://srv", False)), 2)

    def test_search_skips_sources_without_key_and_reports_errors_without_secrets(self):
        def boom(url, headers=None, timeout=30):
            raise OSError("https://api.poly.pizza/?token=SECRET failed")
        with mock.patch.object(providers, "_open", boom), tempfile.TemporaryDirectory() as d:
            items, errors = providers.search("x", False, {"polypizza": "SECRET", "sketchfab": ""}, d)
        self.assertEqual((items, errors), ([], ["polypizza: OSError"]))


if __name__ == "__main__":
    unittest.main()
