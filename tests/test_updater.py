# -*- coding: utf-8 -*-
import io
import json
import os
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
        "body": "- 修复任务栏多条目\n- 优化更新提示",
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
        self.assertTrue(updater.should_enable_updater(platform="darwin", frozen=True))
        self.assertFalse(updater.should_enable_updater(platform="darwin", frozen=False))
        self.assertFalse(updater.should_enable_updater(platform="linux", frozen=True))

    def test_releases_page_url(self):
        self.assertEqual(
            updater.releases_page_url(),
            "https://github.com/1301604100/eggplant/releases",
        )
        self.assertEqual(
            updater.releases_page_url("gitee"),
            "https://gitee.com/kary2/eggplant-releases/releases",
        )

    def test_read_local_version_fallback(self):
        self.assertEqual(updater.read_local_version(resource_reader=lambda: (_ for _ in ()).throw(OSError())), "0.0.0")
        self.assertEqual(updater.read_local_version(resource_reader=lambda: "1.3.0\n"), "1.3.0")

    def test_read_local_version_uses_bundled_version_by_default(self):
        version = updater.read_local_version()

        self.assertNotEqual(version, "0.0.0")
        self.assertEqual(len(updater.parse_version(version)), 3)

    def test_pick_latest_release(self):
        picked = updater.pick_latest_release(SAMPLE_RELEASES, platform="win32")
        self.assertIsNotNone(picked)
        self.assertEqual(picked["version"], "1.2.0")
        self.assertEqual(picked["tag"], "v1.2.0")
        self.assertEqual(picked["download_url"], "https://example.com/new.exe")
        self.assertEqual(picked["size"], 200)
        self.assertIn("修复任务栏多条目", picked["body"])
        self.assertEqual(picked.get("source"), "github")

    def test_pick_latest_accepts_gitee_attach_files(self):
        releases = [
            {
                "tag_name": "v1.3.0",
                "draft": False,
                "prerelease": False,
                "body": "gitee build",
                "attach_files": [
                    {
                        "name": "茄子桌宠.exe",
                        "download_url": "https://gitee.com/file.exe",
                        "size": 9,
                    }
                ],
            }
        ]
        picked = updater.pick_latest_release(
            releases, source="gitee", platform="win32"
        )
        self.assertEqual(picked["version"], "1.3.0")
        self.assertEqual(picked["download_url"], "https://gitee.com/file.exe")
        self.assertEqual(picked["source"], "gitee")

    def test_pick_latest_darwin_selects_macos_zip(self):
        releases = [
            {
                "tag_name": "v1.5.0",
                "draft": False,
                "prerelease": False,
                "body": "mac",
                "assets": [
                    {
                        "name": "EggplantPet-Windows.exe",
                        "browser_download_url": "https://example.com/win.exe",
                        "size": 1,
                    },
                    {
                        "name": "EggplantPet-macOS.zip",
                        "browser_download_url": "https://example.com/mac.zip",
                        "size": 2,
                    },
                ],
            }
        ]
        picked = updater.pick_latest_release(releases, platform="darwin")
        self.assertEqual(picked["download_url"], "https://example.com/mac.zip")
        self.assertIsNone(
            updater.pick_latest_release(
                [
                    {
                        "tag_name": "v1.5.0",
                        "draft": False,
                        "prerelease": False,
                        "assets": [
                            {
                                "name": "EggplantPet-Windows.exe",
                                "browser_download_url": "https://example.com/win.exe",
                                "size": 1,
                            }
                        ],
                    }
                ],
                platform="darwin",
            )
        )

    def test_fetch_latest_release_falls_back_to_gitee(self):
        gitee_payload = [
            {
                "tag_name": "v1.4.0",
                "draft": False,
                "prerelease": False,
                "body": "from gitee",
                "assets": [
                    {
                        "name": "EggplantPet-Windows.exe",
                        "browser_download_url": "https://gitee.example/a.exe",
                        "size": 3,
                    }
                ],
            }
        ]

        def fake_urlopen(req, timeout=None):
            url = getattr(req, "full_url", None) or req.get_full_url()
            if "api.github.com" in url:
                raise updater.urllib.error.URLError("github blocked")
            return FakeResponse(gitee_payload)

        picked = updater.fetch_latest_release(
            urlopen=fake_urlopen, platform="win32"
        )
        self.assertEqual(picked["version"], "1.4.0")
        self.assertEqual(picked["source"], "gitee")

    def test_format_release_notes_empty_and_truncate(self):
        self.assertEqual(updater.format_release_notes(""), "暂无更新说明")
        self.assertEqual(updater.format_release_notes(None), "暂无更新说明")
        long_body = "a" * 400
        notes = updater.format_release_notes(long_body, max_chars=20)
        self.assertEqual(len(notes), 20)
        self.assertTrue(notes.endswith("…"))

    def test_format_update_prompt_text_includes_notes(self):
        text = updater.format_update_prompt_text(
            "1.0.0",
            {"version": "1.2.0", "body": "修复拖动闪烁"},
        )
        self.assertIn("1.2.0", text)
        self.assertIn("1.0.0", text)
        self.assertIn("修复拖动闪烁", text)

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
        picked = updater.pick_latest_release(releases, platform="win32")
        self.assertEqual(picked["download_url"], "https://example.com/zh.exe")

    def test_pick_latest_none_when_empty(self):
        self.assertIsNone(updater.pick_latest_release([], platform="win32"))
        self.assertIsNone(
            updater.pick_latest_release(
                [{"tag_name": "v1.0.0", "draft": True, "prerelease": False, "assets": []}],
                platform="win32",
            )
        )

    def test_resolve_app_bundle_from_executable(self):
        path = os.path.join(
            os.sep,
            "Users",
            "me",
            "Apps",
            "茄子桌宠.app",
            "Contents",
            "MacOS",
            "茄子桌宠",
        )
        resolved = updater.resolve_app_bundle(path)
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.endswith("茄子桌宠.app"))
        self.assertIsNone(
            updater.resolve_app_bundle(os.path.join(os.sep, "usr", "local", "bin", "foo"))
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

        result = updater.check_for_update(
            local_version="1.0.0", urlopen=fake_urlopen, platform="win32"
        )
        self.assertEqual(result["version"], "1.2.0")

    def test_check_for_update_none_when_current(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(SAMPLE_RELEASES)

        self.assertIsNone(
            updater.check_for_update(
                local_version="1.2.0", urlopen=fake_urlopen, platform="win32"
            )
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

    def test_build_update_bat_retries_copy_and_logs_failure(self):
        content = updater.build_update_bat_content(
            r"C:\Apps\茄子桌宠.exe",
            r"C:\Temp\new.exe",
            4242,
        )

        self.assertIn('set "NEW=C:\\Temp\\new.exe"', content)
        self.assertIn('set "CUR=C:\\Apps\\茄子桌宠.exe"', content)
        self.assertIn("ping -n 2 127.0.0.1 >nul", content)
        self.assertIn("set RETRIES=15", content)
        self.assertIn(":copy_retry", content)
        self.assertIn("update-failed.log", content)
        self.assertNotIn("pause", content.lower())
        self.assertNotIn("timeout ", content.lower())

    def test_write_update_script_uses_oem_encoding_for_chinese_windows_paths(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        script_path = str(Path(tmp.name) / "update.bat")

        with mock.patch.object(updater.sys, "platform", "win32"), mock.patch(
            "builtins.open",
            mock.mock_open(),
        ) as mocked_open:
            updater.write_update_script(
                r"C:\应用\茄子桌宠.exe",
                r"C:\临时\新版.exe",
                4242,
                script_path,
            )

        mocked_open.assert_called_once_with(script_path, "w", encoding="oem")
        written = mocked_open().write.call_args.args[0]
        self.assertIn("茄子桌宠.exe", written)
        self.assertIn("新版.exe", written)

    def test_launch_update_uses_named_no_window_flag_on_windows(self):
        with mock.patch.object(updater.sys, "platform", "win32"), mock.patch.object(
            updater.subprocess,
            "Popen",
        ) as popen:
            updater.launch_update_and_exit(r"C:\Temp\update.bat", None)

        popen.assert_called_once_with(
            ["cmd.exe", "/c", r"C:\Temp\update.bat"],
            creationflags=updater.CREATE_NO_WINDOW,
            close_fds=True,
        )

    def test_build_update_sh_content_replaces_app(self):
        content = updater.build_update_sh_content(
            "/Apps/茄子桌宠.app",
            "/tmp/EggplantPet-macOS.zip",
            4242,
        )
        self.assertIn("4242", content)
        self.assertIn("茄子桌宠.app", content)
        self.assertIn("EggplantPet-macOS.zip", content)
        self.assertIn("unzip", content)
        self.assertIn("xattr", content)
        self.assertIn("com.apple.quarantine", content)
        self.assertIn("open ", content)

    def test_write_update_script_darwin_writes_shell(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        script_path = str(Path(tmp.name) / "update.sh")
        exe = str(Path(tmp.name) / "茄子桌宠.app" / "Contents" / "MacOS" / "茄子桌宠")
        Path(exe).parent.mkdir(parents=True)
        Path(exe).write_text("x", encoding="utf-8")

        with mock.patch.object(updater.sys, "platform", "darwin"):
            updater.write_update_script(
                exe,
                str(Path(tmp.name) / "EggplantPet-macOS.zip"),
                99,
                script_path,
            )

        text = Path(script_path).read_text(encoding="utf-8")
        self.assertIn("#!/bin/bash", text)
        self.assertIn("unzip", text)
        self.assertTrue(os.access(script_path, os.X_OK))

    def test_launch_update_uses_bash_on_darwin(self):
        with mock.patch.object(updater.sys, "platform", "darwin"), mock.patch.object(
            updater.subprocess,
            "Popen",
        ) as popen:
            updater.launch_update_and_exit("/tmp/update.sh", None)

        popen.assert_called_once_with(["/bin/bash", "/tmp/update.sh"], close_fds=True)


if __name__ == "__main__":
    unittest.main()
