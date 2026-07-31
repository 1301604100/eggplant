# 茄子桌宠：应用内自动更新 设计规格

**日期：** 2026-07-31  
**状态：** 待用户审阅  
**范围：** Windows 打包版启动/手动检查更新、语义版本、GitHub Releases 下载并替换重启  

---

## 1. 目标与非目标

### 目标

- Windows 打包版（PyInstaller `sys.frozen`）支持**启动静默检查**与菜单**「检查更新」**。
- 使用语义版本（`VERSION` 文件 + `vX.Y.Z` Release tag）判断是否有新版本。
- 用户确认后，应用内下载 EXE，经临时脚本替换当前文件并重启，无需再打开 GitHub 页面手动下载。
- 用户数据目录 `~/.eggplant_pet/` 不受 EXE 替换影响。

### 非目标（本次不做）

- macOS / 源码运行下的自动替换
- 差分包、代码签名校验、强制更新
- 「跳过此版本」持久记忆、更新日志 UI
- 自建 CDN / 第三方更新框架（pyupdater 等）

---

## 2. 架构与模块

采用自研轻量更新器 + GitHub Releases API（方案 1）。

```
eggplant_pet/
├── VERSION                 # 单一版本源，如 1.0.0
├── updater.py              # 查版本 / 下载 / 写替换脚本
├── main.py                 # 启动延迟检查、气泡确认、触发更新
├── tray.py                 # 「检查更新」菜单项
├── build.bat               # 打包纳入 VERSION / updater
└── .github/workflows/build-windows.yml
```

| 模块 | 职责 | 依赖 |
|------|------|------|
| `VERSION` | 本地版本唯一来源；打包时 `--add-data` 打进 EXE | — |
| `updater.py` | 读本地版本；请求 Releases API；semver 比较；下载；生成替换+重启脚本 | 标准库（urllib、json、tempfile、subprocess 等） |
| `main.py` | 启动约 3s 后后台检查；气泡「更新 / 稍后」；下载进度提示；退出前启动 bat | updater, bubble |
| `tray.py` | 托盘菜单「检查更新」回调 | 由 main 注入 |

**启用条件：** `sys.platform == "win32"` 且 `getattr(sys, "frozen", False)`。  
源码运行与 macOS：**不**做启动检查；菜单项隐藏（或点按提示「仅 Windows 安装版支持自动更新」——实现时优先**隐藏**以减少干扰）。

**仓库常量：** `owner=1301604100`，`repo=eggplant`（与现有 Releases 一致；可集中写在 `updater.py`）。

---

## 3. 版本比较与发版流程

### 本地版本

- 根目录 `VERSION`：单行文本，如 `1.0.0`（可含前后空白，读取时 strip）。
- 运行时优先从打包资源读取 `VERSION`；失败则视为 `0.0.0`（便于永远能提示去更新）。

### 远端版本

- `GET https://api.github.com/repos/1301604100/eggplant/releases`
- 过滤：非 `draft`、非 `prerelease`，且 tag 可解析为 semver（允许前缀 `v`，如 `v1.2.0` → `1.2.0`）。
- 取 semver **最大**的一条作为最新。
- 资产选择顺序：`茄子桌宠.exe` → 否则 `EggplantPet-Windows.exe`；皆无则视为无法更新。

### 比较规则

- 三段整数比较：`(major, minor, patch)`。
- 远端 > 本地 → 有更新；相等或更旧 → 已是最新。

### CI 发版（替换「仅覆盖 latest」）

1. 读仓库根目录 `VERSION`。
2. PyInstaller 打包：`--add-data VERSION;.`，`--hidden-import updater`（及既有 hidden-import）。
3. 以 tag `v{VERSION}` 创建或更新 GitHub Release，上传 `茄子桌宠.exe` 与 `EggplantPet-Windows.exe`。
4. **同一 VERSION 重复推送**：允许覆盖该 tag 资产（修包）。**发布新版本必须先改 `VERSION`。**
5. 可选：额外维护指向同一次发布的 `latest` 方便 README 外链；**客户端一律以最新 semver tag 为准**，不依赖 `latest`。

触发条件保持现有：push `main`/`master` 或 `workflow_dispatch`。

---

## 4. 交互与更新替换流程

### 入口

1. **启动检查**：满足启用条件时，启动约 **3 秒**后后台线程查询（不阻塞 UI）。
2. **手动检查**：右键菜单与托盘菜单「检查更新」（行为相同）。

### 有更新时

- 气泡文案：`发现新版本 {remote}（当前 {local}），要更新吗？`
- 操作：**更新** / **稍后**
- 「稍后」：仅本会话抑制自动弹窗；手动「检查更新」仍可再次查询并提示。

### 用户确认「更新」

1. 气泡改为「正在下载…」（可选简单进度百分比）。
2. 下载到 `%TEMP%\eggplant_pet_update\`（新 EXE 临时文件名固定或带版本号均可）。
3. 校验：文件存在、大小 > 0；若 API 提供 `size` 则与之一致，否则至少非空。
4. 写出 `update.bat`（或等效 cmd）：
   - 等待当前进程 PID 退出；
   - 将新 EXE 覆盖当前 `sys.executable` 路径；
   - 启动新 EXE；
   - 清理临时文件（尽力而为）。
5. 以独立进程启动 bat 后，桌宠正常退出。

### 无更新 / 手动已最新

- 启动静默检查无更新：**不打扰**。
- 手动检查且已最新：气泡 `已是最新版本 {local}`。

---

## 5. 错误处理

| 场景 | 行为 |
|------|------|
| 非 Windows 打包版 | 不启用检查；菜单隐藏 |
| 网络失败 / 超时 / HTTP 非 2xx | 启动检查静默失败；手动检查提示「检查失败，请稍后重试」 |
| 无合法 release / 无可用 EXE 资产 | 手动检查提示无法更新；启动检查静默 |
| 下载中断或校验失败 | 删除不完整临时文件；气泡「下载失败」 |
| 替换失败（权限、杀软、文件占用） | bat 尽力提示或保留临时 EXE；应用本身不崩溃；用户可手动覆盖 |
| `~/.eggplant_pet/` 用户数据 | 不随更新删除 |

---

## 6. 测试计划

对齐现有 unittest 风格，以 `updater` 纯逻辑为主：

- `parse_version` / 版本比较（含 `v` 前缀、相等、大小）
- 从 mock Releases JSON 选出最新非 prerelease 与资产 URL
- `should_enable_updater`：非 frozen / 非 win32 为 false

手动验证：

- 本地 VERSION 低于远端 → 启动提示 → 确认下载 → 替换重启成功
- 「稍后」后本次会话不再自动弹
- 已最新时手动检查提示文案
- 断网时手动检查失败提示

---

## 7. 成功标准

- Windows 打包版启动后能发现更高 semver 的 Release，并在确认后完成下载、替换、重启。
- 右键与托盘「检查更新」行为一致；已最新与失败时有明确气泡反馈。
- 改 `VERSION` 并推送 main 后，CI 发布 `v{VERSION}` 可供客户端拉取。
- 不破坏现有聊天、托盘、动画及本地数据持久化。
