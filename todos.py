# -*- coding: utf-8 -*-
"""待办列表悬浮面板（Element UI 风格）。"""

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QCheckBox, QFrame,
)

import storage
from ui_theme import (
    apply_card_shadow,
    panel_stylesheet,
    ui_font,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT,
)


class TodoPanel(QWidget):
    def __init__(self, on_close=None):
        super().__init__(None)
        self.on_close = on_close
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(340)
        self.setMinimumHeight(300)
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
        title = QLabel("待办")
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
        self.list.setObjectName("elTodoList")
        self.list.setMinimumHeight(160)
        # setItemWidget 时 item 的 padding 会裁切行内控件，改由 row 自己留白
        self.list.setStyleSheet("""
            QListWidget#elTodoList::item {
                padding: 0px;
                margin: 2px 0;
                border-radius: 4px;
            }
        """)
        root.addWidget(self.list)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入待办内容，回车添加")
        self.input.setFont(ui_font(11))
        self.input.returnPressed.connect(self._on_add)
        add_btn = QPushButton("添加")
        add_btn.setObjectName("elPrimary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFont(ui_font(11))
        add_btn.clicked.connect(self._on_add)
        row.addWidget(self.input, 1)
        row.addWidget(add_btn)
        root.addLayout(row)

        footer = QHBoxLayout()
        clear_btn = QPushButton("清空已完成")
        clear_btn.setObjectName("elDefault")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setFont(ui_font(11))
        clear_btn.clicked.connect(self._on_clear)
        footer.addWidget(clear_btn)
        footer.addStretch()
        root.addLayout(footer)

        self.hint = QLabel("")
        self.hint.setObjectName("elHint")
        self.hint.setFont(ui_font(10))
        root.addWidget(self.hint)

        self.reload()

    def reload(self):
        self.list.clear()
        for t in storage.list_todos():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, t["id"])
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(8)

            cb = QCheckBox()
            cb.setChecked(bool(t.get("done")))
            todo_id = t["id"]
            cb.stateChanged.connect(
                lambda state, i=todo_id: self._toggle(i, state == Qt.Checked)
            )

            edit = QLineEdit(t.get("text") or "")
            edit.setFont(ui_font(11))
            edit.setMinimumHeight(28)
            if t.get("done"):
                edit.setStyleSheet(
                    "text-decoration: line-through; color: %s; border: none; "
                    "background: transparent; padding: 2px 4px;"
                    % COLOR_TEXT_SECONDARY
                )
            else:
                edit.setStyleSheet(
                    "color: %s; border: none; background: transparent; "
                    "padding: 2px 4px;"
                    % COLOR_TEXT
                )
            edit.editingFinished.connect(
                lambda e=edit, i=todo_id: self._edit(i, e.text())
            )

            del_btn = QPushButton("删除")
            del_btn.setObjectName("elTextDanger")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFont(ui_font(10))
            del_btn.setFixedHeight(28)
            del_btn.clicked.connect(lambda _=False, i=todo_id: self._delete(i))

            lay.addWidget(cb, 0, Qt.AlignVCenter)
            lay.addWidget(edit, 1)
            lay.addWidget(del_btn, 0, Qt.AlignVCenter)
            row.adjustSize()
            hint = row.sizeHint()
            item.setSizeHint(QSize(hint.width(), max(44, hint.height())))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)

    def _toggle(self, todo_id, done):
        try:
            storage.update_todo(todo_id, done=done)
        except KeyError:
            pass
        self.reload()

    def _edit(self, todo_id, text):
        try:
            storage.update_todo(todo_id, text=text)
            self.hint.setText("")
        except KeyError:
            pass
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
