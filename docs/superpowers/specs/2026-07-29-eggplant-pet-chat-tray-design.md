# 茄子桌宠：本地对话 + 系统托盘 设计规格

**日期：** 2026-07-29  
**状态：** 待用户审阅  
**参考：** [MaiM-desktop-pet](https://github.com/Mai-with-u/MaiM-desktop-pet)（交互形态，非后端架构）  
**范围：** 实时对话（本地剧本）、系统托盘、气泡对话框增强  

---

## 1. 目标与非目标

### 目标

- 右键 / 托盘「聊聊天」：输入文字，本地规则回复，气泡展示。
- 系统托盘：显示 / 隐藏宠物、聊聊天、退出；双击托盘显示并置前。
- 保留现有：短点动画 + 随机气泡、拖拽、滚轮缩放、置顶、彻底退出。

### 非目标（本次不做）

- MaiBot / WebSocket 后端  
- 大模型 API  
- Live2D、截图  

---

## 2. 架构与模块

采用轻量模块拆分（方案 B），入口仍为 `main.py`。

```
eggplant_pet/
├── main.py       # EggplantPet：窗口、动画、右键菜单；编排 bubble/chat/tray
├── bubble.py     # SpeechBubble（说话）+ ChatInputBubble（输入）
├── chat.py       # reply(user_text) -> str，关键词剧本
├── tray.py       # QSystemTrayIcon 封装
├── eggplant.png
├── requirements.txt
└── .github/workflows/build-windows.yml
```

| 模块 | 职责 | 依赖 |
|------|------|------|
| `main.py` | 主窗口与生命周期 | bubble, chat, tray |
| `bubble.py` | UI 气泡组件 | PyQt5；置顶辅助可复用 main 中函数或抽到共用工具 |
| `chat.py` | 纯逻辑回复，无 UI | 标准库 |
| `tray.py` | 托盘图标与菜单回调 | PyQt5；回调由 main 注入 |

**接口约定：**

```python
# chat.py
def reply(user_text: str) -> str: ...

# tray.py
class PetTray:
    def __init__(self, parent, icon_path, callbacks: dict): ...
    def show(self): ...
    def hide(self): ...

# bubble.py
class SpeechBubble(QWidget):
    def __init__(self, text, parent=None): ...

class ChatInputBubble(QWidget):
    def __init__(self, parent=None, on_send=None): ...
    def focus_input(self): ...
```

`callbacks` 至少包含：`show_pet`, `hide_pet`, `open_chat`, `quit`。

---

## 3. 交互流程

### 3.1 左键短点

- 行为不变：轮播动画 + 随机 `SpeechBubble`。
- 不打开输入框。

### 3.2 右键菜单

现有项保留：调整大小、置顶开关、退出。  
新增：

| 菜单项 | 行为 |
|--------|------|
| 聊聊天 | 打开 `ChatInputBubble`，聚焦输入 |
| 隐藏 | 隐藏主窗口；关闭说话/输入气泡；进程保留，托盘仍可见 |

### 3.3 聊聊天

1. 显示输入气泡（优先角色上方，空间不足则下方），跟随置顶。  
2. 用户输入 → 回车或「发送」。  
3. 空串忽略；非空则隐藏输入框，`chat.reply(text)`，`SpeechBubble` 展示回复（停留约 3–4 秒）。  
4. Esc 关闭输入框。  

### 3.4 系统托盘

- 图标：`eggplant.png`；提示文案如「茄子桌宠」。  
- 菜单：显示宠物 / 隐藏宠物 / 聊聊天 / 退出。  
- 双击：显示宠物并 `raise_` + 刷新原生置顶。  
- 退出：关气泡 → `tray.hide()` → `QApplication.quit()`。  

### 3.5 置顶

说话气泡与输入气泡在 `show` 后调用现有 `apply_native_topmost`，与主窗口 `is_stay_on_top` 一致。

---

## 4. 本地剧本（`chat.py`）

- 匹配：子串关键词，大小写不敏感。  
- 命中：从该组回复中 `random.choice`。  
- 未命中：默认闲聊短句列表随机。  
- 空输入：调用方不发送。

初始关键词组（实现时可微调文案，结构不变）：

| 关键词 | 回复方向 |
|--------|----------|
| 你好、嗨、hello、hi | 打招呼 |
| 名字、你是谁 | 自我介绍（茄子桌宠） |
| 吃、饿 | 吃相关玩笑 |
| 累、困 | 安慰休息 |
| 加油、工作 | 打气 |
| 可爱 | 害羞/得意 |
| 再见、拜拜 | 告别 |

---

## 5. 打包与兼容

- 依赖不变：`PyQt5`、`pyinstaller`（开发打包用）。  
- GitHub Actions / `build.bat`：入口 `main.py`，`--add-data eggplant.png`。  
- 确保 `bubble` / `chat` / `tray` 被打进 onefile（同目录 import 通常自动收集；若 CI 失败再补 `--hidden-import`）。  
- 托盘不可用：跳过托盘初始化，右键「隐藏」可改为仅 `hide()` 并在下次启动或需文档说明用托盘恢复；优先保证「退出」可用。  
- 隐藏时一并关闭气泡，避免幽灵窗口。  

---

## 6. 测试要点（手测）

1. 短点：动画 + 随机气泡仍正常。  
2. 右键「聊聊天」：可输入、回车回复、气泡显示。  
3. 关键词「你好」命中；无关句走默认回复。  
4. 托盘隐藏后桌宠消失，显示后恢复；双击托盘恢复。  
5. 托盘/菜单退出后进程与托盘图标均消失（macOS 程序坞 / Windows 托盘）。  
6. 置顶开/关时，气泡层级与主窗口一致。  

---

## 7. 实现顺序建议

1. `chat.py`（可单测 `reply`）  
2. `bubble.py`（从 `main` 抽出 SpeechBubble + 新增 ChatInputBubble）  
3. `tray.py` + `main` 接入隐藏/显示/退出  
4. `main` 接「聊聊天」与回复展示  
5. 更新 README；必要时微调 Actions hidden-import  

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-29 | 初稿；用户确认方案 B、交互选项 3、本地剧本 A |
