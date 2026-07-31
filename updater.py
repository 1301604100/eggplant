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
