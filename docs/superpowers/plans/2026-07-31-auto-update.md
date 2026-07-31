# Windows 应用内自动更新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows 打包版可在启动时与菜单中检查 GitHub Releases 的语义版本，确认后下载 EXE、替换并重启，用户无需再手动打开 GitHub 下载。

**Architecture:** `updater.py` 负责版本读写、Releases API、下载与 `update.bat` 生成；`bubble.ConfirmBubble` 提供「更新 / 稍后」；`main.py` 用 `QTimer` 延迟启动检查并用后台线程跑网络；`tray.py` 增加「检查更新」；CI 按 `VERSION` 发布 `vX.Y.Z`。

**Tech Stack:** Python 3.8+、PyQt5、stdlib（urllib、json、threading、tempfile、subprocess、unittest）；无新第三方依赖。

**Spec:** `docs/superpowers/specs/2026-07-31-auto-update-design.md`

## Global Constraints

- 仅 `sys.platform == "win32"` 且 `getattr(sys, "frozen", False)` 启用完整更新；菜单「检查更新」在未启用时隐藏
- 不做差分包、签名校验、强制更新、「跳过此版本」持久化、更新日志 UI
- 兼容 Python 3.8（避免仅 3.9+ 的运行时语法）
- 仓库固定：`GITHUB_OWNER = "1301604100"`，`GITHUB_REPO = "eggplant"`
- 资产优先 `茄子桌宠.exe`，否则 `EggplantPet-Windows.exe`
- 用户数据 `~/.eggplant_pet/` 不得因更新删除
- GitHub API 请求须带 `User-Agent: eggplant-pet` 与 `Accept: application/vnd.github+json`
- 打包需 `--add-data VERSION;.` 与 `--hidden-import updater`

## File Structure

| 文件 | 动作 | 职责 |
|------|------|------|
| `VERSION` | Create | 单一版本源，初始 `1.0.0` |
| `updater.py` | Create | 版本解析/比较、API、下载、写 bat、启用判断 |
| `tests/test_updater.py` | Create | updater 纯逻辑单测 |
| `bubble.py` | Modify | 新增 `ConfirmBubble`（文案 + 两按钮） |
| `main.py` | Modify | 启动检查、手动检查、下载确认、退出启动 bat |
| `tray.py` | Modify | 「检查更新」菜单项（回调注入） |
| `build.bat` | Modify | VERSION + updater |
| `.github/workflows/build-windows.yml` | Modify | 按 VERSION 发 `vX.Y.Z` Release |
| `README.md` | Modify | 版本发版与自动更新说明 |

---

### Task 1: VERSION + updater 纯逻辑（TDD）

**Files:**
- Create: `VERSION`
- Create: `updater.py`
- Create: `tests/test_updater.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `GITHUB_OWNER = "1301604100"`
  - `GITHUB_REPO = "eggplant"`
  - `ASSET_NAMES = ("茄子桌宠.exe", "EggplantPet-Windows.exe")`
  - `parse_version(text: str) -> tuple` — 接受 `"1.2.0"` / `"v1.2.0"`，返回 `(1, 2, 0)`；非法抛 `ValueError`
  - `compare_versions(a: tuple, b: tuple) -> int` — `<0` / `0` / `>0`
  - `should_enable_updater(platform=None, frozen=None) -> bool` — 默认读 `sys.platform` 与 `getattr(sys, "frozen", False)`
  - `read_local_version(resource_reader=None) -> str` — 读 VERSION 文件内容 strip；失败返回 `"0.0.0"`。`resource_reader` 为可调用 `() -> str`，测时可注入；默认实现见 Step 3
  - `pick_latest_release(releases: list) -> dict | None` — 从 GitHub releases JSON 列表选出最新非 draft/prerelease；返回 `{"version": "1.2.0", "tag": "v1.2.0", "download_url": "...", "size": int|None}` 或 `None`
  - （本任务尚未实现网络下载函数；Task 2）

- [ ] **Step 1: 写 VERSION 与失败单测**

创建 `VERSION`（单行，无多余空行）：

```text
1.0.0
```

创建 `tests/test_updater.py`：

```python
# -*- coding: utf-8 -*-
import unittest

import updater


