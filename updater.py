# -*- coding: utf-8 -*-
"""应用内自动更新：版本比较与 GitHub / Gitee Releases 选择。"""

import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request

GITHUB_OWNER = "1301604100"
GITHUB_REPO = "eggplant"
GITEE_OWNER = "kary2"
GITEE_REPO = "eggplant-releases"
WINDOWS_ASSET_NAMES = ("茄子桌宠.exe", "EggplantPet-Windows.exe")
MAC_ASSET_NAMES = ("EggplantPet-macOS.zip",)
# 兼容旧测试/引用
ASSET_NAMES = WINDOWS_ASSET_NAMES
CREATE_NO_WINDOW = 0x08000000
RELEASES_PAGE_URL = "https://github.com/%s/%s/releases" % (
    GITHUB_OWNER,
    GITHUB_REPO,
)
GITEE_RELEASES_PAGE_URL = "https://gitee.com/%s/%s/releases" % (
    GITEE_OWNER,
    GITEE_REPO,
)
GITHUB_RELEASES_API = "https://api.github.com/repos/%s/%s/releases" % (
    GITHUB_OWNER,
    GITHUB_REPO,
)
GITEE_RELEASES_API = "https://gitee.com/api/v5/repos/%s/%s/releases" % (
    GITEE_OWNER,
    GITEE_REPO,
)

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
    """是否启用应用内自动下载替换（Windows / macOS 打包版）。"""
    if platform is None:
        platform = sys.platform
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return frozen and platform in ("win32", "darwin")


def releases_page_url(source=None):
    """打开发布页：按检查来源选择 GitHub 或 Gitee。"""
    if source == "gitee":
        return GITEE_RELEASES_PAGE_URL
    return RELEASES_PAGE_URL


def asset_names_for_platform(platform=None):
    if platform is None:
        platform = sys.platform
    if platform == "darwin":
        return MAC_ASSET_NAMES
    return WINDOWS_ASSET_NAMES


def resolve_app_bundle(executable_path):
    """从 Mac .app 内可执行文件路径解析出 .app 包根目录。"""
    path = os.path.abspath(executable_path or "")
    while path and path != os.path.dirname(path):
        if path.endswith(".app"):
            return path
        path = os.path.dirname(path)
    return None


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


def _asset_for_release(release, platform=None):
    assets = release.get("assets")
    if not assets:
        assets = release.get("attach_files") or []
    by_name = {a.get("name"): a for a in assets if isinstance(a, dict)}
    for name in asset_names_for_platform(platform):
        if name in by_name:
            a = by_name[name]
            url = a.get("browser_download_url") or a.get("download_url")
            if url:
                size = a.get("size")
                try:
                    size = int(size) if size is not None else None
                except (TypeError, ValueError):
                    size = None
                return url, size
    return None, None


def pick_latest_release(releases, source=None, platform=None):
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
        url, size = _asset_for_release(rel, platform=platform)
        if not url:
            continue
        if best_tuple is None or compare_versions(ver_tuple, best_tuple) > 0:
            best_tuple = ver_tuple
            body = rel.get("body")
            if body is None:
                body = ""
            best = {
                "version": "%d.%d.%d" % ver_tuple,
                "tag": tag if str(tag).startswith("v") else "v%s" % ("%d.%d.%d" % ver_tuple),
                "download_url": url,
                "size": size,
                "body": str(body),
                "source": source or "github",
            }
    return best


def format_release_notes(body, max_chars=360):
    """把 Release body 收成弹窗可用的纯文本摘要。"""
    text = str(body or "").replace("\r\n", "\n").strip()
    if not text:
        return "暂无更新说明"
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def format_update_prompt_text(local_version, release):
    notes = format_release_notes(release.get("body") if release else "")
    return "发现新版本 %s（当前 %s）\n\n%s" % (
        release["version"],
        local_version,
        notes,
    )


def _default_urlopen(req, timeout=15):
    return urllib.request.urlopen(req, timeout=timeout)


