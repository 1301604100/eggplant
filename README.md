# 🍆 茄子桌面宠物

一个可爱的茄子毛绒玩具风格的 Windows 桌面宠物程序。

## ⚖️ 许可与使用限制

本项目为**专有软件**，详见根目录 [`LICENSE`](LICENSE)。

- **允许**：通过 [GitHub Releases](https://github.com/1301604100/eggplant/releases) 下载官方构建，供个人非商业运行。
- **禁止**：未经书面许可，使用、复制、修改、分发本仓库**源代码**，或基于源码二次开发/再发布。

## ✨ 功能特性

- 🖼️ **透明窗口**：无边框、背景透明，角色浮在桌面上
- 📌 **始终置顶**：默认置顶显示，随时可见
- 🖱️ **拖动移动**：鼠标左键按住角色可拖动到任意位置
- 🎯 **点击互动**：点击角色轮流触发三种动画：
  - 🦘 跳跃：茄子向上跳起再落下
  - 🔘 压扁回弹：茄子被压扁然后弹性恢复
  - 〰️ 左右抖动：茄子左右摇晃
- 💬 **对话气泡**：点击时随机气泡；也可「聊聊天」输入，本地关键词回复
- 🔗 **常用网址**：右键/托盘子菜单按别名快速打开；「管理…」打开悬浮面板，添加/编辑/删除网址
- ✅ **待办列表**：右键/托盘「待办」打开悬浮面板（锚在茄子下方），添加、勾选、编辑、删除、清空已完成
- 🔔 **系统托盘**：显示/隐藏宠物、聊聊天、常用网址、待办、退出；双击托盘恢复显示
- 📏 **滚轮缩放**：鼠标滚轮可以调整角色大小
- 📋 **右键菜单**：
  - 聊聊天 / 隐藏
  - 常用网址（子菜单按别名打开；管理… 悬浮编辑）
  - 待办（悬浮在茄子下方）
  - 调整大小（小/中/大/超大）
  - 置顶开关
  - 退出程序

## 🚀 快速开始

### 方式一：GitHub Releases 下载（推荐，无需本机 Windows / Python）

打包成功后会按根目录 `VERSION` 自动发布到 Releases（如 `v1.0.0`），长期可下载：

1. 打开 [Releases 页面](https://github.com/1301604100/eggplant/releases)
2. 进入对应版本（tag: `v{VERSION}`，例如 `v1.0.0`）
3. 下载 `茄子桌宠.exe` 或 `EggplantPet-Windows.exe`，双击运行

右键/托盘菜单均有「检查更新」：先查询最新 Release 并弹出更新说明。Windows 安装版确认后自动下载替换 EXE；macOS / 源码运行确认后打开 GitHub Releases 页面。Windows 安装版还会在启动约 3 秒后静默检查；选择「稍后」则本会话不再自动弹出。

发新版：修改根目录 `VERSION` → 打并推送 tag（如 `git tag v1.0.1 && git push origin v1.0.1`）。只有 `v*` tag 变动才会触发云端打包；也可在 Actions 里手动 **Run workflow**。同一 tag 重复推送会覆盖该版本资产。

> 💡 打包后的 EXE 是单文件，内置 Python 运行时，目标电脑无需安装 Python  
> Artifacts 仍会保留一份临时产物，但请优先用 Releases 链接分享

> 源码仅供版权所有者维护使用，第三方请勿克隆运行或二次分发（见 `LICENSE`）。

## 🎮 使用说明

| 操作 | 功能 |
|------|------|
| 左键拖动 | 移动桌宠位置 |
| 左键点击 | 触发互动动画 + 随机对话气泡 |
| 鼠标滚轮 | 调整大小（向上放大，向下缩小） |
| 右键 → 聊聊天 | 打开输入框，本地剧本对话 |
| 右键 → 常用网址 | 子菜单按别名打开浏览器；「管理…」悬浮编辑 |
| 右键 → 待办 | 悬浮待办面板（添加/勾选/编辑/删除/清空已完成） |
| 右键 → 隐藏 | 隐藏桌宠（托盘可恢复） |
| 托盘 → 常用网址 / 待办 | 与右键菜单相同入口 |
| 托盘双击 | 显示并置前桌宠 |
| Esc（输入框/面板） | 关闭聊天输入或悬浮面板 |

## 📁 文件说明

```
eggplant_pet/
├── main.py                          # 主窗口与动画
├── bubble.py                        # 说话气泡 / 聊天输入
├── chat.py                          # 本地关键词回复
├── tray.py                          # 系统托盘
├── storage.py                       # 本地 JSON 持久化（网址/待办）
├── bookmarks.py                     # 常用网址管理面板
├── todos.py                         # 待办列表面板
├── eggplant.png                     # 茄子角色图片（透明背景）
├── eggplant.ico                     # Windows 应用 / EXE 图标
├── build.bat                        # Windows 本机打包脚本
├── .github/workflows/build-windows.yml  # GitHub Actions 云端打包
└── README.md                        # 说明文档
```

## 💾 数据存储

常用网址与待办保存在用户目录：

```
~/.eggplant_pet/data.json
```

重启后自动加载；损坏时会备份并恢复为空数据。

## 📋 系统要求

- Windows 7 / 8 / 10 / 11
- Python 3.8 或更高版本（仅源码运行和打包时需要）
- 约 50MB 磁盘空间

## ❓ 常见问题

**Q: 运行后看不到角色？**
A: 角色默认出现在屏幕右下角，检查是否被其他窗口遮挡。

**Q: 如何退出程序？**
A: 右键点击角色，选择"退出"。

**Q: 打包失败怎么办？**
A: 确保已安装 Python 和 pip，尝试手动执行：
   ```
   pip install PyQt5 pyinstaller
   pyinstaller --onefile --windowed --name "茄子桌宠" --icon=eggplant.ico --add-data "eggplant.png;." --add-data "eggplant.ico;." --add-data "VERSION;." --hidden-import bubble --hidden-import chat --hidden-import tray --hidden-import storage --hidden-import bookmarks --hidden-import todos --hidden-import ui_theme --hidden-import updater main.py
   ```

---

祝你使用愉快！🍆✨
