# -*- coding: utf-8 -*-
"""常用网址管理悬浮面板（Element UI 风格）。"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QFrame,
)

import storage
from ui_theme import apply_card_shadow, panel_stylesheet, ui_font


class BookmarkPanel(QWidget):
    """别名 + URL 列表管理。"""

    def __init__(self, on_close=None):
        super().__init__(None)
        self.on_close = on_close
        self._selected_id = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(360)
        self.setStyleSheet(panel_stylesheet())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 12)
        outer.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("elCard")
        apply_card_shadow(card)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("常用网址")
        title.setObjectName("elTitle")
        title.setFont(ui_font(13, bold=True))
        close_btn = QPushButton("×")
        close_btn.setObjectName("elText")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(self._close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.setMinimumHeight(140)
        self.list.setFont(ui_font(11))
        self.list.currentItemChanged.connect(self._on_select)
        root.addWidget(self.list)

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("别名")
        self.alias_edit.setFont(ui_font(11))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com")
        self.url_edit.setFont(ui_font(11))
        form = QHBoxLayout()
        form.setSpacing(8)
        form.addWidget(self.alias_edit, 1)
        form.addWidget(self.url_edit, 2)
        root.addLayout(form)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        add_btn = QPushButton("添加")
        add_btn.setObjectName("elPrimary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFont(ui_font(11))
        add_btn.clicked.connect(self._on_add)
        save_btn = QPushButton("保存")
        save_btn.setObjectName("elDefault")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFont(ui_font(11))
        save_btn.clicked.connect(self._on_save)
        del_btn = QPushButton("删除")
        del_btn.setObjectName("elDanger")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFont(ui_font(11))
        del_btn.clicked.connect(self._on_delete)
        actions.addWidget(add_btn)
        actions.addWidget(save_btn)
        actions.addWidget(del_btn)
        actions.addStretch()
        root.addLayout(actions)

        self.hint = QLabel("")
        self.hint.setObjectName("elHint")
        self.hint.setFont(ui_font(10))
        root.addWidget(self.hint)

        self.reload()

    def reload(self):
        self.list.clear()
        self._selected_id = None
        for b in storage.list_bookmarks():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, b["id"])
            item.setText("%s\n%s" % (b["alias"], b["url"]))
            item.setToolTip(b["url"])
            # 第二行用稍淡的提示：Qt 列表不支持富文本行内，靠字号与提示区分
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
