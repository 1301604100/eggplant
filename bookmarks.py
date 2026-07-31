# -*- coding: utf-8 -*-
"""常用网址管理悬浮面板。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel,
)

import storage


class BookmarkPanel(QWidget):
    """别名 + URL 列表管理。"""

    def __init__(self, on_close=None):
        super().__init__(None)
        self.on_close = on_close
        self._selected_id = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("常用网址")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self._close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        root.addWidget(self.list)

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("别名")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("网址")
        form = QHBoxLayout()
        form.addWidget(self.alias_edit, 1)
        form.addWidget(self.url_edit, 2)
        root.addLayout(form)

        actions = QHBoxLayout()
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._on_delete)
        actions.addWidget(add_btn)
        actions.addWidget(save_btn)
        actions.addWidget(del_btn)
        root.addLayout(actions)

        self.hint = QLabel("")
        self.hint.setStyleSheet("color: #b91c1c; font-size: 11px;")
        root.addWidget(self.hint)

        self.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 235);
                border-radius: 14px;
                color: #333;
            }
            QLineEdit, QListWidget {
                background: rgba(255, 255, 255, 230);
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 4px 8px;
            }
            QPushButton {
                background: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover { background: #6d28d9; }
        """)
        self.reload()

    def reload(self):
        self.list.clear()
        self._selected_id = None
        for b in storage.list_bookmarks():
            item = QListWidgetItem("%s  —  %s" % (b["alias"], b["url"]))
            item.setData(Qt.UserRole, b["id"])
            self.list.addItem(item)
        self.alias_edit.clear()
        self.url_edit.clear()

    def _on_select(self, current, _previous):
        if current is None:
            self._selected_id = None
            return
        self._selected_id = current.data(Qt.UserRole)
        for b in storage.list_bookmarks():
            if b["id"] == self._selected_id:
                self.alias_edit.setText(b["alias"])
                self.url_edit.setText(b["url"])
                break

    def _on_add(self):
        try:
            storage.add_bookmark(self.alias_edit.text(), self.url_edit.text())
            self.alias_edit.clear()
            self.url_edit.clear()
            self.hint.setText("")
            self.reload()
        except ValueError:
            self.hint.setText("请填写别名和网址")

    def _on_save(self):
        if not self._selected_id:
            self.hint.setText("请先选中一项再保存")
            return
        try:
            storage.update_bookmark(
                self._selected_id, self.alias_edit.text(), self.url_edit.text()
            )
            self.hint.setText("")
            self.reload()
        except (ValueError, KeyError):
            self.hint.setText("保存失败，请检查别名和网址")

    def _on_delete(self):
        if not self._selected_id:
            self.hint.setText("请先选中一项再删除")
            return
        storage.delete_bookmark(self._selected_id)
        self.alias_edit.clear()
        self.url_edit.clear()
        self.hint.setText("")
        self.reload()

    def _close(self):
        self.hide()
        if self.on_close:
            self.on_close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close()
            return
        super().keyPressEvent(event)
