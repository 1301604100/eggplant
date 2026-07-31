# -*- coding: utf-8 -*-
"""说话气泡与聊天输入气泡。"""

from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QRect, QEvent
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPainterPath,
)


class SpeechBubble(QWidget):
    """对话气泡（展示文本）"""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        font = QFont("Microsoft YaHei", 11)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()

        self.padding_x = 16
        self.padding_y = 10
        self.bubble_width = max(text_width + self.padding_x * 2, 60)
        self.bubble_height = text_height + self.padding_y * 2
        self.tail_height = 10

        self.setFixedSize(self.bubble_width + 4, self.bubble_height + self.tail_height + 4)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        rect_x = 2
        rect_y = 2
        rect_w = self.bubble_width
        rect_h = self.bubble_height
        radius = 12

        path.addRoundedRect(rect_x, rect_y, rect_w, rect_h, radius, radius)

        tail_x = rect_x + rect_w / 2
        tail_y = rect_y + rect_h
        path.moveTo(tail_x - 8, tail_y)
        path.lineTo(tail_x, tail_y + self.tail_height)
        path.lineTo(tail_x + 8, tail_y)
        path.closeSubpath()

        painter.fillPath(path, QColor(255, 255, 255, 245))
        painter.setPen(QColor(220, 220, 220, 200))
        painter.drawPath(path)

        painter.setPen(QColor(60, 60, 60))
        font = QFont("Microsoft YaHei", 11)
        painter.setFont(font)
        text_rect = QRect(
            rect_x + self.padding_x,
            rect_y + self.padding_y,
            rect_w - self.padding_x * 2,
            rect_h - self.padding_y * 2,
        )
        painter.drawText(text_rect, Qt.AlignCenter, self.text)


class ChatInputBubble(QWidget):
    """聊天气泡输入框"""

    def __init__(self, parent=None, on_send=None):
        super().__init__(parent)
        self.on_send = on_send
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("对我说点什么吧...")
        self.input_field.setMinimumWidth(220)
        self.input_field.setFont(QFont("Microsoft YaHei", 11))
        self.input_field.returnPressed.connect(self._emit_send)
        self.input_field.installEventFilter(self)

        self.send_btn = QPushButton("发送")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFont(QFont("Microsoft YaHei", 11))
        self.send_btn.clicked.connect(self._emit_send)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self.input_field)
        layout.addWidget(self.send_btn)

        self.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 235);
                border-radius: 14px;
            }
            QLineEdit {
                background: rgba(255, 255, 255, 230);
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 6px 10px;
                color: #333;
            }
            QPushButton {
                background: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: #6d28d9;
            }
        """)

    def focus_input(self):
        self.input_field.setFocus()
        self.activateWindow()

    def clear(self):
        self.input_field.clear()

    def _emit_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        if self.on_send:
            self.on_send(text)

    def eventFilter(self, obj, event):
        if obj is self.input_field and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class ConfirmBubble(QWidget):
    """带确认/取消的提示气泡。"""

    def __init__(self, text, confirm_text="更新", cancel_text="稍后",
                 on_confirm=None, on_cancel=None, parent=None):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Microsoft YaHei", 11))
        self.label.setStyleSheet("color: #333; background: transparent;")

        self.confirm_btn = QPushButton(confirm_text)
        self.confirm_btn.setObjectName("confirmBtn")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setFont(QFont("Microsoft YaHei", 11))
        self.confirm_btn.clicked.connect(self._emit_confirm)

        self.cancel_btn = QPushButton(cancel_text)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFont(QFont("Microsoft YaHei", 11))
        self.cancel_btn.clicked.connect(self._emit_cancel)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.confirm_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        layout.addWidget(self.label)
        layout.addLayout(row)

        self.setMinimumWidth(260)
        self.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 235);
                border-radius: 14px;
            }
            QPushButton {
                background: #eee;
                color: #333;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover { background: #e2e2e2; }
            QPushButton#confirmBtn {
                background: #4b5563;
                color: white;
            }
            QPushButton#confirmBtn:hover { background: #374151; }
        """)

    def _emit_confirm(self):
        self.hide()
        if self.on_confirm:
            self.on_confirm()

    def _emit_cancel(self):
        self.hide()
        if self.on_cancel:
            self.on_cancel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._emit_cancel()
            return
        super().keyPressEvent(event)
