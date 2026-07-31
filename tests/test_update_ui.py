# -*- coding: utf-8 -*-
import os
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


class _FakePet(object):
    def __init__(self):
        self._update_snoozed = False
        self.messages = []
        self.releases = []

    def _show_bubble(self, text, duration_ms=2500):
        self.messages.append((text, duration_ms))

    def _show_update_prompt(self, release):
        self.releases.append(release)


if __name__ == "__main__":
    unittest.main()
