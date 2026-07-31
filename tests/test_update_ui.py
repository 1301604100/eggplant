# -*- coding: utf-8 -*-
import os
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
        self.assertTrue(pet.download_result[1].endswith("update.bat"))
        self.assertFalse(pet._update_busy)

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
        self.messages = []
        self.releases = []

    def _show_bubble(self, text, duration_ms=2500):
        self.messages.append((text, duration_ms))

    def _show_update_prompt(self, release):
        self.releases.append(release)


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