SAMPLE_RELEASES = [
    {
        "tag_name": "v1.0.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "EggplantPet-Windows.exe",
                "browser_download_url": "https://example.com/old.exe",
                "size": 100,
            }
        ],
    },
    {
        "tag_name": "v1.2.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "茄子桌宠.exe",
                "browser_download_url": "https://example.com/new.exe",
                "size": 200,
            }
        ],
    },
    {
        "tag_name": "v2.0.0-beta",
        "draft": False,
        "prerelease": True,
        "assets": [
            {
                "name": "茄子桌宠.exe",
                "browser_download_url": "https://example.com/beta.exe",
                "size": 300,
            }
        ],
    },
    {
        "tag_name": "not-a-version",
        "draft": False,
        "prerelease": False,
        "assets": [],
    },
]


class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version("v1.2.0"), (1, 2, 0))
        self.assertEqual(updater.parse_version(" 1.0.0\n"), (1, 0, 0))
        with self.assertRaises(ValueError):
            updater.parse_version("abc")
        with self.assertRaises(ValueError):
            updater.parse_version("1.2")

    def test_compare_versions(self):
        self.assertLess(updater.compare_versions((1, 0, 0), (1, 0, 1)), 0)
        self.assertEqual(updater.compare_versions((1, 2, 0), (1, 2, 0)), 0)
        self.assertGreater(updater.compare_versions((2, 0, 0), (1, 9, 9)), 0)

    def test_should_enable_updater(self):
        self.assertTrue(updater.should_enable_updater(platform="win32", frozen=True))
        self.assertFalse(updater.should_enable_updater(platform="win32", frozen=False))
        self.assertFalse(updater.should_enable_updater(platform="darwin", frozen=True))

    def test_read_local_version_fallback(self):
        self.assertEqual(updater.read_local_version(resource_reader=lambda: (_ for _ in ()).throw(OSError())), "0.0.0")
        self.assertEqual(updater.read_local_version(resource_reader=lambda: "1.3.0\n"), "1.3.0")

    def test_pick_latest_release(self):
        picked = updater.pick_latest_release(SAMPLE_RELEASES)
        self.assertIsNotNone(picked)
        self.assertEqual(picked["version"], "1.2.0")
        self.assertEqual(picked["tag"], "v1.2.0")
        self.assertEqual(picked["download_url"], "https://example.com/new.exe")
        self.assertEqual(picked["size"], 200)

    def test_pick_latest_prefers_chinese_asset_name(self):
        releases = [
            {
                "tag_name": "v1.0.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "EggplantPet-Windows.exe",
                        "browser_download_url": "https://example.com/en.exe",
                        "size": 1,
                    },
                    {
                        "name": "茄子桌宠.exe",
                        "browser_download_url": "https://example.com/zh.exe",
                        "size": 2,
                    },
                ],
            }
        ]
        picked = updater.pick_latest_release(releases)
        self.assertEqual(picked["download_url"], "https://example.com/zh.exe")

    def test_pick_latest_none_when_empty(self):
        self.assertIsNone(updater.pick_latest_release([]))
        self.assertIsNone(
            updater.pick_latest_release(
                [{"tag_name": "v1.0.0", "draft": True, "prerelease": False, "assets": []}]
            )
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测确认失败**

Run: `python -m unittest tests.test_updater -v`

Expected: FAIL（`ModuleNotFoundError: No module named 'updater'` 或导入失败）

- [ ] **Step 3: 实现 `updater.py`（本任务范围）**

```python
# -*- coding: utf-8 -*-
"""应用内自动更新：版本比较与 GitHub Releases 选择。"""

from __future__ import print_function

import os
import re
import sys

GITHUB_OWNER = "1301604100"
GITHUB_REPO = "eggplant"
ASSET_NAMES = ("茄子桌宠.exe", "EggplantPet-Windows.exe")

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text):
    if text is None:
        raise ValueError("empty version")
    m = _VERSION_RE.match(str(text).strip())
    if not m:
        raise ValueError("invalid version: %r" % (text,))
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def compare_versions(a, b):
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def should_enable_updater(platform=None, frozen=None):
    if platform is None:
        platform = sys.platform
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return platform == "win32" and frozen


def _default_version_reader():
    if hasattr(sys, "_MEIPASS"):
        path = os.path.join(sys._MEIPASS, "VERSION")
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_local_version(resource_reader=None):
    reader = resource_reader or _default_version_reader
    try:
        ver = str(reader()).strip()
        t = parse_version(ver)
        return "%d.%d.%d" % t
    except Exception:
        return "0.0.0"


def _asset_for_release(release):
    assets = release.get("assets") or []
    by_name = {a.get("name"): a for a in assets if isinstance(a, dict)}
    for name in ASSET_NAMES:
        if name in by_name:
            a = by_name[name]
            url = a.get("browser_download_url")
            if url:
                size = a.get("size")
                try:
                    size = int(size) if size is not None else None
                except (TypeError, ValueError):
                    size = None
                return url, size
    return None, None


def pick_latest_release(releases):
    best = None
    best_tuple = None
    for rel in releases or []:
        if not isinstance(rel, dict):
            continue
        if rel.get("draft") or rel.get("prerelease"):
            continue
        tag = rel.get("tag_name") or ""
        try:
            ver_tuple = parse_version(tag)
        except ValueError:
            continue
        url, size = _asset_for_release(rel)
        if not url:
            continue
        if best_tuple is None or compare_versions(ver_tuple, best_tuple) > 0:
            best_tuple = ver_tuple
            best = {
                "version": "%d.%d.%d" % ver_tuple,
                "tag": tag if str(tag).startswith("v") else "v%s" % ("%d.%d.%d" % ver_tuple),
                "download_url": url,
                "size": size,
            }
    return best
```

- [ ] **Step 4: 跑测确认通过**

Run: `python -m unittest tests.test_updater -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add VERSION updater.py tests/test_updater.py
git commit -m "$(cat <<'EOF'
feat: 添加版本解析与 GitHub Release 选择逻辑

为 Windows 自动更新提供 semver 比较与资产挑选的纯逻辑基础。

EOF
)"
```

---

### Task 2: 检查更新 / 下载 / 写替换脚本

**Files:**
- Modify: `updater.py`
- Modify: `tests/test_updater.py`

**Interfaces:**
- Consumes: Task 1 全部 API
- Produces:
  - `fetch_latest_release(urlopen=None, timeout=15) -> dict | None` — 请求 `https://api.github.com/repos/{owner}/{repo}/releases`，解析 JSON 后 `pick_latest_release`；失败抛异常或返回由调用方处理——**约定：网络/HTTP/JSON 错误抛异常**（`URLError`/`HTTPError`/`ValueError`），无可用 release 返回 `None`
  - `check_for_update(local_version=None, urlopen=None) -> dict | None` — 返回有更新时的 release dict（含 version/download_url/size），已最新或无法比较返回 `None`；`local_version` 默认 `read_local_version()`
  - `download_update(url, dest_path, expected_size=None, urlopen=None, progress_callback=None) -> None` — 下载到 `dest_path`；若 `expected_size` 非 None 且最终大小不符则删文件并抛 `ValueError`；`progress_callback(received: int, total: int|None)` 可选
  - `write_update_script(current_exe, new_exe, pid, script_path) -> str` — 写 bat，返回 `script_path`
  - `build_update_bat_content(current_exe, new_exe, pid) -> str` — 纯函数便于单测（bat 正文）
  - `launch_update_and_exit(script_path, quit_callback) -> None` — `subprocess.Popen` 启动 bat（`creationflags` 在 win32 用 `CREATE_NEW_CONSOLE` 或 `DETACHED_PROCESS` 之一，隐藏窗口可用 `CREATE_NO_WINDOW=0x08000000`），然后调用 `quit_callback()`

- [ ] **Step 1: 追加失败单测**

在 `tests/test_updater.py` 追加：

```python
import io
import json
import tempfile
from pathlib import Path
from unittest import mock


class FakeResponse(object):
    def __init__(self, payload, headers=None):
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, bytes):
            data = payload
        else:
            data = str(payload).encode("utf-8")
        self._buf = io.BytesIO(data)
        self.headers = headers or {}

    def read(self, n=-1):
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestUpdaterNetwork(unittest.TestCase):
    def test_check_for_update_finds_newer(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(SAMPLE_RELEASES)

        result = updater.check_for_update(local_version="1.0.0", urlopen=fake_urlopen)
        self.assertEqual(result["version"], "1.2.0")

    def test_check_for_update_none_when_current(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(SAMPLE_RELEASES)

        self.assertIsNone(
            updater.check_for_update(local_version="1.2.0", urlopen=fake_urlopen)
        )

    def test_download_update_writes_file(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(b"MZ-fake-exe", headers={"Content-Length": "11"})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "app.exe"
        updater.download_update(
            "https://example.com/a.exe",
            str(dest),
            expected_size=11,
            urlopen=fake_urlopen,
        )
        self.assertEqual(dest.read_bytes(), b"MZ-fake-exe")

    def test_download_update_rejects_bad_size(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(b"short")

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "app.exe"
        with self.assertRaises(ValueError):
            updater.download_update(
                "https://example.com/a.exe",
                str(dest),
                expected_size=100,
                urlopen=fake_urlopen,
            )
        self.assertFalse(dest.exists())

    def test_build_update_bat_content_contains_paths_and_pid(self):
        content = updater.build_update_bat_content(
            r"C:\Apps\茄子桌宠.exe",
            r"C:\Temp\new.exe",
            4242,
        )
        self.assertIn("4242", content)
        self.assertIn("茄子桌宠.exe", content)
        self.assertIn("new.exe", content)
        self.assertIn("start", content.lower())
```

- [ ] **Step 2: 跑测确认新用例失败**

Run: `python -m unittest tests.test_updater.TestUpdaterNetwork -v`

Expected: FAIL（缺 `check_for_update` 等属性）

- [ ] **Step 3: 在 `updater.py` 实现网络与脚本函数**

追加（保留 Task 1 已有内容）：

```python
import json
import subprocess
import tempfile
import urllib.error
import urllib.request


RELEASES_URL = "https://api.github.com/repos/%s/%s/releases" % (
    GITHUB_OWNER,
    GITHUB_REPO,
)


def _default_urlopen(req, timeout=15):
    return urllib.request.urlopen(req, timeout=timeout)


def _github_request(url):
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": "eggplant-pet",
            "Accept": "application/vnd.github+json",
        },
    )


def fetch_latest_release(urlopen=None, timeout=15):
    opener = urlopen or _default_urlopen
    req = _github_request(RELEASES_URL)
    with opener(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("unexpected releases payload")
    return pick_latest_release(data)


def check_for_update(local_version=None, urlopen=None):
    local = local_version if local_version is not None else read_local_version()
    local_t = parse_version(local)
    latest = fetch_latest_release(urlopen=urlopen)
    if not latest:
        return None
    if compare_versions(parse_version(latest["version"]), local_t) > 0:
        return latest
    return None


def download_update(url, dest_path, expected_size=None, urlopen=None, progress_callback=None):
    opener = urlopen or _default_urlopen
    req = _github_request(url)
    # browser_download_url 也带 UA
    received = 0
    try:
        with opener(req, timeout=60) as resp:
            total = expected_size
            if total is None:
                cl = None
                try:
                    cl = resp.headers.get("Content-Length")
                except Exception:
                    cl = None
                if cl:
                    try:
                        total = int(cl)
                    except ValueError:
                        total = None
            tmp_path = dest_path + ".part"
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, total)
            if expected_size is not None and received != int(expected_size):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise ValueError(
                    "download size mismatch: got %s expected %s"
                    % (received, expected_size)
                )
            if received <= 0:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise ValueError("empty download")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
    except Exception:
        # 清理不完整文件
        for p in (dest_path, dest_path + ".part"):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise


def build_update_bat_content(current_exe, new_exe, pid):
    # 使用短循环等待 PID 退出，再 copy /Y 覆盖并 start "" 启动
    lines = [
        "@echo off",
        "setlocal",
        "set PID=%d" % int(pid),
        "set NEW=%s" % new_exe,
        "set CUR=%s" % current_exe,
        ":wait",
        "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul",
        "if not errorlevel 1 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait",
        ")",
        "copy /Y \"%NEW%\" \"%CUR%\" >nul",
        "if errorlevel 1 (",
        "  echo Update failed. New file kept at:",
        "  echo %NEW%",
        "  pause",
        "  exit /b 1",
        ")",
        "start \"\" \"%CUR%\"",
        "del \"%NEW%\" >nul 2>&1",
        "endlocal",
    ]
    return "\r\n".join(lines) + "\r\n"


def write_update_script(current_exe, new_exe, pid, script_path):
    content = build_update_bat_content(current_exe, new_exe, pid)
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(content)
    return script_path


def launch_update_and_exit(script_path, quit_callback):
    kwargs = {}
    if sys.platform == "win32":
        # 0x00000008 DETACHED_PROCESS | 0x08000000 CREATE_NO_WINDOW
        kwargs["creationflags"] = 0x00000008
        kwargs["close_fds"] = True
    subprocess.Popen(["cmd.exe", "/c", script_path], **kwargs)
    if quit_callback:
        quit_callback()
```

`build_update_bat_content` 里路径若含 `&` 等特殊字符，实现时用传入的绝对路径原样写入双引号；单测路径不含危险字符即可。

- [ ] **Step 4: 跑全量 updater 测试**

Run: `python -m unittest tests.test_updater -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add updater.py tests/test_updater.py
git commit -m "$(cat <<'EOF'
feat: 实现检查更新、下载与 Windows 替换脚本

完成从 GitHub Releases 拉取、落盘校验到写 bat 替换重启的链路。

EOF
)"
```

---

### Task 3: ConfirmBubble + main/tray 接入

**Files:**
- Modify: `bubble.py` — 新增 `ConfirmBubble`
- Modify: `main.py` — 启动检查、手动检查、下载与退出
- Modify: `tray.py` — 「检查更新」入口

**Interfaces:**
- Consumes:
  - `updater.should_enable_updater`
  - `updater.read_local_version`
  - `updater.check_for_update`
  - `updater.download_update`
  - `updater.write_update_script`
  - `updater.launch_update_and_exit`
- Produces（`main.py` 行为，非导出 API）：
  - 启动约 3s 后若启用则后台 `check_for_update`；有更新且本会话未「稍后」则弹出确认
  - `_check_for_updates(manual: bool)`：手动时已最新/失败有气泡文案
  - 托盘/右键在启用时显示「检查更新」

- [ ] **Step 1: 在 `bubble.py` 增加 `ConfirmBubble`**

在文件末尾追加（风格对齐 `ChatInputBubble`，按钮用中性色避免强品牌紫依赖；「更新」主按钮、「稍后」次按钮）：

先把 `bubble.py` 顶部导入改为包含 `QLabel, QVBoxLayout`：

```python
from PyQt5.QtWidgets import (
    QWidget, QLineEdit, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QGraphicsDropShadowEffect,
)
```

在文件末尾追加：

```python
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
```

- [ ] **Step 2: 改 `tray.py`**

- 类 docstring 的 callbacks 增加 `check_for_updates`。
- 在「聊聊天」与「退出」之间（或退出前分隔线处）插入：

```python
        check_update_cb = self.callbacks.get("check_for_updates")
        if check_update_cb:
            menu.addSeparator()
            update_action = QAction("检查更新", parent)
            update_action.triggered.connect(check_update_cb)
            menu.addAction(update_action)
```

仅当 callback 存在时显示（main 只在 `should_enable_updater()` 时注入）。

- [ ] **Step 3: 改 `main.py`**

1. Import：

```python
import threading
import tempfile
from bubble import SpeechBubble, ChatInputBubble, ConfirmBubble
import updater
```

2. 在 `EggplantPet.__init__` 末尾（托盘创建之后）初始化：

```python
        self._update_prompt = None
        self._update_snoozed = False
        self._update_busy = False
        if updater.should_enable_updater():
            QTimer.singleShot(3000, lambda: self._check_for_updates(manual=False))
```

3. 创建托盘时 callbacks 增加（仅启用时）：

```python
            callbacks = {
                "show_pet": self._show_pet,
                "hide_pet": self._hide_pet,
                "open_chat": self._open_chat_input,
                "populate_bookmarks_menu": self._populate_bookmarks_menu,
                "toggle_todo_panel": self._toggle_todo_panel,
                "quit": self._quit_app,
            }
            if updater.should_enable_updater():
                callbacks["check_for_updates"] = lambda: self._check_for_updates(manual=True)
```

（按现有 callbacks 字典实际字段合并，不要删掉已有 key。）

4. 右键菜单：在「退出」前，若 `updater.should_enable_updater()`：

```python
        if updater.should_enable_updater():
            menu.addSeparator()
            update_action = QAction("检查更新", self)
            update_action.triggered.connect(lambda: self._check_for_updates(manual=True))
            menu.addAction(update_action)
```

5. 实现方法（放在类内合适位置）：

```python
    def _check_for_updates(self, manual=False):
        if not updater.should_enable_updater():
            return
        if self._update_busy:
            return
        if (not manual) and self._update_snoozed:
            return

        def worker():
            err = None
            result = None
            try:
                result = updater.check_for_update()
            except Exception as exc:
                err = exc
            def done():
                self._on_update_check_done(result, err, manual=manual)
            QTimer.singleShot(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_check_done(self, result, err, manual=False):
        if err is not None:
            if manual:
                self._show_bubble("检查失败，请稍后重试", duration_ms=3000)
            return
        if result is None:
            if manual:
                local = updater.read_local_version()
                self._show_bubble("已是最新版本 %s" % local, duration_ms=3000)
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
        # 定位：复用 _show_bubble 的坐标夹取逻辑（复制 x/y 计算）
        w = self._update_prompt
        bubble_x = self.x() + self.width() // 2 - w.width() // 2
        bubble_y = self.y() - w.height() - 5
        screen = QApplication.primaryScreen().availableGeometry()
        if bubble_x < 10:
            bubble_x = 10
        if bubble_x + w.width() > screen.width() - 10:
            bubble_x = screen.width() - w.width() - 10
        if bubble_y < 10:
            bubble_y = self.y() + self.height() + 5
        w.move(bubble_x, bubble_y)
        w.show()
        apply_native_topmost(w, self.is_stay_on_top)

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
            dest = None
            script = None
            try:
                tmpdir = os.path.join(tempfile.gettempdir(), "eggplant_pet_update")
                os.makedirs(tmpdir, exist_ok=True)
                dest = os.path.join(tmpdir, "EggplantPet-Windows-%s.exe" % release["version"])
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

            def done():
                self._on_download_done(err, script)

            QTimer.singleShot(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_done(self, err, script_path):
        self._update_busy = False
        if err is not None:
            self._show_bubble("下载失败", duration_ms=3000)
            return
        self._show_bubble("正在更新，即将重启…", duration_ms=2000)
        updater.launch_update_and_exit(script_path, self._quit_app)
```

6. 在 `_hide_bubble` / `_quit_app` / `closeEvent` 路径中调用 `_hide_update_prompt()`，避免残留窗口。

7. 拖动/缩放时若需要，可对 `_update_prompt` 做与气泡类似的重定位；最低要求：显示时位置正确即可（YAGNI：可不跟随拖动）。

- [ ] **Step 4: 语法与单测回归**

Run:

```bash
python -m py_compile main.py tray.py bubble.py updater.py
python -m unittest tests.test_updater tests.test_chat tests.test_storage -v
```

Expected: PASS（若本机无 `test_storage` 则跳过该模块）

- [ ] **Step 5: Commit**

```bash
git add bubble.py main.py tray.py
git commit -m "$(cat <<'EOF'
feat: 接入启动与菜单检查更新 UI

Windows 打包版可确认后下载并重启完成更新。

EOF
)"
```

---

### Task 4: 打包、CI 发版与 README

**Files:**
- Modify: `build.bat`
- Modify: `.github/workflows/build-windows.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: 根目录 `VERSION`；`updater` 模块
- Produces: Release tag `v{VERSION}`；EXE 内含 `VERSION`

- [ ] **Step 1: 改 `build.bat` 的 pyinstaller 行**

在现有 `--add-data` / `--hidden-import` 基础上增加：

```bat
pyinstaller --onefile --windowed --name "茄子桌宠" --icon=eggplant.ico --add-data "eggplant.png;." --add-data "eggplant.ico;." --add-data "VERSION;." --hidden-import bubble --hidden-import chat --hidden-import tray --hidden-import storage --hidden-import bookmarks --hidden-import todos --hidden-import updater main.py
```

（若当前仓库 `build.bat` 尚无 storage/bookmarks/todos，以**现有行为 + VERSION + updater**为准，不要臆造缺失模块；有则保留。）

- [ ] **Step 2: 改 `.github/workflows/build-windows.yml`**

在 Checkout 后增加读版本：

```yaml
      - name: Read VERSION
        id: version
        shell: pwsh
        run: |
          $v = (Get-Content -Raw VERSION).Trim()
          if (-not $v) { throw "VERSION is empty" }
          echo "value=$v" >> $env:GITHUB_OUTPUT
          echo "tag=v$v" >> $env:GITHUB_OUTPUT
```

Build EXE 命令与 `build.bat` 对齐（含 `--add-data VERSION;.` 与 `--hidden-import updater`）。

Publish 步骤改为：

```yaml
      - name: Publish GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ steps.version.outputs.tag }}
          name: 茄子桌宠 ${{ steps.version.outputs.tag }}
          body: |
            ## 下载说明
            下载下方附件即可运行（无需安装 Python）：
            - `茄子桌宠.exe`（中文文件名）
            - `EggplantPet-Windows.exe`（英文文件名，部分环境下载更稳）

            - Version: `${{ steps.version.outputs.value }}`
            - Commit: `${{ github.sha }}`
            - Workflow run: #${{ github.run_number }}
          files: |
            dist/茄子桌宠.exe
            dist/EggplantPet-Windows.exe
          fail_on_unmatched_files: true
          make_latest: true
          overwrite_files: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

