#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
茄子桌面宠物 - Eggplant Desktop Pet
"""

import sys
import os
import random
import tempfile
import threading
import webbrowser
from ctypes import CFUNCTYPE, c_char_p, c_long, c_void_p, cdll, util
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu, QAction
from PyQt5.QtCore import (
    Qt, QObject, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect,
    QSequentialAnimationGroup, pyqtSignal,
)
from PyQt5.QtGui import QPixmap, QIcon

from bubble import SpeechBubble, ChatInputBubble, ConfirmBubble
from chat import reply as chat_reply
from tray import PetTray
from bookmarks import BookmarkPanel
from todos import TodoPanel
import storage
import updater


# macOS: Qt 的 WindowStaysOnTopHint 约等于 level=8；此前误用 NSFloatingWindowLevel=3 反而更低
# 置顶用 NSStatusWindowLevel=25，才能压过普通应用窗口
_MAC_STATUS_LEVEL = 25
_MAC_NORMAL_LEVEL = 0
# CanJoinAllSpaces | Stationary | FullScreenAuxiliary
_MAC_COLLECTION_BEHAVIOR = (1 << 0) | (1 << 4) | (1 << 8)
_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040


def apply_native_topmost(widget, enabled):
    """用系统原生 API 设置置顶（Qt 的 WindowStaysOnTopHint 在 macOS 上常失效）"""
    if widget is None:
        return
    try:
        if sys.platform == "darwin":
            _macos_set_window_level(widget, enabled)
        elif sys.platform == "win32":
            _windows_set_topmost(widget, enabled)
    except Exception:
        pass


def _macos_set_window_level(widget, enabled):
    libobjc = cdll.LoadLibrary(util.find_library("objc"))
    sel_registerName = libobjc.sel_registerName
    sel_registerName.restype = c_void_p
    sel_registerName.argtypes = [c_char_p]

    msg_void = CFUNCTYPE(c_void_p, c_void_p, c_void_p)(("objc_msgSend", libobjc))
    msg_set_long = CFUNCTYPE(None, c_void_p, c_void_p, c_long)(("objc_msgSend", libobjc))
    msg_set_bool = CFUNCTYPE(None, c_void_p, c_void_p, c_long)(("objc_msgSend", libobjc))

    ns_view = c_void_p(int(widget.winId()))
    ns_window = msg_void(ns_view, sel_registerName(b"window"))
    if not ns_window:
        return

    # 失焦时不要自动隐藏（Tool 窗口默认可能 hidesOnDeactivate）
    msg_set_bool(ns_window, sel_registerName(b"setHidesOnDeactivate:"), 0)

    if enabled:
        msg_set_long(ns_window, sel_registerName(b"setLevel:"), _MAC_STATUS_LEVEL)
        msg_set_long(
            ns_window,
            sel_registerName(b"setCollectionBehavior:"),
            _MAC_COLLECTION_BEHAVIOR,
        )
        msg_void(ns_window, sel_registerName(b"orderFrontRegardless"))
    else:
        msg_set_long(ns_window, sel_registerName(b"setLevel:"), _MAC_NORMAL_LEVEL)


def _windows_set_topmost(widget, enabled):
    user32 = cdll.LoadLibrary("user32")
    hwnd = int(widget.winId())
    insert_after = _HWND_TOPMOST if enabled else _HWND_NOTOPMOST
    user32.SetWindowPos(
        hwnd, insert_after, 0, 0, 0, 0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
    )


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


class _UpdateSignals(QObject):
    """把 Python 工作线程的结果排队投递到 Qt 主线程。"""

    check_finished = pyqtSignal(object, object, bool)
    download_finished = pyqtSignal(object, object)


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
        self.setWindowTitle("茄子桌宠")
        self.setWindowIcon(QIcon(self._get_resource_path("eggplant.png")))

        # 角色标签
        self.pet_label = QLabel(self)
        self.pet_label.setAlignment(Qt.AlignCenter)
        self._update_pixmap()

        # 对话气泡 / 聊天输入
        self.bubble = None
        self.chat_input = None
        self.bookmark_panel = None
        self.todo_panel = None
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

        # 系统托盘
        callbacks = {
            "show_pet": self._show_pet,
            "hide_pet": self._hide_pet,
            "open_chat": self._open_chat,
            "populate_bookmarks_menu": self._populate_bookmarks_menu,
            "toggle_todo_panel": self._toggle_todo_panel,
            "quit": self._quit_app,
        }
        if updater.should_enable_updater():
            callbacks["check_for_updates"] = (
                lambda: self._check_for_updates(manual=True)
            )
        self.tray = PetTray(
            self,
            self._get_resource_path("eggplant.png"),
            callbacks,
        )
        self.tray.show()

        self._update_prompt = None
        self._update_snoozed = False
        self._update_busy = False
        self._update_signals = _UpdateSignals(self)
        self._update_signals.check_finished.connect(
            self._on_update_check_done,
            Qt.QueuedConnection,
        )
        self._update_signals.download_finished.connect(
            self._on_download_done,
            Qt.QueuedConnection,
        )
        if updater.should_enable_updater():
            QTimer.singleShot(
                3000,
                lambda: self._check_for_updates(manual=False),
            )

        # 初始位置（屏幕右下角）
        self._init_position()
        self._apply_stay_on_top()

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
                self._reposition_open_panels()

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
            self._reposition_open_panels()

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

        bookmarks_menu = menu.addMenu("常用网址")
        self._populate_bookmarks_menu(bookmarks_menu)

        todo_action = QAction("待办", self)
        todo_action.triggered.connect(self._toggle_todo_panel)
        menu.addAction(todo_action)

        menu.addSeparator()

        chat_action = QAction("聊聊天", self)
        chat_action.triggered.connect(self._open_chat)
        menu.addAction(chat_action)

        hide_action = QAction("隐藏", self)
        hide_action.triggered.connect(self._hide_pet)
        menu.addAction(hide_action)

        menu.addSeparator()

        # 置顶开关
        top_action = QAction("取消置顶" if self.is_stay_on_top else "始终置顶", self)
        top_action.triggered.connect(self._toggle_stay_on_top)
        menu.addAction(top_action)

        if updater.should_enable_updater():
            menu.addSeparator()
            update_action = QAction("检查更新", self)
            update_action.triggered.connect(
                lambda: self._check_for_updates(manual=True)
            )
            menu.addAction(update_action)

        menu.addSeparator()

        # 退出
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        menu.exec_(event.globalPos())

    def _quit_app(self):
        """彻底退出（macOS 上 Tool 窗口 close 不会结束进程，图标会留在程序坞）"""
        self._hide_bubble()
        self._hide_update_prompt()
        self._hide_chat_input()
        self._hide_panels()
        if self.tray:
            self.tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _hide_pet(self):
        self._hide_bubble()
        self._hide_update_prompt()
        self._hide_chat_input()
        self._hide_panels()
        self.hide()

    def _show_pet(self):
        self.show()
        self.raise_()
        self._refresh_native_topmost()

    def _open_chat(self):
        """打开聊天输入气泡"""
        self._show_pet()
        self._hide_bubble()
        self._close_exclusive_ui(keep="chat")
        if self.chat_input is None:
            self.chat_input = ChatInputBubble(on_send=self._on_chat_send)
        self._position_chat_input()
        self.chat_input.show()
        self.chat_input.raise_()
        apply_native_topmost(self.chat_input, self.is_stay_on_top)
        self.chat_input.focus_input()

    def _hide_chat_input(self):
        if self.chat_input is not None:
            self.chat_input.hide()

    def _hide_panels(self):
        if self.bookmark_panel is not None:
            self.bookmark_panel.hide()
        if self.todo_panel is not None:
            self.todo_panel.hide()

    def _close_exclusive_ui(self, keep=None):
        """keep: None | 'chat' | 'bookmarks' | 'todos'"""
        if keep != "chat":
            self._hide_chat_input()
        if keep != "bookmarks" and self.bookmark_panel is not None:
            self.bookmark_panel.hide()
        if keep != "todos" and self.todo_panel is not None:
            self.todo_panel.hide()

    def _position_panel(self, panel):
        if panel is None:
            return
        panel.adjustSize()
        x = self.x() + self.width() // 2 - panel.width() // 2
        y = self.y() + self.height() + 8
        screen = QApplication.primaryScreen().availableGeometry()
        if x < 10:
            x = 10
        if x + panel.width() > screen.width() - 10:
            x = screen.width() - panel.width() - 10
        if y + panel.height() > screen.height() - 10:
            y = max(10, self.y() - panel.height() - 8)
        panel.move(x, y)

    def _reposition_open_panels(self):
        if self.bookmark_panel is not None and self.bookmark_panel.isVisible():
            self._position_panel(self.bookmark_panel)
        if self.todo_panel is not None and self.todo_panel.isVisible():
            self._position_panel(self.todo_panel)
        if self.chat_input is not None and self.chat_input.isVisible():
            self._position_chat_input()

    def _open_bookmark_url(self, url):
        try:
            ok = webbrowser.open(url)
            if not ok:
                self._show_bubble("打不开这个链接", duration_ms=2500)
        except Exception:
            self._show_bubble("打不开这个链接", duration_ms=2500)

    def _populate_bookmarks_menu(self, submenu):
        submenu.clear()
        bookmarks = storage.list_bookmarks()
        if not bookmarks:
            empty = QAction("暂无网址", submenu)
            empty.setEnabled(False)
            submenu.addAction(empty)
        else:
            for b in bookmarks:
                action = QAction(b["alias"], submenu)
                action.triggered.connect(
                    lambda _=False, u=b["url"]: self._open_bookmark_url(u)
                )
                submenu.addAction(action)
        submenu.addSeparator()
        manage = QAction("管理…", submenu)
        manage.triggered.connect(self._toggle_bookmark_panel)
        submenu.addAction(manage)

    def _toggle_bookmark_panel(self):
        self._show_pet()
        if self.bookmark_panel is not None and self.bookmark_panel.isVisible():
            self.bookmark_panel.hide()
            return
        self._close_exclusive_ui(keep="bookmarks")
        if self.bookmark_panel is None:
            self.bookmark_panel = BookmarkPanel()
        self.bookmark_panel.reload()
        self._position_panel(self.bookmark_panel)
        self.bookmark_panel.show()
        self.bookmark_panel.raise_()
        apply_native_topmost(self.bookmark_panel, self.is_stay_on_top)

    def _toggle_todo_panel(self):
        self._show_pet()
        if self.todo_panel is not None and self.todo_panel.isVisible():
            self.todo_panel.hide()
            return
        self._close_exclusive_ui(keep="todos")
        if self.todo_panel is None:
            self.todo_panel = TodoPanel()
        self.todo_panel.reload()
        self._position_panel(self.todo_panel)
        self.todo_panel.show()
        self.todo_panel.raise_()
        apply_native_topmost(self.todo_panel, self.is_stay_on_top)

    def _position_chat_input(self):
        if self.chat_input is None:
            return
        self.chat_input.adjustSize()
        x = self.x() + self.width() // 2 - self.chat_input.width() // 2
        y = self.y() - self.chat_input.height() - 8
        screen = QApplication.primaryScreen().availableGeometry()
        if x < 10:
            x = 10
        if x + self.chat_input.width() > screen.width() - 10:
            x = screen.width() - self.chat_input.width() - 10
        if y < 10:
            y = self.y() + self.height() + 8
        self.chat_input.move(x, y)

    def _on_chat_send(self, text):
        self._hide_chat_input()
        answer = chat_reply(text)
        if answer:
            self._show_bubble(answer, duration_ms=3500)

    # ============== 自动更新 ==============
    def _check_for_updates(self, manual=False):
        if not updater.should_enable_updater():
            return
        if self._update_prompt is not None:
            return
        if self._update_busy:
            return
        if (not manual) and self._update_snoozed:
            return

        self._update_busy = True

        def worker():
            err = None
            result = None
            try:
                result = updater.check_for_update()
            except Exception as exc:
                err = exc

            self._update_signals.check_finished.emit(result, err, manual)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self._on_update_check_done(None, exc, manual=manual)

    def _on_update_check_done(self, result, err, manual=False):
        self._update_busy = False
        if err is not None:
            if manual:
                self._show_bubble("检查失败，请稍后重试", duration_ms=3000)
            return
        if result is None:
            if manual:
                local = updater.read_local_version()
                self._show_bubble(
                    "已是最新版本 %s" % local,
                    duration_ms=3000,
                )
            return
        if (not manual) and self._update_snoozed:
            return
        self._show_update_prompt(result)

    def _show_update_prompt(self, release):
        self._hide_bubble()
        self._hide_update_prompt()
        local = updater.read_local_version()
        text = "发现新版本 %s（当前 %s），要更新吗？" % (
            release["version"],
            local,
        )
        self._update_prompt = ConfirmBubble(
            text,
            confirm_text="更新",
            cancel_text="稍后",
            on_confirm=lambda: self._start_download_update(release),
            on_cancel=self._snooze_update_prompt,
        )
        prompt = self._update_prompt
        prompt.adjustSize()
        bubble_x = self.x() + self.width() // 2 - prompt.width() // 2
        bubble_y = self.y() - prompt.height() - 5
        screen = QApplication.primaryScreen().availableGeometry()
        if bubble_x < 10:
            bubble_x = 10
        if bubble_x + prompt.width() > screen.width() - 10:
            bubble_x = screen.width() - prompt.width() - 10
        if bubble_y < 10:
            bubble_y = self.y() + self.height() + 5
        prompt.move(bubble_x, bubble_y)
        prompt.show()
        apply_native_topmost(prompt, self.is_stay_on_top)

    def _hide_update_prompt(self):
        if self._update_prompt:
            self._update_prompt.close()
            self._update_prompt = None

    def _snooze_update_prompt(self):
        self._update_snoozed = True
        self._hide_update_prompt()

    def _start_download_update(self, release):
        if self._update_busy:
            return
        self._update_busy = True
        self._hide_update_prompt()
        self._show_bubble("正在下载…", duration_ms=60000)

        def worker():
            err = None
            script = None
            try:
                tmpdir = os.path.join(
                    tempfile.gettempdir(),
                    "eggplant_pet_update",
                )
                os.makedirs(tmpdir, exist_ok=True)
                dest = os.path.join(
                    tmpdir,
                    "EggplantPet-Windows-%s.exe" % release["version"],
                )
                updater.download_update(
                    release["download_url"],
                    dest,
                    expected_size=release.get("size"),
                )
                script = os.path.join(tmpdir, "update.bat")
                updater.write_update_script(
                    sys.executable,
                    dest,
                    os.getpid(),
                    script,
                )
            except Exception as exc:
                err = exc

            self._update_signals.download_finished.emit(err, script)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as exc:
            self._on_download_done(exc, None)

    def _on_download_done(self, err, script_path):
        self._update_busy = False
        if err is not None:
            self._show_bubble("下载失败", duration_ms=3000)
            return
        self._show_bubble("正在更新，即将重启…", duration_ms=2000)
        updater.launch_update_and_exit(script_path, self._quit_app)

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
        self._reposition_open_panels()

    def _toggle_stay_on_top(self):
        """切换置顶状态"""
        self.is_stay_on_top = not self.is_stay_on_top
        self._apply_stay_on_top()

    def _apply_stay_on_top(self):
        """应用置顶状态（Qt 标志 + 原生窗口层级）"""
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.is_stay_on_top:
            flags |= Qt.WindowStaysOnTopHint
        pos = self.pos()
        self.setWindowFlags(flags)
        self.move(pos)
        self.show()
        self.raise_()
        # 立即设置一次，并延后补设（等 Qt 建好 NSWindow 后再压高层级）
        self._refresh_native_topmost()
        QTimer.singleShot(0, self._refresh_native_topmost)
        QTimer.singleShot(100, self._refresh_native_topmost)

    def _refresh_native_topmost(self):
        apply_native_topmost(self, self.is_stay_on_top)
        if self.bubble is not None:
            apply_native_topmost(self.bubble, self.is_stay_on_top)
        if self.chat_input is not None and self.chat_input.isVisible():
            apply_native_topmost(self.chat_input, self.is_stay_on_top)
        if self.bookmark_panel is not None and self.bookmark_panel.isVisible():
            apply_native_topmost(self.bookmark_panel, self.is_stay_on_top)
        if self.todo_panel is not None and self.todo_panel.isVisible():
            apply_native_topmost(self.todo_panel, self.is_stay_on_top)

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

        # 气泡稍晚出现，避开预备动作
        QTimer.singleShot(280, self._show_random_bubble)

    def _stop_running_animation(self):
        if self.animation is not None:
            try:
                self.animation.stop()
            except Exception:
                pass
            self.animation = None
        timer = getattr(self, "_shake_timer", None)
        if timer is not None:
            timer.stop()
            self._shake_timer = None

    def _make_pos_anim(self, start, end, duration, curve):
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        return anim

    def _make_geo_anim(self, start, end, duration, curve):
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(curve)
        return anim

    def _squashed_rect(self, base: QRect, width_ratio: float, height_ratio: float) -> QRect:
        """底部对齐的压扁矩形，用于落地/挤压感"""
        w = max(8, int(base.width() * width_ratio))
        h = max(8, int(base.height() * height_ratio))
        x = base.x() + (base.width() - w) // 2
        y = base.y() + base.height() - h
        return QRect(x, y, w, h)

    def _animate_jump(self):
        """跳跃：下蹲预备 → 起跳 → 落下 → 轻弹落地"""
        if self.is_animating:
            return
        self._stop_running_animation()
        self.is_animating = True
        self.original_geometry = QRect(self.geometry())
        origin = self.original_geometry.topLeft()
        peak = QPoint(origin.x(), origin.y() - 72)

        group = QSequentialAnimationGroup(self)
        dip = self._make_pos_anim(
            origin, QPoint(origin.x(), origin.y() + 10), 90, QEasingCurve.InQuad
        )
        up = self._make_pos_anim(
            QPoint(origin.x(), origin.y() + 10), peak, 300, QEasingCurve.OutCubic
        )
        down = self._make_pos_anim(peak, origin, 270, QEasingCurve.InCubic)
        bounce = QPropertyAnimation(self, b"pos")
        bounce.setDuration(220)
        bounce.setStartValue(origin)
        bounce.setKeyValueAt(0.0, origin)
        bounce.setKeyValueAt(0.35, QPoint(origin.x(), origin.y() - 14))
        bounce.setKeyValueAt(1.0, origin)
        bounce.setEasingCurve(QEasingCurve.OutQuad)

        group.addAnimation(dip)
        group.addAnimation(up)
        group.addAnimation(down)
        group.addAnimation(bounce)
        group.finished.connect(self._animation_finished)
        self.animation = group
        group.start()

    def _animate_squash(self):
        """压扁：柔和下压 → 过冲回弹 → 归位（替代生硬 OutElastic）"""
        if self.is_animating:
            return
        self._stop_running_animation()
        self.is_animating = True
        self.original_geometry = QRect(self.geometry())
        base = QRect(self.original_geometry)

        pressed = self._squashed_rect(base, 1.18, 0.72)
        overshoot = self._squashed_rect(base, 0.94, 1.06)

        group = QSequentialAnimationGroup(self)
        press = self._make_geo_anim(base, pressed, 160, QEasingCurve.InOutSine)
        hold = self._make_geo_anim(pressed, pressed, 40, QEasingCurve.Linear)
        release = self._make_geo_anim(pressed, overshoot, 220, QEasingCurve.OutBack)
        settle = self._make_geo_anim(overshoot, base, 160, QEasingCurve.OutSine)

        # OutBack 过冲幅度略收一点，避免抖太狠
        release.setEasingCurve(QEasingCurve(QEasingCurve.OutBack))
        curve = release.easingCurve()
        curve.setAmplitude(1.05)
        curve.setOvershoot(1.2)
        release.setEasingCurve(curve)

        group.addAnimation(press)
        group.addAnimation(hold)
        group.addAnimation(release)
        group.addAnimation(settle)
        group.finished.connect(self._animation_finished)
        self.animation = group
        group.start()

    def _animate_shake(self):
        """抖动：幅度衰减的平滑左右摆动"""
        if self.is_animating:
            return
        self._stop_running_animation()
        self.is_animating = True
        self.original_geometry = QRect(self.geometry())
        origin = self.original_geometry.topLeft()
        y = origin.y()

        # 衰减位移：越晃越小
        offsets = [16, -13, 10, -7, 4, -2, 0]
        group = QSequentialAnimationGroup(self)
        prev = origin
        for i, ox in enumerate(offsets):
            end = QPoint(origin.x() + ox, y)
            duration = 55 + i * 8
            step = self._make_pos_anim(prev, end, duration, QEasingCurve.InOutSine)
            group.addAnimation(step)
            prev = end

        group.finished.connect(self._animation_finished)
        self.animation = group
        group.start()

    def _animation_finished(self):
        """动画结束，确保几何归位"""
        self.is_animating = False
        self.animation = None
        if self.original_geometry is not None:
            self.setGeometry(self.original_geometry)
            self.original_geometry = None

    # ============== 对话气泡 ==============
    def _show_random_bubble(self):
        """显示随机对话气泡"""
        text = random.choice(DIALOGUES)
        self._show_bubble(text)

    def _show_bubble(self, text, duration_ms=2500):
        """显示对话气泡"""
        self._hide_bubble()

        self.bubble = SpeechBubble(text)
        bubble_x = self.x() + self.width() // 2 - self.bubble.width() // 2
        bubble_y = self.y() - self.bubble.height() - 5

        screen = QApplication.primaryScreen().availableGeometry()
        if bubble_x < 10:
            bubble_x = 10
        if bubble_x + self.bubble.width() > screen.width() - 10:
            bubble_x = screen.width() - self.bubble.width() - 10
        if bubble_y < 10:
            bubble_y = self.y() + self.height() + 5

        self.bubble.move(bubble_x, bubble_y)
        self.bubble.show()
        apply_native_topmost(self.bubble, self.is_stay_on_top)

        self.bubble_timer.start(duration_ms)

    def _hide_bubble(self):
        """隐藏对话气泡"""
        self.bubble_timer.stop()
        if self.bubble:
            self.bubble.close()
            self.bubble = None

    def closeEvent(self, event):
        self._hide_bubble()
        self._hide_update_prompt()
        self._hide_chat_input()
        self._hide_panels()
        if self.tray:
            self.tray.hide()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def main():
    # 高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("茄子桌宠")
    # 托盘常驻时，隐藏主窗口不应退出进程
    app.setQuitOnLastWindowClosed(False)

    # 应用/程序坞图标（与托盘一致用茄子图）
    icon_path = os.path.join(
        getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
        "eggplant.png",
    )
    app_icon = QIcon(icon_path)
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    pet = EggplantPet()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
