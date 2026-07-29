# 🍆 茄子桌面宠物

一个可爱的茄子毛绒玩具风格的 Windows 桌面宠物程序。

## ✨ 功能特性

- 🖼️ **透明窗口**：无边框、背景透明，角色浮在桌面上
- 📌 **始终置顶**：默认置顶显示，随时可见
- 🖱️ **拖动移动**：鼠标左键按住角色可拖动到任意位置
- 🎯 **点击互动**：点击角色轮流触发三种动画：
  - 🦘 跳跃：茄子向上跳起再落下
  - 🔘 压扁回弹：茄子被压扁然后弹性恢复
  - 〰️ 左右抖动：茄子左右摇晃
- 💬 **对话气泡**：互动时随机显示有趣的中文对话气泡
- 📏 **滚轮缩放**：鼠标滚轮可以调整角色大小
- 📋 **右键菜单**：
  - 调整大小（小/中/大/超大）
  - 置顶开关
  - 退出程序

## 🚀 快速开始

### 方式一：直接运行 Python 源码

1. 安装 Python 3.8+（官网下载：https://www.python.org/downloads/）
2. 安装依赖：
   ```bash
   pip install PyQt5
   ```
3. 运行程序：
   ```bash
   python main.py
   ```

### 方式二：GitHub Actions 云端打包（无需本机 Windows / Python）

1. 将代码推送到 GitHub（`main` 分支）
2. 打开仓库 **Actions** 页面，等待 **Build Windows EXE** 完成
3. 进入该次运行详情，在 **Artifacts** 中下载 `eggplant-pet-windows`
4. 解压得到 `茄子桌宠.exe`，在 Windows 上双击运行

也可在 Actions 页面点击 **Run workflow** 手动触发打包。

> 💡 打包后的 EXE 是单文件，内置 Python 运行时，目标电脑无需安装 Python

### 方式三：本机 Windows 打包

1. 确保已安装 Python 3.8+
2. 双击运行 `build.bat` 脚本
3. 生成的 EXE 在 `dist` 文件夹中

## 🎮 使用说明

| 操作 | 功能 |
|------|------|
| 左键拖动 | 移动桌宠位置 |
| 左键点击 | 触发互动动画 + 对话气泡 |
| 鼠标滚轮 | 调整大小（向上放大，向下缩小） |
| 右键点击 | 打开菜单 |

## 📁 文件说明

```
eggplant_pet/
├── main.py                          # 主程序源码
├── eggplant.png                     # 茄子角色图片（透明背景）
├── build.bat                        # Windows 本机打包脚本
├── .github/workflows/build-windows.yml  # GitHub Actions 云端打包
└── README.md                        # 说明文档
```

## 🔧 自定义修改

### 修改对话内容
打开 `main.py`，找到 `DIALOGUES` 列表，添加或修改你喜欢的对话。

### 修改基础大小
找到 `self.base_size = 150`，调整数值可以改变默认大小。

### 修改动画速度
在各动画函数中调整 `duration` 参数（单位：毫秒）。

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
   pyinstaller --onefile --windowed --name "茄子桌宠" --add-data "eggplant.png;." main.py
   ```

---

祝你使用愉快！🍆✨
