@echo off
chcp 65001 >nul
echo ========================================
echo   茄子桌面宠物 - Windows 打包脚本
echo ========================================
echo.

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python，请先安装 Python 3.8 或更高版本
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Python 环境正常
echo.

echo [2/3] 安装依赖包...
pip install PyQt5 pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo 警告：依赖安装可能失败，请检查网络连接
    pause
)
echo 依赖安装完成
echo.

echo [3/3] 打包 EXE 文件...
pyinstaller --onefile --windowed --name "茄子桌宠" --icon=eggplant.ico --add-data "eggplant.png;." --add-data "eggplant.ico;." --hidden-import bubble --hidden-import chat --hidden-import tray --hidden-import storage --hidden-import bookmarks --hidden-import todos main.py

if errorlevel 1 (
    echo.
    echo 打包失败！请检查错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包成功！
echo ========================================
echo.
echo EXE 文件位置：dist\茄子桌宠.exe
echo.
echo 你可以直接双击运行 dist\茄子桌宠.exe
echo.
pause
