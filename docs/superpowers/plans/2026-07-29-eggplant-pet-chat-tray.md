# 茄子桌宠：本地对话 + 系统托盘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为茄子桌宠增加本地剧本对话、聊天气泡输入、系统托盘（显示/隐藏/退出），模块拆分为 `chat.py` / `bubble.py` / `tray.py`。

**Architecture:** `main.py` 保留主窗口与动画；说话/输入气泡抽到 `bubble.py`；`chat.reply` 纯逻辑；`PetTray` 注入回调。交互：短点仍随机气泡；右键/托盘「聊聊天」走输入框。

**Tech Stack:** Python 3.8+、PyQt5、stdlib unittest；无新第三方依赖。

**Spec:** `docs/superpowers/specs/2026-07-29-eggplant-pet-chat-tray-design.md`

## Global Constraints

- 不做 MaiBot / API / Live2D / 截图
- 打包仍 `--onefile` + `eggplant.png`；必要时 `--hidden-import`
- 退出必须 `tray.hide()` + `QApplication.quit()`
- 置顶气泡调用 `apply_native_topmost`（仍在 `main.py`）

---

### Task 1: chat.py + 单测

**Files:**
- Create: `chat.py`
- Create: `tests/test_chat.py`

**Produces:** `reply(user_text: str) -> str`

- [x] 实现关键词表与 `reply`
- [x] 写测试：打招呼命中、空串、默认回复非空
- [x] `python -m unittest tests.test_chat -v` 通过

### Task 2: bubble.py

**Files:**
- Create: `bubble.py`
- Modify: `main.py`（改用 SpeechBubble）

**Produces:** `SpeechBubble`, `ChatInputBubble(on_send=callable)`

- [x] 迁移原 `BubbleWidget` 为 `SpeechBubble`
- [x] 新增 `ChatInputBubble`（输入+发送、Esc、focus_input）
- [x] main 短点气泡改用 SpeechBubble，行为不变

### Task 3: tray.py + 隐藏/显示

**Files:**
- Create: `tray.py`
- Modify: `main.py`

**Produces:** `PetTray(parent, icon_path, callbacks)`

- [x] 托盘菜单：显示/隐藏/聊聊天/退出；双击显示
- [x] main：`_hide_pet` / `_show_pet`；隐藏时关气泡
- [x] 退出路径清理托盘

### Task 4: 聊聊天接线

**Files:**
- Modify: `main.py`

- [x] 右键「聊聊天」「隐藏」
- [x] `_open_chat` 显示 ChatInputBubble；发送后 `chat.reply` + SpeechBubble（约 3.5s）
- [x] `_refresh_native_topmost` 覆盖输入气泡

### Task 5: 打包与 README

**Files:**
- Modify: `.github/workflows/build-windows.yml`
- Modify: `build.bat`
- Modify: `README.md`

- [x] hidden-import：`bubble`,`chat`,`tray`
- [x] README 补充聊聊天与托盘说明
- [ ] 手测清单对照 spec §6（请本机验证）