说明：同一 `VERSION` 重复推送会覆盖同 tag 资产；发新版须先改 `VERSION`。

- [ ] **Step 3: 更新 `README.md`**

在「方式二：GitHub Releases」中补充：

- 发布按 `VERSION` 生成 tag（如 `v1.0.0`）
- Windows 安装版支持启动检查与菜单「检查更新」，确认后自动下载替换
- 发新版流程：改根目录 `VERSION` → 推送 `main`（或手动 Run workflow）

- [ ] **Step 4: 校验 workflow YAML 与本地编译**

Run:

```bash
python -m py_compile updater.py main.py tray.py bubble.py
python -m unittest tests.test_updater -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add build.bat .github/workflows/build-windows.yml README.md VERSION
git commit -m "$(cat <<'EOF'
ci: 按 VERSION 发布 Release 并打包自动更新支持

发版 tag 与客户端 semver 对齐，打包纳入 VERSION 与 updater。

EOF
)"
```

---

## Manual Verification（Task 3–4 之后）

在 Windows 上：

1. 将本地 `VERSION` 设为低于已发布的最高 tag，打包运行 → 约 3 秒后出现确认气泡 → 「更新」→ 重启后版本升高。
2. 点「稍后」→ 同会话不再自动弹；菜单「检查更新」仍可再出。
3. VERSION 已最新 → 菜单提示「已是最新版本 …」。
4. 断网 → 菜单提示「检查失败，请稍后重试」；启动检查无打扰。

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| 启动静默检查 + 菜单检查更新 | Task 3 |
| 语义版本 VERSION + vX.Y.Z | Task 1, 4 |
| 下载 EXE + bat 替换重启 | Task 2, 3 |
| 仅 Windows frozen | Task 1 `should_enable_updater`, Task 3 隐藏菜单 |
| 「稍后」仅本会话 | Task 3 `_update_snoozed` |
| CI 发版改 tag | Task 4 |
| 用户数据保留 | 不触碰 `~/.eggplant_pet/`（全任务） |
| 单测 parse/compare/pick/enable | Task 1–2 |
| 错误提示文案 | Task 3 |

## Placeholder / Consistency Review

- 无 TBD；接口名在 Task 间一致：`check_for_update` / `download_update` / `write_update_script` / `launch_update_and_exit`。
- `ConfirmBubble` 的 cancel 实现以 Step 说明为准，不含死代码。
- `build.bat` hidden-import 以仓库当时已有模块为准，仅强制新增 `VERSION` 与 `updater`。
