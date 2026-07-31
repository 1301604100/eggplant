# -*- coding: utf-8 -*-
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import updater


SAMPLE_RELEASES = [
    {
        "tag_name": "v1.0.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "EggplantPet-Windows.exe",
                "browser_download_url": "https://example.com/old.exe",
                "size": 100,
            }
        ],
    },
    {
        "tag_name": "v1.2.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "茄子桌宠.exe",
                "browser_download_url": "https://example.com/new.exe",
                "size": 200,
            }
        ],
    },
    {
        "tag_name": "v2.0.0-beta",
        "draft": False,
        "prerelease": True,
        "assets": [
            {
                "name": "茄子桌宠.exe",
                "browser_download_url": "https://example.com/beta.exe",
                "size": 300,
            }
        ],
    },
    {
        "tag_name": "not-a-version",
        "draft": False,
        "prerelease": False,
        "assets": [],
    },
]


class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version(" 1.0.0\n"), (1, 0, 0))
        with self.assertRaises(ValueError):
            updater.parse_version("abc")
        with self.assertRaises(ValueError):
            updater.parse_version("1.2")

    def test_compare_versions(self):
        self.assertLess(updater.compare_versions((1, 0, 0), (1, 0, 1)), 0)
        self.assertEqual(updater.compare_versions((1, 2, 0), (1, 2, 0)), 0)
        self.assertGreater(updater.compare_versions((2, 0, 0), (1, 9, 9)), 0)

    def test_should_enable_updater(self):
        self.assertTrue(updater.should_enable_updater(platform="win32", frozen=True))
        self.assertFalse(updater.should_enable_updater(platform="win32", frozen=False))
        self.assertFalse(updater.should_enable_updater(platform="darwin", frozen=True))

    def test_read_local_version_fallback(self):
        self.assertEqual(updater.read_local_version(resource_reader=lambda: (_ for _ in ()).throw(OSError())), "0.0.0")
        self.assertEqual(updater.read_local_version(resource_reader=lambda: "1.3.0\n"), "1.3.0")

    def test_pick_latest_release(self):
        picked = updater.pick_latest_release(SAMPLE_RELEASES)
        self.assertIsNotNone(picked)
        self.assertEqual(picked["version"], "1.2.0")
        self.assertEqual(picked["tag"], "v1.2.0")
        self.assertEqual(picked["download_url"], "https://example.com/new.exe")
        self.assertEqual(picked["size"], 200)

    def test_pick_latest_prefers_chinese_asset_name(self):
        releases = [
            {
                "tag_name": "v1.0.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "EggplantPet-Windows.exe",
                        "browser_download_url": "https://example.com/en.exe",
                        "size": 1,
                    },
                    {
                        "name": "茄子桌宠.exe",
                        "browser_download_url": "https://example.com/zh.exe",
                        "size": 2,
                    },
                ],
            }
        ]
        picked = updater.pick_latest_release(releases)
        self.assertEqual(picked["download_url"], "https://example.com/zh.exe")

    def test_pick_latest_none_when_empty(self):
        self.assertIsNone(updater.pick_latest_release([]))
        self.assertIsNone(
            updater.pick_latest_release(
                [{"tag_name": "v1.0.0", "draft": True, "prerelease": False, "assets": []}]
            )
        )


class FakeResponse(object):
    def __init__(self, payload, headers=None):
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, bytes):
            data = payload
        else:
            data = str(payload).encode("utf-8")
        self._buf = io.BytesIO(data)
        self.headers = headers or {}

    def read(self, n=-1):
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestUpdaterNetwork(unittest.TestCase):
    def test_check_for_update_finds_newer(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(SAMPLE_RELEASES)

        result = updater.check_for_update(local_version="1.0.0", urlopen=fake_urlopen)
        self.assertEqual(result["version"], "1.2.0")

    def test_check_for_update_none_when_current(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(SAMPLE_RELEASES)

        self.assertIsNone(
            updater.check_for_update(local_version="1.2.0", urlopen=fake_urlopen)
        )

    def test_download_update_writes_file(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(b"MZ-fake-exe", headers={"Content-Length": "11"})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "app.exe"
        updater.download_update(
            "https://example.com/a.exe",
            str(dest),
            expected_size=11,
            urlopen=fake_urlopen,
        )
        self.assertEqual(dest.read_bytes(), b"MZ-fake-exe")

    def test_download_update_rejects_bad_size(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(b"short")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "app.exe"
        with self.assertRaises(ValueError):
            updater.download_update(
                "https://example.com/a.exe",
                str(dest),
                expected_size=100,
                urlopen=fake_urlopen,
            )
        self.assertFalse(dest.exists())

    def test_build_update_bat_content_contains_paths_and_pid(self):
        content = updater.build_update_bat_content(
            r"C:\Apps\茄子桌宠.exe",
            r"C:\Temp\new.exe",
            4242,
        )
        self.assertIn("4242", content)
        self.assertIn("茄子桌宠.exe", content)
        self.assertIn("new.exe", content)
        self.assertIn("start", content.lower())


if __name__ == "__main__":
    unittest.main()
