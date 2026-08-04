# -*- coding: utf-8 -*-
import os
import sys
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QWidget

import bubble
import main
from tray import PetTray


class TestUpdateUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_confirm_bubble_invokes_confirm_and_cancel_callbacks(self):
        events = []
        prompt = bubble.ConfirmBubble(
            "发现新版本",
            on_confirm=lambda: events.append("confirm"),
            on_cancel=lambda: events.append("cancel"),
        )

        prompt._emit_confirm()
        prompt._emit_cancel()

        self.assertEqual(events, ["confirm", "cancel"])

    def test_manual_current_version_reports_local_version(self):
        pet = _FakePet()

        with mock.patch.object(main.updater, "read_local_version", return_value="1.2.3"):
            main.EggplantPet._on_update_check_done(pet, None, None, manual=True)

        self.assertEqual(pet.messages, [("已是最新版本 1.2.3", 3000)])

    def test_snoozed_auto_check_does_not_show_prompt(self):
        pet = _FakePet()
        pet._update_snoozed = True

        main.EggplantPet._on_update_check_done(
            pet,
            {"version": "2.0.0"},
            None,
            manual=False,
        )

        self.assertEqual(pet.releases, [])

    def test_hiding_regular_bubble_keeps_update_prompt_open(self):
        pet = _BubbleOnlyPet()
        bubble = pet.bubble

        main.EggplantPet._hide_bubble(pet)

        self.assertTrue(pet.bubble_timer.stopped)
        self.assertTrue(bubble.closed)
        self.assertIsNone(pet.bubble)
        self.assertFalse(pet.update_prompt_hidden)

    def test_tray_shows_update_action_only_with_callback(self):
        parent = QWidget()
        called = []
        callbacks = {
            "check_for_updates": lambda: called.append(True),
            "quit": lambda: None,
        }

        with mock.patch.object(
            QSystemTrayIcon,
            "isSystemTrayAvailable",
            return_value=True,
        ):
            tray = PetTray(parent, "", callbacks)

        actions = tray.tray_icon.contextMenu().actions()
        update_actions = [action for action in actions if action.text() == "检查更新"]
        self.assertEqual(len(update_actions), 1)

        update_actions[0].trigger()
        self.assertEqual(called, [True])

    def test_tray_hides_update_action_without_callback(self):
        parent = QWidget()

        with mock.patch.object(
            QSystemTrayIcon,
            "isSystemTrayAvailable",
            return_value=True,
        ):
            tray = PetTray(parent, "", {"quit": lambda: None})

        action_texts = [
            action.text() for action in tray.tray_icon.contextMenu().actions()
        ]
        self.assertNotIn("检查更新", action_texts)

    def test_non_windows_prompt_opens_releases_page_on_confirm(self):
        pet = _FakePet()
        opened = []
        pet._open_releases_page = lambda source=None: opened.append(source or "releases")
        pet._hide_bubble = lambda: None
        pet._hide_update_prompt = lambda: None
        pet._snooze_update_prompt = lambda: None
        pet._present_floating = lambda prompt: None
        pet.x = lambda: 100
        pet.y = lambda: 100
        pet.width = lambda: 150
        pet.height = lambda: 150

        with mock.patch.object(
            main.updater,
            "should_enable_updater",
            return_value=False,
        ), mock.patch.object(
            main.updater,
            "read_local_version",
            return_value="1.0.0",
        ), mock.patch.object(
            main,
            "ConfirmBubble",
            side_effect=lambda *args, **kwargs: _CaptureConfirm(*args, **kwargs),
        ), mock.patch.object(
            main.QApplication,
            "primaryScreen",
            return_value=_FakeScreen(),
        ):
            main.EggplantPet._show_update_prompt(
                pet,
                {"version": "1.2.0", "body": "修复 mac 菜单"},
            )
            prompt = pet._update_prompt
            self.assertEqual(prompt.confirm_text, "打开下载页")
            self.assertIn("修复 mac 菜单", prompt.text)
            prompt.on_confirm()

        self.assertEqual(opened, ["releases"])

    def test_open_releases_page_uses_github_releases_url(self):
        pet = _FakePet()
        opened = []

        with mock.patch.object(
            main.webbrowser,
            "open",
            side_effect=lambda url: opened.append(url) or True,
        ):
            main.EggplantPet._open_releases_page(pet)

        self.assertEqual(
            opened,
            ["https://github.com/1301604100/eggplant/releases"],
        )

    def test_check_worker_completion_reaches_main_thread_handler(self):
        pet = _RecordingPet()
        self.addCleanup(pet.hide)

        with mock.patch.object(
            main.updater,
            "should_enable_updater",
            return_value=True,
        ), mock.patch.object(
            main.updater,
            "check_for_update",
            return_value=None,
        ):
            pet._check_for_updates(manual=False)
            completed = self._process_events_until(pet.completed.is_set)

        self.assertTrue(completed)
        self.assertIs(pet.handler_thread, threading.main_thread())
        self.assertFalse(pet._update_busy)

    def test_check_busy_prevents_overlapping_workers(self):
        pet = _RecordingPet()
        self.addCleanup(pet.hide)
        started = threading.Event()
        release = threading.Event()
        call_count = [0]
        lock = threading.Lock()

        def blocking_check():
            with lock:
                call_count[0] += 1
                started.set()
            release.wait(1)
            return None

        try:
            with mock.patch.object(
                main.updater,
                "should_enable_updater",
                return_value=True,
            ), mock.patch.object(
                main.updater,
                "check_for_update",
                side_effect=blocking_check,
            ):
                pet._check_for_updates(manual=False)
                self.assertTrue(started.wait(1))
                pet._check_for_updates(manual=True)
                time.sleep(0.05)

            self.assertEqual(call_count[0], 1)
        finally:
            release.set()

    def test_download_worker_completion_reaches_main_thread_handler(self):
        pet = _RecordingPet()
        self.addCleanup(pet.hide)
        release = {
            "version": "2.0.0",
            "download_url": "https://example.com/update.exe",
            "size": 123,
        }

        with mock.patch.object(
            main.updater,
            "download_update",
        ), mock.patch.object(
            main.updater,
            "write_update_script",
        ), mock.patch.object(
            main.updater,
            "launch_update_and_exit",
        ):
            pet._start_download_update(release)
            completed = self._process_events_until(
                pet.download_completed.is_set,
            )

        self.assertTrue(completed)
        self.assertIs(
            pet.download_handler_thread,
            threading.main_thread(),
        )
        self.assertIsNone(pet.download_result[0])
        script_name = "update.sh" if sys.platform == "darwin" else "update.bat"
        self.assertTrue(pet.download_result[1].endswith(script_name))
        self.assertFalse(pet._update_busy)

    def test_confirm_starts_download_after_repeated_check_attempt(self):
        pet = _RecordingPet()
        self.addCleanup(pet.hide)
        release = {
            "version": "2.0.0",
            "download_url": "https://example.com/update.exe",
            "size": 123,
        }
        unblock_check = threading.Event()

        def blocking_check():
            unblock_check.wait(1)
            return release

        try:
            with mock.patch.object(
                main.updater,
                "should_enable_updater",
                return_value=True,
            ), mock.patch.object(
                main.updater,
                "read_local_version",
                return_value="1.0.0",
            ), mock.patch.object(
                main.updater,
                "check_for_update",
                side_effect=blocking_check,
            ), mock.patch.object(
                main.updater,
                "download_update",
            ), mock.patch.object(
                main.updater,
                "write_update_script",
            ), mock.patch.object(
                main.updater,
                "launch_update_and_exit",
            ), mock.patch.object(
                main,
                "apply_native_topmost",
            ):
                pet._on_update_check_done(release, None, manual=True)
                prompt = pet._update_prompt
                pet._check_for_updates(manual=True)
                prompt._emit_confirm()
                completed = self._process_events_until(
                    pet.download_completed.is_set,
                    timeout=0.5,
                )

            self.assertTrue(completed)
            self.assertFalse(pet._update_busy)
        finally:
            unblock_check.set()

    def _process_events_until(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return True
            time.sleep(0.01)
        self.app.processEvents()
        return predicate()


class _FakePet(object):
    def __init__(self):
        self._update_snoozed = False
        self._update_busy = False
        self._update_prompt = None
        self.messages = []
        self.releases = []

    def _show_bubble(self, text, duration_ms=2500):
        self.messages.append((text, duration_ms))

    def _show_update_prompt(self, release):
        self.releases.append(release)


class _CaptureConfirm(object):
    def __init__(self, text, confirm_text="更新", cancel_text="稍后",
                 on_confirm=None, on_cancel=None, parent=None):
        self.text = text
        self.confirm_text = confirm_text
        self.cancel_text = cancel_text
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def adjustSize(self):
        return None

    def width(self):
        return 280

    def height(self):
        return 160

    def move(self, x, y):
        return None


class _FakeScreen(object):
    def availableGeometry(self):
        from PyQt5.QtCore import QRect
        return QRect(0, 0, 1920, 1080)


class _BubbleOnlyPet(object):
    def __init__(self):
        self.bubble_timer = _FakeTimer()
        self.bubble = _FakeBubble()
        self.update_prompt_hidden = False

    def _hide_update_prompt(self):
        self.update_prompt_hidden = True


class _FakeTimer(object):
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeBubble(object):
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _RecordingPet(main.EggplantPet):
    def __init__(self):
        self.completed = threading.Event()
        self.handler_thread = None
        self.download_completed = threading.Event()
        self.download_handler_thread = None
        self.download_result = None
        super().__init__()

    def _on_update_check_done(self, result, err, manual=False):
        self.handler_thread = threading.current_thread()
        super()._on_update_check_done(result, err, manual=manual)
        self.completed.set()

    def _on_download_done(self, err, script_path):
        self.download_handler_thread = threading.current_thread()
        self.download_result = (err, script_path)
        super()._on_download_done(err, script_path)
        self.download_completed.set()

    def _show_bubble(self, text, duration_ms=2500):
        pass

    def _refresh_native_topmost(self):
        pass


if __name__ == "__main__":
    unittest.main()
