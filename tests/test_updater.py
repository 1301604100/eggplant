# -*- coding: utf-8 -*-
import unittest

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


if __name__ == "__main__":
    unittest.main()
