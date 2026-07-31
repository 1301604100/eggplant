# 常用网址 + 待办列表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在茄子桌宠右键与托盘菜单中加入常用网址（别名 + 快速打开 + 管理面板）与待办列表（悬浮在茄子下方），数据持久化到本地 JSON。

**Architecture:** `storage.py` 负责 `~/.eggplant_pet/data.json` 的读写与 CRUD；`bookmarks.py` / `todos.py` 提供对齐 `ChatInputBubble` 的悬浮面板；`main.py` 负责菜单、定位跟随、互斥与打开浏览器；`tray.py` 注入相同入口回调。

**Tech Stack:** Python 3.8+、PyQt5、stdlib（json / pathlib / uuid / webbrowser / unittest）；无新第三方依赖。

**Spec:** `docs/superpowers/specs/2026-07-31-bookmarks-todos-design.md`

## Global Constraints

- 不做云同步、分类/标签、优先级、截止日期、导入导出
- 不做完整 GUI 自动化；面板靠手测
- 兼容 Python 3.8（类型注解用注释或 `typing`，不用 `list[dict]` 运行时语法若影响 3.8）
- 打包需补 `--hidden-import storage` / `bookmarks` / `todos`
- 悬浮面板须调用 `apply_native_topmost`（`main.py` 已有）
- 退出 / 隐藏宠物时必须关闭业务面板

## File Structure

| 文件 | 动作 | 职责 |
|------|------|------|
| `storage.py` | Create | JSON 持久化 + bookmarks/todos CRUD |
| `tests/test_storage.py` | Create | storage 单测（临时目录） |
| `bookmarks.py` | Create | 网址管理悬浮面板 `BookmarkPanel` |
| `todos.py` | Create | 待办悬浮面板 `TodoPanel` |
| `main.py` | Modify | 菜单、定位、互斥、`webbrowser.open`、跟随 |
| `tray.py` | Modify | 托盘「常用网址」「待办」入口 |
| `build.bat` / `.github/workflows/build-windows.yml` | Modify | hidden-import |
| `README.md` | Modify | 功能说明 |

---

### Task 1: storage.py + 单测（TDD）

**Files:**
- Create: `storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `DEFAULT_DATA = {"bookmarks": [], "todos": []}`
  - `data_path() -> Path` — 默认 `Path.home() / ".eggplant_pet" / "data.json"`；若环境变量 `EGGPLANT_PET_HOME` 有值，则用 `Path(EGGPLANT_PET_HOME) / "data.json"`（便于测试）
  - `load() -> dict`
  - `save(data: dict) -> None`
  - `normalize_url(url: str) -> str`
  - `list_bookmarks() -> list`
  - `add_bookmark(alias: str, url: str) -> dict`
  - `update_bookmark(bookmark_id: str, alias: str, url: str) -> dict`
  - `delete_bookmark(bookmark_id: str) -> None`
  - `list_todos() -> list`
  - `add_todo(text: str) -> dict`
  - `update_todo(todo_id: str, text=None, done=None) -> dict`
  - `delete_todo(todo_id: str) -> None`
  - `clear_completed_todos() -> int`

- [ ] **Step 1: Write the failing tests**

```python
# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from pathlib import Path

import storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["EGGPLANT_PET_HOME"] = self.tmp.name
        # 避免模块缓存路径；每次用 data_path() 读 env

    def tearDown(self):
        os.environ.pop("EGGPLANT_PET_HOME", None)

    def test_normalize_url_adds_https(self):
        self.assertEqual(storage.normalize_url("github.com"), "https://github.com")
        self.assertEqual(storage.normalize_url("https://a.com"), "https://a.com")
        self.assertEqual(storage.normalize_url("http://a.com"), "http://a.com")

    def test_load_missing_returns_empty_and_creates_file(self):
        data = storage.load()
        self.assertEqual(data["bookmarks"], [])
        self.assertEqual(data["todos"], [])
        self.assertTrue(storage.data_path().is_file())

    def test_load_corrupt_recovers(self):
        p = storage.data_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        data = storage.load()
        self.assertEqual(data, storage.DEFAULT_DATA)

    def test_bookmark_crud(self):
        b = storage.add_bookmark("GH", "github.com")
        self.assertEqual(b["alias"], "GH")
        self.assertEqual(b["url"], "https://github.com")
        self.assertTrue(b["id"])
        self.assertEqual(len(storage.list_bookmarks()), 1)
        storage.update_bookmark(b["id"], "GitHub", "https://github.com/x")
        self.assertEqual(storage.list_bookmarks()[0]["alias"], "GitHub")
        storage.delete_bookmark(b["id"])
        self.assertEqual(storage.list_bookmarks(), [])

    def test_add_bookmark_rejects_empty(self):
        with self.assertRaises(ValueError):
            storage.add_bookmark("", "https://a.com")
        with self.assertRaises(ValueError):
            storage.add_bookmark("a", "  ")

    def test_todo_crud_and_clear_completed(self):
        t1 = storage.add_todo("写周报")
        t2 = storage.add_todo("开会")
        storage.update_todo(t1["id"], done=True)
        storage.update_todo(t2["id"], text="开会纪要")
        n = storage.clear_completed_todos()
        self.assertEqual(n, 1)
        todos = storage.list_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["text"], "开会纪要")
        self.assertFalse(todos[0]["done"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_storage -v`  
Expected: FAIL（`ModuleNotFoundError: storage` 或属性不存在）

- [ ] **Step 3: Implement `storage.py`**

```python
# -*- coding: utf-8 -*-
"""本地 JSON 持久化：常用网址与待办。"""

from __future__ import print_function

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA = {"bookmarks": [], "todos": []}


def data_path():
    home = os.environ.get("EGGPLANT_PET_HOME")
    base = Path(home) if home else Path.home() / ".eggplant_pet"
    return base / "data.json"


def load():
    path = data_path()
    if not path.is_file():
        data = {"bookmarks": [], "todos": []}
        save(data)
        return data
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("root must be object")
        data = {
            "bookmarks": list(raw.get("bookmarks") or []),
            "todos": list(raw.get("todos") or []),
        }
        return data
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        print("storage.load: corrupt data, resetting:", e)
        data = {"bookmarks": [], "todos": []}
        save(data)
        return data


def save(data):
    path = data_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError as e:
        print("storage.save failed:", e)


def normalize_url(url):
    text = (url or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return text
    return "https://" + text


def list_bookmarks():
    return list(load().get("bookmarks") or [])


def add_bookmark(alias, url):
    alias = (alias or "").strip()
    url = normalize_url(url)
    if not alias or not url:
        raise ValueError("alias and url required")
    data = load()
    item = {"id": str(uuid.uuid4()), "alias": alias, "url": url}
    data["bookmarks"].append(item)
    save(data)
    return item


def update_bookmark(bookmark_id, alias, url):
    alias = (alias or "").strip()
    url = normalize_url(url)
    if not alias or not url:
        raise ValueError("alias and url required")
    data = load()
    for item in data["bookmarks"]:
        if item.get("id") == bookmark_id:
            item["alias"] = alias
            item["url"] = url
            save(data)
            return item
    raise KeyError(bookmark_id)


def delete_bookmark(bookmark_id):
    data = load()
    data["bookmarks"] = [b for b in data["bookmarks"] if b.get("id") != bookmark_id]
    save(data)


def list_todos():
    return list(load().get("todos") or [])


def add_todo(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("text required")
    data = load()
    item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "done": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["todos"].append(item)
    save(data)
    return item


def update_todo(todo_id, text=None, done=None):
    data = load()
    for item in data["todos"]:
        if item.get("id") == todo_id:
            if text is not None:
                text = text.strip()
                if not text:
                    raise ValueError("text required")
                item["text"] = text
            if done is not None:
                item["done"] = bool(done)
            save(data)
            return item
    raise KeyError(todo_id)


def delete_todo(todo_id):
    data = load()
    data["todos"] = [t for t in data["todos"] if t.get("id") != todo_id]
    save(data)


def clear_completed_todos():
    data = load()
    before = len(data["todos"])
    data["todos"] = [t for t in data["todos"] if not t.get("done")]
    removed = before - len(data["todos"])
    save(data)
    return removed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_storage -v`  
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add storage.py tests/test_storage.py
git commit -m "$(cat <<'EOF'
feat: 添加本地 JSON 存储与 bookmarks/todos CRUD

为常用网址和待办提供可测的持久化层，支持坏文件恢复与 URL 规范化。
EOF
)"
```

---

### Task 2: BookmarkPanel 悬浮面板

**Files:**
- Create: `bookmarks.py`

**Interfaces:**
- Consumes: `storage.list_bookmarks`, `add_bookmark`, `update_bookmark`, `delete_bookmark`
- Produces: `class BookmarkPanel(QWidget)`
  - `__init__(self, on_close=None)`
  - `reload(self)` — 从 storage 刷新列表
  - `keyPressEvent` / Esc → `hide()` 并可选调用 `on_close`

- [ ] **Step 1: Implement `bookmarks.py`**

实现要点（对齐 `bubble.ChatInputBubble` 窗口标志与白底圆角样式）：

```python
# -*- coding: utf-8 -*-
"""常用网址管理悬浮面板。"""

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QMessageBox,
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
```

- [ ] **Step 2: Smoke import**

Run: `python -c "from bookmarks import BookmarkPanel; print('ok')"`  
Expected: `ok`（需已安装 PyQt5）

- [ ] **Step 3: Commit**

```bash
git add bookmarks.py
git commit -m "$(cat <<'EOF'
feat: 添加常用网址管理悬浮面板

提供别名/URL 的添加、保存与删除，样式对齐聊天气泡。
EOF
)"
```

---

### Task 3: TodoPanel 悬浮面板

**Files:**
- Create: `todos.py`

**Interfaces:**
- Consumes: `storage.list_todos`, `add_todo`, `update_todo`, `delete_todo`, `clear_completed_todos`
- Produces: `class TodoPanel(QWidget)`
  - `__init__(self, on_close=None)`
  - `reload(self)`
  - Esc / 关闭 → hide + `on_close`

- [ ] **Step 1: Implement `todos.py`**

```python
# -*- coding: utf-8 -*-
"""待办列表悬浮面板。"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QCheckBox, QWidgetItem,
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
```

注意：实现时去掉未使用的 `QWidgetItem` import；`stateChanged` / `editingFinished` 的 lambda 绑定用默认参数捕获 `todo_id`，避免闭包踩坑。

- [ ] **Step 2: Smoke import**

Run: `python -c "from todos import TodoPanel; print('ok')"`  
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add todos.py
git commit -m "$(cat <<'EOF'
feat: 添加待办悬浮面板

支持添加、勾选、编辑、删除与清空已完成。
EOF
)"
```

---

### Task 4: main.py 编排（菜单 / 定位 / 互斥 / 打开链接）

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `BookmarkPanel`, `TodoPanel`, `storage.list_bookmarks`, `webbrowser.open`
- Produces（`EggplantPet` 方法）:
  - `_populate_bookmarks_menu(submenu)`
  - `_open_bookmark_url(url)`
  - `_toggle_bookmark_panel()` / `_toggle_todo_panel()`
  - `_position_panel(panel)` — 锚在茄子下方居中，夹入屏幕
  - `_hide_panels()` — 隐藏 bookmarks/todos 面板
  - `_close_exclusive_ui(except_name=None)` — 关闭聊天输入与另一面板
  - 拖动 / 缩放 / 隐藏 / 退出 / `_refresh_native_topmost` 覆盖面板

- [ ] **Step 1: 增加 import 与实例字段**

在 `main.py` 顶部增加：

```python
import webbrowser
from bookmarks import BookmarkPanel
from todos import TodoPanel
import storage
```

在 `EggplantPet.__init__` 中（`self.chat_input = None` 附近）增加：

```python
self.bookmark_panel = None
self.todo_panel = None
```

- [ ] **Step 2: 实现面板辅助方法**

在 `_hide_chat_input` 附近加入（完整粘贴，勿省略）：

```python
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
        empty = QAction("暂无网址", self)
        empty.setEnabled(False)
        submenu.addAction(empty)
    else:
        for b in bookmarks:
            action = QAction(b["alias"], self)
            action.triggered.connect(
                lambda _=False, u=b["url"]: self._open_bookmark_url(u)
            )
            submenu.addAction(action)
    submenu.addSeparator()
    manage = QAction("管理…", self)
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
```

- [ ] **Step 3: 改 `contextMenuEvent`**

在「聊聊天」之前插入：

```python
bookmarks_menu = menu.addMenu("常用网址")
self._populate_bookmarks_menu(bookmarks_menu)

todo_action = QAction("待办", self)
todo_action.triggered.connect(self._toggle_todo_panel)
menu.addAction(todo_action)

menu.addSeparator()
```

（保留原有聊聊天 / 隐藏 / 置顶 / 退出。）

- [ ] **Step 4: 改互斥与生命周期挂钩**

1. `_open_chat` 开头增加：`self._close_exclusive_ui(keep="chat")`（在 `_hide_bubble` 之后即可；勿再无条件只藏 chat）。
2. `_hide_pet` / `_quit_app`：在关 chat 后调用 `self._hide_panels()`。
3. `mouseMoveEvent` 拖动成功移动后：调用 `self._reposition_open_panels()`（当前拖动时会 `_hide_chat_input()`——**改为**对业务面板跟随而非一律隐藏；聊天输入可继续隐藏或一并跟随，推荐：拖动时 `_reposition_open_panels()`，不再强制 `_hide_chat_input()`，与 spec「拖动跟随」一致）。
4. `_set_scale` 末尾：`self._reposition_open_panels()`。
5. `_refresh_native_topmost`：若面板可见则 `apply_native_topmost(panel, ...)`。

- [ ] **Step 5: 手测清单（本机）**

- 右键「常用网址」空态显示「暂无网址」；管理… 添加后子菜单出现别名；点击打开浏览器
- 「待办」面板在茄子下方；添加/勾选/编辑/删/清空已完成
- 两面板互斥；与聊聊天互斥；Esc 关闭；拖动跟随；隐藏宠物后面板消失

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "$(cat <<'EOF'
feat: 右键菜单接入常用网址与待办面板

编排悬浮面板定位、互斥与浏览器打开，数据走 storage。
EOF
)"
```

---

### Task 5: tray.py 相同入口

**Files:**
- Modify: `tray.py`
- Modify: `main.py`（callbacks 字典）

**Interfaces:**
- Consumes: callbacks `open_bookmarks_menu` 不够——托盘需要动态子菜单。采用：
  - `populate_bookmarks_menu(submenu)` — main 注入，签名接受 `QMenu`
  - `toggle_todo_panel`
  - 或更简单：callbacks 提供 `list_bookmark_entries() -> list[(alias, url)]`、`open_url(url)`、`manage_bookmarks`、`toggle_todos`
- Produces: 托盘菜单含「常用网址」子菜单 +「待办」

- [ ] **Step 1: 扩展 `PetTray.__init__` 菜单构建**

在「聊聊天」前插入（需 `aboutToShow` 以便每次打开刷新书签）：

```python
bookmarks_menu = menu.addMenu("常用网址")
bookmarks_menu.aboutToShow.connect(
    lambda: self._populate_bookmarks(bookmarks_menu)
)

todo_action = QAction("待办", parent)
todo_action.triggered.connect(self._on_todos)
menu.addAction(todo_action)

menu.addSeparator()
```

并实现：

```python
def _populate_bookmarks(self, submenu):
    cb = self.callbacks.get("populate_bookmarks_menu")
    if cb:
        cb(submenu)

def _on_todos(self):
    cb = self.callbacks.get("toggle_todo_panel")
    if cb:
        cb()
```

- [ ] **Step 2: main 注入回调**

```python
self.tray = PetTray(
    self,
    self._get_resource_path("eggplant.png"),
    {
        "show_pet": self._show_pet,
        "hide_pet": self._hide_pet,
        "open_chat": self._open_chat,
        "populate_bookmarks_menu": self._populate_bookmarks_menu,
        "toggle_todo_panel": self._toggle_todo_panel,
        "quit": self._quit_app,
    },
)
```

右键菜单每次 `contextMenuEvent` 已重建，可继续在构建时调用 `_populate_bookmarks_menu`；托盘用 `aboutToShow` 刷新。

- [ ] **Step 3: 手测托盘**

- 托盘「常用网址」与右键一致；「待办」打开同一面板

- [ ] **Step 4: Commit**

```bash
git add tray.py main.py
git commit -m "$(cat <<'EOF'
feat: 托盘菜单同步常用网址与待办入口

与右键菜单共用 populate / toggle 回调，aboutToShow 刷新书签列表。
EOF
)"
```

---

### Task 6: 打包 hidden-import + README

**Files:**
- Modify: `build.bat`
- Modify: `.github/workflows/build-windows.yml`
- Modify: `README.md`

- [ ] **Step 1: 打包脚本增加 hidden-import**

在现有 `--hidden-import tray` 后追加：

```
--hidden-import storage --hidden-import bookmarks --hidden-import todos
```

`build.bat` 与 `build-windows.yml` 两处都改。

- [ ] **Step 2: 更新 README「右键菜单」与使用说明**

补充：

- 常用网址：子菜单按别名打开；管理… 悬浮编辑
- 待办：悬浮在茄子下方；添加/勾选/编辑/删除/清空已完成
- 数据位置：`~/.eggplant_pet/data.json`
- 托盘同样入口

- [ ] **Step 3: 跑 storage 单测回归**

Run: `python -m unittest tests.test_storage tests.test_chat -v`  
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add build.bat .github/workflows/build-windows.yml README.md
git commit -m "$(cat <<'EOF'
docs: 说明常用网址与待办，并更新打包 hidden-import

保证 onefile 打入 storage/bookmarks/todos，文档与功能对齐。
EOF
)"
```

---

## Self-Review (plan vs spec)

| Spec 要求 | Task |
|-----------|------|
| 子菜单别名打开 + 管理… | Task 4, 5 |
| 待办悬浮茄子下方 | Task 3, 4 `_position_panel` |
| 待办：添加/勾选/删/编辑/清空已完成 | Task 3 |
| 网址管理面板 CRUD | Task 2 |
| 右键 + 托盘入口 | Task 4, 5 |
| `~/.eggplant_pet/data.json` | Task 1 |
| 坏文件恢复 / URL https | Task 1 |
| 互斥、Esc、跟随、隐藏关面板 | Task 4 |
| storage 单测 | Task 1 |
| 打包 + README | Task 6 |
| 非目标未写入任务 | 是 |

**Placeholder scan:** 无 TBD；GUI 手测步骤已列出。  
**类型一致性:** `populate_bookmarks_menu(submenu)` / `_toggle_todo_panel` / `_toggle_bookmark_panel` 在 Task 4–5 命名一致。
