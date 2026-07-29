#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
茄子桌面宠物 - Eggplant Desktop Pet
"""

import sys
import os
import random
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QAction,
                             QVBoxLayout, QHBoxLayout, QPushButton, QDialog,
                             QSlider, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize, pyqtProperty
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics, QPainterPath


# ============== 对话气泡内容 ==============
DIALOGUES = [
    "你好呀~",
    "今天也要加油哦！",
    "嘿嘿，被你发现啦",
    "我是茄子，不是葡萄！",
    "摸摸头~",
    "无聊吗？陪我玩呀",
    "你在做什么呢？",
    "茄子茄子~",
    "我超可爱的对吧？",
    "不许摸我！...再摸一下嘛",
    "工作辛苦了",
    "记得喝水哦",
    "哇！好厉害",
    "嘿嘿嘿",
    "我跳得高不高？",
    "压扁了啦！",
    "摇摇晃晃~",
    "我是最可爱的茄子！",
    "想吃茄子吗？",
    "别戳我啦~",
    "你好棒！",
    "加油加油！",
    "摸鱼中...",
    "困了吗？",
    "一起加油吧！",
]


class BubbleWidget(QWidget):
    """对话气泡组件"""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 计算气泡大小
        font = QFont("Microsoft YaHei", 11)
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()

        self.padding_x = 16
        self.padding_y = 10
        self.bubble_width = text_width + self.padding_x * 2
        self.bubble_height = text_height + self.padding_y * 2
        self.tail_height = 10

        self.setFixedSize(self.bubble_width + 4, self.bubble_height + self.tail_height + 4)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 气泡主体
        path = QPainterPath()
        rect_x = 2
        rect_y = 2
        rect_w = self.bubble_width
        rect_h = self.bubble_height
        radius = 12

        # 圆角矩形
        path.addRoundedRect(rect_x, rect_y, rect_w, rect_h, radius, radius)

        # 气泡尾巴（指向下方中间）
        tail_x = rect_x + rect_w / 2
        tail_y = rect_y + rect_h
        path.moveTo(tail_x - 8, tail_y)
        path.lineTo(tail_x, tail_y + self.tail_height)
        path.lineTo(tail_x + 8, tail_y)
        path.closeSubpath()

        # 填充白色背景
        painter.fillPath(path, QColor(255, 255, 255, 245))

        # 绘制边框
        painter.setPen(QColor(220, 220, 220, 200))
        painter.drawPath(path)

        # 绘制文字
        painter.setPen(QColor(60, 60, 60))
        font = QFont("Microsoft YaHei", 11)
        painter.setFont(font)
        text_rect = QRect(rect_x + self.padding_x, rect_y + self.padding_y,
                          rect_w - self.padding_x * 2, rect_h - self.padding_y * 2)
        painter.drawText(text_rect, Qt.AlignCenter, self.text)


class EggplantPet(QWidget):
    """茄子桌面宠物主窗口"""

    def __init__(self):
        super().__init__()

        # 基础配置
        self.base_size = 150  # 基础大小
        self.current_scale = 1.0  # 当前缩放比例
        self.min_scale = 0.5
        self.max_scale = 2.5
        self.is_stay_on_top = True
        self.is_animating = False
        self.animation_index = 0  # 轮流触发互动的索引

        # 加载图片
        self.original_pixmap = QPixmap(self._get_resource_path("eggplant.png"))
        if self.original_pixmap.isNull():
            print("错误：无法加载图片 eggplant.png")
            sys.exit(1)

        # 窗口设置
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 角色标签
        self.pet_label = QLabel(self)
        self.pet_label.setAlignment(Qt.AlignCenter)
        self._update_pixmap()

        # 对话气泡
        self.bubble = None
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self._hide_bubble)

        # 拖动相关
        self.drag_position = None
        self.is_dragging = False
        self.press_pos = None

        # 动画相关
        self.animation = None
        self.original_geometry = None

        # 初始位置（屏幕右下角）
        self._init_position()

        self.show()

    def _get_resource_path(self, filename):
        """获取资源文件路径（兼容打包后）"""
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, filename)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    def _init_position(self):
        """初始化窗口位置到屏幕右下角"""
        screen = QApplication.primaryScreen().availableGeometry()
        size = int(self.base_size * self.current_scale)
        x = screen.width() - size - 50
        y = screen.height() - size - 100
        self.setGeometry(x, y, size, size)
        self.pet_label.setGeometry(0, 0, size, size)

    def _update_pixmap(self):
        """更新显示的图片（根据当前缩放）"""
        size = int(self.base_size * self.current_scale)
        scaled = self.original_pixmap.scaled(
            size, size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.pet_label.setPixmap(scaled)
        self.pet_label.setFixedSize(size, size)

    def resizeEvent(self, event):
        self.pet_label.setGeometry(0, 0, self.width(), self.height())

    # ============== 鼠标事件 ==============
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.press_pos = event.globalPos()
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            # 判断是否为拖动（移动超过一定距离才算拖动）
            if self.press_pos:
                delta = (event.globalPos() - self.press_pos).manhattanLength()
                if delta > 5:
                    self.is_dragging = True
            if self.is_dragging and not self.is_animating:
                self.move(event.globalPos() - self.drag_position)
                # 移动时隐藏气泡
                self._hide_bubble()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_dragging and not self.is_animating:
                # 点击触发互动
                self._trigger_interaction()
            self.is_dragging = False
            self.drag_position = None
            self.press_pos = None

    def wheelEvent(self, event):
        """鼠标滚轮调整大小"""
        if self.is_animating:
            return
        delta = event.angleDelta().y()
        if delta > 0:
            new_scale = min(self.current_scale + 0.1, self.max_scale)
        else:
            new_scale = max(self.current_scale - 0.1, self.min_scale)

        if new_scale != self.current_scale:
            # 保持中心位置不变
            old_size = int(self.base_size * self.current_scale)
            new_size = int(self.base_size * new_scale)
            center_x = self.x() + old_size / 2
            center_y = self.y() + old_size / 2

            self.current_scale = new_scale
            self.setFixedSize(new_size, new_size)
            self._update_pixmap()
            self.move(int(center_x - new_size / 2), int(center_y - new_size / 2))
            self._hide_bubble()

    def contextMenuEvent(self, event):
        """右键菜单"""
        menu = QMenu(self)

        # 调整大小子菜单
        size_menu = menu.addMenu("调整大小")

        small_action = QAction("小 (50%)", self)
        small_action.triggered.connect(lambda: self._set_scale(0.6))
        size_menu.addAction(small_action)

        medium_action = QAction("中 (100%)", self)
        medium_action.triggered.connect(lambda: self._set_scale(1.0))
        size_menu.addAction(medium_action)

        large_action = QAction("大 (150%)", self)
        large_action.triggered.connect(lambda: self._set_scale(1.5))
        size_menu.addAction(large_action)

        xlarge_action = QAction("超大 (200%)", self)
        xlarge_action.triggered.connect(lambda: self._set_scale(2.0))
        size_menu.addAction(xlarge_action)

        menu.addSeparator()

        # 置顶开关
        top_action = QAction("取消置顶" if self.is_stay_on_top else "始终置顶", self)
        top_action.triggered.connect(self._toggle_stay_on_top)
        menu.addAction(top_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec_(event.globalPos())

    # ============== 大小调整 ==============
    def _set_scale(self, scale):
        """设置缩放比例"""
        if self.is_animating:
            return
        old_size = int(self.base_size * self.current_scale)
        new_size = int(self.base_size * scale)
        center_x = self.x() + old_size / 2
        center_y = self.y() + old_size / 2

        self.current_scale = scale
        self.setFixedSize(new_size, new_size)
        self._update_pixmap()
        self.move(int(center_x - new_size / 2), int(center_y - new_size / 2))
        self._hide_bubble()

    def _toggle_stay_on_top(self):
        """切换置顶状态"""
        self.is_stay_on_top = not self.is_stay_on_top
        flags = self.windowFlags()
        if self.is_stay_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ============== 互动动画 ==============
    def _trigger_interaction(self):
        """触发互动（轮流播放不同动画）"""
        animations = [
            self._animate_jump,
            self._animate_squash,
            self._animate_shake,
        ]
        anim_func = animations[self.animation_index % len(animations)]
        self.animation_index += 1
        anim_func()

        # 显示对话气泡
        QTimer.singleShot(200, self._show_random_bubble)

    def _animate_jump(self):
        """跳跃动画"""
        if self.is_animating:
            return
        self.is_animating = True
        self.original_geometry = self.geometry()

        jump_height = 60
        duration = 400

        # 上升
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(duration // 2)
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(QPoint(self.x(), self.y() - jump_height))
        self.animation.setEasingCurve(QEasingCurve.OutQuad)

        # 下降
        self.animation.finished.connect(self._jump_down)
        self.animation.start()

    def _jump_down(self):
        """跳跃下落"""
        if not self.original_geometry:
            self.is_animating = False
            return
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(200)
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(self.original_geometry.topLeft())
        self.animation.setEasingCurve(QEasingCurve.InQuad)
        self.animation.finished.connect(self._animation_finished)
        self.animation.start()

    def _animate_squash(self):
        """压扁回弹动画"""
        if self.is_animating:
            return
        self.is_animating = True
        self.original_geometry = self.geometry()

        size = self.width()
        squash_ratio = 0.6  # 压扁到60%高度
        stretch_ratio = 1.15  # 横向拉伸到115%

        # 压扁
        new_width = int(size * stretch_ratio)
        new_height = int(size * squash_ratio)
        new_x = self.x() - (new_width - size) // 2
        new_y = self.y() + (size - new_height)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(150)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.geometry().adjusted(
            (new_width - size) // -2, size - new_height,
            (new_width - size) // 2, 0
        ))
        self.animation.setEasingCurve(QEasingCurve.InQuad)
        self.animation.finished.connect(self._squash_rebound)
        self.animation.start()

    def _squash_rebound(self):
        """压扁后回弹"""
        if not self.original_geometry:
            self.is_animating = False
            return
        # 回弹到略大再恢复
        size = self.original_geometry.width()
        rebound_size = int(size * 1.08)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(200)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.original_geometry)
        self.animation.setEasingCurve(QEasingCurve.OutElastic)
        self.animation.finished.connect(self._animation_finished)
        self.animation.start()

    def _animate_shake(self):
        """左右抖动动画"""
        if self.is_animating:
            return
        self.is_animating = True
        self.original_geometry = self.geometry()

        shake_distance = 12
        duration = 300

        # 使用定时器实现多次抖动
        self._shake_count = 0
        self._max_shakes = 5
        self._shake_timer = QTimer(self)
        self._shake_timer.timeout.connect(self._shake_step)
        self._shake_timer.start(duration // self._max_shakes)

    def _shake_step(self):
        """抖动的一步"""
        self._shake_count += 1
        if self._shake_count >= self._max_shakes:
            self._shake_timer.stop()
            # 回到原位
            self.setGeometry(self.original_geometry)
            self._animation_finished()
            return

        direction = 1 if self._shake_count % 2 == 1 else -1
        offset = 12 if self._shake_count < self._max_shakes - 1 else 0
        self.move(self.original_geometry.x() + direction * offset, self.y())

    def _animation_finished(self):
        """动画结束"""
        self.is_animating = False
        self.animation = None
        if self.original_geometry:
            self.setGeometry(self.original_geometry)
            self.original_geometry = None

    # ============== 对话气泡 ==============
    def _show_random_bubble(self):
        """显示随机对话气泡"""
        text = random.choice(DIALOGUES)
        self._show_bubble(text)

    def _show_bubble(self, text):
        """显示对话气泡"""
        self._hide_bubble()

        self.bubble = BubbleWidget(text)
        # 气泡显示在角色上方居中
        bubble_x = self.x() + self.width() // 2 - self.bubble.width() // 2
        bubble_y = self.y() - self.bubble.height() - 5

        # 确保气泡不超出屏幕
        screen = QApplication.primaryScreen().availableGeometry()
        if bubble_x < 10:
            bubble_x = 10
        if bubble_x + self.bubble.width() > screen.width() - 10:
            bubble_x = screen.width() - self.bubble.width() - 10
        if bubble_y < 10:
            # 如果上方空间不够，显示在下方
            bubble_y = self.y() + self.height() + 5

        self.bubble.move(bubble_x, bubble_y)
        self.bubble.show()

        # 2.5秒后自动消失
        self.bubble_timer.start(2500)

    def _hide_bubble(self):
        """隐藏对话气泡"""
        self.bubble_timer.stop()
        if self.bubble:
            self.bubble.close()
            self.bubble = None

    def closeEvent(self, event):
        self._hide_bubble()
        event.accept()


def main():
    # 高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    pet = EggplantPet()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
