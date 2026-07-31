# -*- coding: utf-8 -*-
"""待办列表悬浮面板。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QCheckBox,
)

import storage


class TodoPanel(QWidget):
    def __init__(self, on_close=None):
        super().__init__(None)
        self.on_close = on_close
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(300)
        self.setMinimumHeight(260)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("待办")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self._close)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        root.addLayout(header)

        self.list = QListWidget()
        root.addWidget(self.list)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("新待办…")
        self.input.returnPressed.connect(self._on_add)
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add)
        row.addWidget(self.input)
        row.addWidget(add_btn)
        root.addLayout(row)

        clear_btn = QPushButton("清空已完成")
        clear_btn.clicked.connect(self._on_clear)
        root.addWidget(clear_btn)

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
        for t in storage.list_todos():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, t["id"])
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(4, 2, 4, 2)
            cb = QCheckBox()
            cb.setChecked(bool(t.get("done")))
            todo_id = t["id"]
            cb.stateChanged.connect(
                lambda state, i=todo_id: self._toggle(i, state == Qt.Checked)
            )
            edit = QLineEdit(t.get("text") or "")
            if t.get("done"):
                edit.setStyleSheet("text-decoration: line-through; color: #888;")
            edit.editingFinished.connect(
                lambda e=edit, i=todo_id: self._edit(i, e.text())
            )
            del_btn = QPushButton("删")
            del_btn.setFixedWidth(36)
            del_btn.clicked.connect(lambda _=False, i=todo_id: self._delete(i))
            lay.addWidget(cb)
            lay.addWidget(edit, 1)
            lay.addWidget(del_btn)
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)

    def _toggle(self, todo_id, done):
        storage.update_todo(todo_id, done=done)
        self.reload()

    def _edit(self, todo_id, text):
        try:
            storage.update_todo(todo_id, text=text)
            self.hint.setText("")
        except ValueError:
            self.hint.setText("待办文案不能为空")
            self.reload()

    def _delete(self, todo_id):
        storage.delete_todo(todo_id)
        self.reload()

    def _on_add(self):
        try:
            storage.add_todo(self.input.text())
            self.input.clear()
            self.hint.setText("")
            self.reload()
        except ValueError:
            self.hint.setText("请输入待办内容")

    def _on_clear(self):
        storage.clear_completed_todos()
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
