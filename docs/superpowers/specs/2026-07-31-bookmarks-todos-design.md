# 茄子桌宠：常用网址 + 待办列表 设计规格

**日期：** 2026-07-31  
**状态：** 待用户审阅  
**范围：** 右键/托盘常用网址（含别名）、悬浮待办面板、本地 JSON 持久化  

---

## 1. 目标与非目标

### 目标

- **常用网址**：右键/托盘子菜单按别名快速打开；「管理…」打开悬浮管理面板，支持添加/编辑/删除（别名 + URL）。
- **待办**：右键/托盘「待办」打开悬浮列表面板（锚在茄子下方），支持添加、勾选完成/取消、删除、编辑文案、清空已完成。
- 数据本地持久化，重启后保留。
- 入口同时出现在茄子右键菜单与系统托盘菜单。

### 非目标（本次不做）

- 云同步 / 多设备
- 分类、标签、优先级、截止日期
- 导入导出
- 完整 GUI 自动化测试

---

## 2. 架构与模块

采用独立模块 + 本地 JSON + 复用气泡式悬浮窗（方案 1）。

```
eggplant_pet/
├── main.py          # 菜单入口、面板定位/跟随、打开浏览器、编排
├── tray.py          # 托盘菜单增加「常用网址」「待办」入口
├── storage.py       # 用户目录 JSON 读写；bookmarks / todos CRUD
├── bookmarks.py     # 网址管理悬浮面板
├── todos.py         # 待办悬浮面板
├── bubble.py        # 现有聊天气泡（样式/置顶模式可参考）
└── ...
```

| 模块 | 职责 | 依赖 |
|------|------|------|
| `storage.py` | 持久化与纯逻辑 CRUD | 标准库（json、pathlib、uuid） |
| `bookmarks.py` | 网址管理 UI | PyQt5；读写经 storage |
| `todos.py` | 待办 UI | PyQt5；读写经 storage |
| `main.py` | 菜单元件、定位、跟随、互斥、`webbrowser.open` | storage, bookmarks, todos, tray |
| `tray.py` | 托盘菜单与回调注入 | PyQt5；回调由 main 注入 |

**接口约定（示意）：**

```python
# storage.py
def data_path() -> Path: ...
def load() -> dict: ...
def save(data: dict) -> None: ...

def list_bookmarks() -> list[dict]: ...
def add_bookmark(alias: str, url: str) -> dict: ...
def update_bookmark(id: str, alias: str, url: str) -> dict: ...
def delete_bookmark(id: str) -> None: ...
def normalize_url(url: str) -> str: ...  # 无协议时补 https://

def list_todos() -> list[dict]: ...
def add_todo(text: str) -> dict: ...
def update_todo(id: str, *, text=None, done=None) -> dict: ...
def delete_todo(id: str) -> None: ...
def clear_completed_todos() -> int: ...
```

---

## 3. 数据模型

**路径：** `~/.eggplant_pet/data.json`（跨平台用户主目录下）。

**结构：**

```json
{
  "bookmarks": [
    { "id": "uuid", "alias": "GitHub", "url": "https://github.com" }
  ],
  "todos": [
    { "id": "uuid", "text": "写周报", "done": false, "created_at": "ISO8601" }
  ]
}
```

**规则：**

- 别名、待办文案必须非空。
- URL 非空；写入前经 `normalize_url`（无 `http://` / `https://` 时补 `https://`）。
- 「清空已完成」仅删除 `done: true` 的待办。
- 文件缺失或 JSON 损坏：视为空数据，写回合法默认结构 `{"bookmarks":[],"todos":[]}`。

---

## 4. 菜单交互

### 右键菜单与托盘菜单（相同能力）

**常用网址（子菜单）**

- 每条显示 `alias`；点击 → 系统默认浏览器打开对应 `url`。
- 无书签时：一项禁用的「暂无网址」。
- 分隔线后：**管理…** → 打开网址管理悬浮面板。

**待办**

- 单项「待办」→ 打开待办悬浮面板（不在菜单里枚举待办项，避免过长）。

---

## 5. 悬浮面板行为

网址管理面板与待办面板共用规则，视觉对齐现有 `ChatInputBubble`：

- 无边框、圆角浅色底、`Qt.Tool` + 置顶（跟随宠物 `is_stay_on_top`）。
- 默认锚在茄子**下方水平居中**；超出屏幕可用区时夹入边界。
- 茄子拖动 / 缩放时跟随重定位；隐藏宠物时面板一并隐藏。
- **互斥**：同时只显示一个业务面板；与聊天输入也互斥（打开其一关闭其他）。
- Esc 或面板「关闭」→ 关闭；再次点同一菜单项 → 切换显示/隐藏。

### 网址管理面板

- 列表展示别名 + URL；选中后可编辑并保存，或删除。
- 底部：别名、URL 输入 +「添加」；对选中项提供「保存」更新。

### 待办面板

- 列表：勾选框 + 文案（完成项划线）。
- 支持：添加、勾选切换、删除、单击文案编辑、清空已完成。

---

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| `data.json` 缺失 / 损坏 | 空数据 + 写回默认结构 |
| 别名或待办文案为空 | 忽略提交；输入区简短提示 |
| URL 为空或无法规范化 | 不添加；管理面板简短提示 |
| 打开浏览器失败 | 不崩溃；可选气泡提示「打不开这个链接」 |
| 磁盘写入失败 | 保留内存状态，控制台打日志，下次操作再试 |

---

## 7. 测试计划

对齐现有 `tests/test_chat.py` 风格，以 `storage` 纯逻辑为主：

- 读写、坏文件恢复
- bookmark / todo CRUD
- `clear_completed_todos`
- `normalize_url`（无协议补 `https://`）

面板交互：手动验证右键菜单、托盘菜单、跟随定位、互斥与 Esc 关闭。

---

## 8. 成功标准

- 可添加带别名的网址，子菜单一点即开浏览器。
- 管理面板可改/删网址，重启后仍在。
- 待办面板悬浮在茄子下方，支持添加/勾选/编辑/删除/清空已完成，重启后仍在。
- 右键与托盘入口行为一致；不破坏现有聊天、托盘、动画能力。
