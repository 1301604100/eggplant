# -*- coding: utf-8 -*-
"""系统托盘封装。"""

from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon


class PetTray:
    """桌宠系统托盘。callbacks: show_pet, hide_pet, open_chat, quit"""

    def __init__(self, parent, icon_path, callbacks):
        self.parent = parent
        self.callbacks = callbacks or {}
        self.tray_icon = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(parent)
        icon = QIcon(icon_path)
        if not icon.isNull():
            self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("茄子桌宠")

        menu = QMenu()
        show_action = QAction("显示宠物", parent)
        show_action.triggered.connect(self._on_show)
        menu.addAction(show_action)

        hide_action = QAction("隐藏宠物", parent)
        hide_action.triggered.connect(self._on_hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        chat_action = QAction("聊聊天", parent)
        chat_action.triggered.connect(self._on_chat)
        menu.addAction(chat_action)

        menu.addSeparator()

        quit_action = QAction("退出", parent)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_activated)

    def show(self):
        if self.tray_icon:
            self.tray_icon.show()

    def hide(self):
        if self.tray_icon:
            self.tray_icon.hide()

    def available(self):
        return self.tray_icon is not None

    def _on_show(self):
        cb = self.callbacks.get("show_pet")
        if cb:
            cb()

    def _on_hide(self):
        cb = self.callbacks.get("hide_pet")
        if cb:
            cb()

    def _on_chat(self):
        cb = self.callbacks.get("open_chat")
        if cb:
            cb()

    def _on_quit(self):
        cb = self.callbacks.get("quit")
        if cb:
            cb()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._on_show()