def _api_request(url, accept=None):
    headers = {"User-Agent": "eggplant-pet"}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def _fetch_releases_list(api_url, urlopen, timeout, accept=None):
    opener = urlopen or _default_urlopen
    req = _api_request(api_url, accept=accept)
    with opener(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("unexpected releases payload from %s" % api_url)
    return data


def fetch_latest_release(urlopen=None, timeout=15, platform=None):
    """先 GitHub，失败或无可用资产时再 Gitee。"""
    errors = []
    sources = (
        ("github", GITHUB_RELEASES_API, "application/vnd.github+json"),
        ("gitee", GITEE_RELEASES_API, None),
    )
    for source, api_url, accept in sources:
        try:
            data = _fetch_releases_list(api_url, urlopen, timeout, accept=accept)
            picked = pick_latest_release(data, source=source, platform=platform)
            if picked:
                print("updater: using %s release %s" % (source, picked.get("tag")))
                return picked
            print("updater: %s has no usable release asset, try next" % source)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
            print("updater: %s fetch failed: %r" % (source, exc))
            errors.append(exc)
    if errors:
        raise errors[0]
    return None


def check_for_update(local_version=None, urlopen=None, platform=None):
    local = local_version if local_version is not None else read_local_version()
    local_t = parse_version(local)
    latest = fetch_latest_release(urlopen=urlopen, platform=platform)
    if not latest:
        return None
    if compare_versions(parse_version(latest["version"]), local_t) > 0:
        return latest
    return None


def download_update(url, dest_path, expected_size=None, urlopen=None, progress_callback=None):
    opener = urlopen or _default_urlopen
    req = _api_request(url)
    received = 0
    try:
        with opener(req, timeout=120) as resp:
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
        for p in (dest_path, dest_path + ".part"):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        raise


def build_update_bat_content(current_exe, new_exe, pid):
    lines = [
        "@echo off",
        "setlocal",
        'set "PID=%d"' % int(pid),
        'set "NEW=%s"' % new_exe,
        'set "CUR=%s"' % current_exe,
        'set "LOG=%~dp0update-failed.log"',
        ":wait",
        "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul",
        "if not errorlevel 1 (",
        "  ping -n 2 127.0.0.1 >nul",
        "  goto wait",
        ")",
        "set RETRIES=15",
        ":copy_retry",
        "copy /Y \"%NEW%\" \"%CUR%\" >nul 2>&1",
        "if not errorlevel 1 goto copy_ok",
        "set /a RETRIES-=1",
        "if %RETRIES% LEQ 0 goto copy_failed",
        "ping -n 2 127.0.0.1 >nul",
        "goto copy_retry",
        ":copy_failed",
        "> \"%LOG%\" echo Update failed after 15 copy attempts.",
        ">> \"%LOG%\" echo New file: \"%NEW%\"",
        ">> \"%LOG%\" echo Current file: \"%CUR%\"",
        "exit /b 1",
        ":copy_ok",
        "start \"\" \"%CUR%\"",
        "del \"%NEW%\" >nul 2>&1",
        "endlocal",
    ]
    return "\r\n".join(lines) + "\r\n"


def build_update_sh_content(app_bundle, new_zip, pid):
    """生成 macOS 替换 .app 的 bash 脚本。"""
    # 用单引号包路径，内部单引号转义为 '\'' 
    def q(path):
        return "'%s'" % str(path).replace("'", "'\\''")

    lines = [
        "#!/bin/bash",
        "set -e",
        "PID=%d" % int(pid),
        "NEW=%s" % q(new_zip),
        "APP=%s" % q(app_bundle),
        'LOG="$(dirname "$NEW")/update-failed.log"',
        'while kill -0 "$PID" 2>/dev/null; do sleep 1; done',
        'TMP="$(mktemp -d)"',
        "cleanup() { rm -rf \"$TMP\"; }",
        "trap cleanup EXIT",
        'if ! unzip -q "$NEW" -d "$TMP"; then',
        '  echo "unzip failed" > "$LOG"',
        "  exit 1",
        "fi",
        'NEW_APP="$(find "$TMP" -maxdepth 3 -name \'*.app\' -type d | head -n 1)"',
        'if [ -z "$NEW_APP" ] || [ ! -d "$NEW_APP" ]; then',
        '  echo "no .app in zip" > "$LOG"',
        "  exit 1",
        "fi",
        'PARENT="$(dirname "$APP")"',
        'BASENAME="$(basename "$APP")"',
        'DEST="$PARENT/$BASENAME"',
        'rm -rf "$DEST"',
        'mv "$NEW_APP" "$DEST"',
        'xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true',
        'open "$DEST"',
        'rm -f "$NEW"',
    ]
    return "\n".join(lines) + "\n"


def write_update_script(current_exe, new_file, pid, script_path, platform=None):
    if platform is None:
        platform = sys.platform
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if platform == "darwin":
        app = resolve_app_bundle(current_exe)
        if not app:
            raise ValueError("cannot resolve .app bundle from %r" % (current_exe,))
        content = build_update_sh_content(app, new_file, pid)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        mode = os.stat(script_path).st_mode
        os.chmod(script_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return script_path
    content = build_update_bat_content(current_exe, new_file, pid)
    encoding = "oem" if platform == "win32" else "utf-8"
    with open(script_path, "w", encoding=encoding) as f:
        f.write(content)
    return script_path


def launch_update_and_exit(script_path, quit_callback):
    kwargs = {"close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        subprocess.Popen(["cmd.exe", "/c", script_path], **kwargs)
    elif sys.platform == "darwin":
        subprocess.Popen(["/bin/bash", script_path], **kwargs)
    else:
        subprocess.Popen(["/bin/sh", script_path], **kwargs)
    if quit_callback:
        quit_callback()
