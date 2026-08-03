# -*- coding: utf-8 -*-
"""应用内自动更新：版本比较与 GitHub Releases 选择。"""

import json
import os
import re
import subprocess
import sys
import urllib.request

GITHUB_OWNER = "1301604100"
GITHUB_REPO = "eggplant"
ASSET_NAMES = ("茄子桌宠.exe", "EggplantPet-Windows.exe")
CREATE_NO_WINDOW = 0x08000000
RELEASES_PAGE_URL = "https://github.com/%s/%s/releases" % (
    GITHUB_OWNER,
    GITHUB_REPO,
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
    """是否启用应用内自动下载替换（仅 Windows 打包版）。"""
    if platform is None:
        platform = sys.platform
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return platform == "win32" and frozen


def releases_page_url():
    """GitHub Releases 页面（非 Windows 打包版「检查更新」跳转用）。"""
    return RELEASES_PAGE_URL


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
            body = rel.get("body")
            if body is None:
                body = ""
            best = {
                "version": "%d.%d.%d" % ver_tuple,
                "tag": tag if str(tag).startswith("v") else "v%s" % ("%d.%d.%d" % ver_tuple),
                "download_url": url,
                "size": size,
                "body": str(body),
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


def write_update_script(current_exe, new_exe, pid, script_path):
    content = build_update_bat_content(current_exe, new_exe, pid)
    parent = os.path.dirname(script_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    encoding = "oem" if sys.platform == "win32" else "utf-8"
    with open(script_path, "w", encoding=encoding) as f:
        f.write(content)
    return script_path


def launch_update_and_exit(script_path, quit_callback):
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        kwargs["close_fds"] = True
    subprocess.Popen(["cmd.exe", "/c", script_path], **kwargs)
    if quit_callback:
        quit_callback()
