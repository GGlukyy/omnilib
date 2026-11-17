"""python -m unittest discover tests   (no Blender needed: providers.py has no bpy)"""

import io
import json
import sys
import socket
import tempfile
import unittest
import urllib.error
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


def FLT(**kw):
    return {**providers.DEFAULT_FILTERS, **kw}


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
            (it,) = providers.polypizza_search("chair", "KEY", FLT(license="cc0"))
        self.assertEqual((it["author"], it["license"], it["url"]), ("Kenney", "CC0 1.0", "https://poly.pizza/m/abc"))
        self.assertIn("License=1", calls[0][0])
        self.assertEqual(calls[0][1], {"x-auth-token": "KEY"})
        self.assertNotIn("KEY", calls[0][0])  # never in the URL

    def test_sketchfab_picks_thumb_near_256_and_downloads_without_token(self):
        op, calls = fake_open({"https://api.sketchfab.com/v3/search": SKETCH})
        with mock.patch.object(providers, "_open", op):
            (it,) = providers.sketchfab_search("tree", "TOK", FLT())
        self.assertEqual((it["thumb"], it["license"]), ("mid", "CC Attribution"))
        self.assertEqual(calls[0][1], {"Authorization": "Token TOK"})

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("scene.gltf", "{}")
            z.writestr("../evil.txt", "x")
        op, calls = fake_open({"https://api.sketchfab.com/v3/models/u1/download": {"gltf": {"url": "https://s3/z.zip"}},
                               "https://s3/z.zip": buf.getvalue()})
        with mock.patch.object(providers, "_open", op), tempfile.TemporaryDirectory() as d:
            path, cached = providers.download(it, d, {"sketchfab": "TOK"})
            self.assertEqual((path.name, cached), ("scene.gltf", False))
            self.assertFalse((Path(d).parent / "evil.txt").exists())
            _, cached = providers.download(it, d, {"sketchfab": "TOK"})  # second time: from the cache
            self.assertTrue(cached)
        self.assertIsNone(calls[1][1])  # signed link: no Authorization header

    def test_search_filters_licence_client_side(self):
        op, _ = fake_open({"http://srv/v1/search": SERVER})
        keys = {"asset_server": "http://srv"}
        with mock.patch.object(providers, "_open", op), tempfile.TemporaryDirectory() as d:
            self.assertEqual([i["id"] for i in providers.search("rock", FLT(license="cc0"), keys, d)[0]], ["polyhaven:rock"])
            self.assertEqual(len(providers.search("rock", FLT(license="ccby"), keys, d)[0]), 2)
            self.assertEqual(len(providers.search("rock", FLT(), keys, d)[0]), 2)

    def test_sketchfab_filters_are_sent_as_parameters(self):
        op, calls = fake_open({"https://api.sketchfab.com/v3/search": SKETCH})
        with mock.patch.object(providers, "_open", op):
            providers.sketchfab_search("tree", "TOK", FLT(animated=True, rigged=True, min_faces=100, max_faces=5000, license="cc0"))
        url = calls[0][0]
        for part in ("animated=true", "rigged=true", "min_face_count=100", "max_face_count=5000", "license=cc0"):
            self.assertIn(part, url)

    def test_disabled_source_and_format_skip_sources(self):
        op, calls = fake_open({"http://srv/v1/search": SERVER, "https://api.poly.pizza": POLY})
        keys = {"asset_server": "http://srv", "polypizza": "K"}
        with mock.patch.object(providers, "_open", op), tempfile.TemporaryDirectory() as d:
            providers.search("x", FLT(sources=("asset_server",)), keys, d)
            self.assertTrue(all(c[0].startswith("http://srv") for c in calls))
            calls.clear()
            providers.search("x", FLT(format="fbx"), keys, d)  # polypizza only has glb
            self.assertTrue(all(c[0].startswith("http://srv") for c in calls))
            self.assertEqual(providers.search("x", FLT(sources=()), keys, d)[0], [])

    def test_license_class(self):
        cls = providers.license_class
        self.assertEqual([cls(x) for x in ("CC0 1.0", "Public Domain", "CC-BY 3.0", "CC Attribution", "CC BY 4.0")],
                         ["cc0", "cc0", "ccby", "ccby", "ccby"])
        self.assertEqual([cls(x) for x in ("CC Attribution-NonCommercial", "CC-BY-SA 4.0", "CC BY-ND", "Standard", "")],
                         ["other"] * 5)

    def test_paging(self):
        items = list(range(25))
        self.assertEqual(providers.page_count(25, 12), 3)
        self.assertEqual(providers.page_count(0, 12), 1)
        self.assertEqual(providers.page_slice(items, 2, 12), (24, [24]))
        self.assertEqual(providers.page_slice(items, 99, 12)[0], 24)  # clamped
        self.assertEqual(providers.page_slice(items, -3, 12)[0], 0)

    def test_download_failure_leaves_no_cache_entry(self):
        item = {"source": "polypizza", "id": "abc", "dl": "https://static.poly.pizza/abc.glb"}
        def boom(url, headers=None, timeout=30):
            raise urllib.error.HTTPError(url, 429, "slow down", {}, None)
        with mock.patch.object(providers, "_open", boom), tempfile.TemporaryDirectory() as d:
            with self.assertRaises(urllib.error.HTTPError):
                providers.download(item, d, {"polypizza": "K"})
            self.assertFalse(providers.cache_folder(d, item).exists())

    def test_trim_cache_removes_least_recently_used(self):
        with tempfile.TemporaryDirectory() as d:
            for n, age in (("old", 100), ("new", 0)):
                f = Path(d) / n
                f.mkdir()
                (f / "m.glb").write_bytes(b"x" * 600_000)
                import os, time
                os.utime(f, (time.time() - age, time.time() - age))
            providers.trim_cache(d, 1)  # 1 MB < 1.2 MB total
            self.assertEqual([p.name for p in Path(d).iterdir()], ["new"])

    def test_error_text_is_readable_and_leaks_nothing(self):
        t = providers.error_text
        http = lambda c: urllib.error.HTTPError("https://x/?token=SECRET", c, "m", {}, None)
        self.assertIn("key", t(http(401)))
        self.assertIn("rate limit", t(http(429)))
        self.assertIn("server error", t(http(503)))
        self.assertEqual(t(socket.timeout()), "timed out")
        self.assertIn("cannot connect", t(urllib.error.URLError("https://x/?token=SECRET")))
        self.assertNotIn("SECRET", t(urllib.error.URLError("https://x/?token=SECRET")))

    def test_search_skips_sources_without_key_and_reports_errors_without_secrets(self):
        def boom(url, headers=None, timeout=30):
            raise OSError("https://api.poly.pizza/?token=SECRET failed")
        with mock.patch.object(providers, "_open", boom), tempfile.TemporaryDirectory() as d:
            items, errors = providers.search("x", FLT(), {"polypizza": "SECRET", "sketchfab": ""}, d)
        self.assertEqual((items, errors), ([], ["polypizza: OSError"]))


if __name__ == "__main__":
    unittest.main()
