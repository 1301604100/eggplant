# -*- coding: utf-8 -*-
"""本地 JSON 持久化：常用网址与待办。"""

from __future__ import print_function

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA = {"bookmarks": [], "todos": []}


def data_path():
    home = os.environ.get("EGGPLANT_PET_HOME")
    base = Path(home) if home else Path.home() / ".eggplant_pet"
    return base / "data.json"


def load():
    path = data_path()
    if not path.is_file():
        data = {"bookmarks": [], "todos": []}
        save(data)
        return data
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("root must be object")
        data = {
            "bookmarks": list(raw.get("bookmarks") or []),
            "todos": list(raw.get("todos") or []),
        }
        return data
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        print("storage.load: corrupt data, resetting:", e)
        data = {"bookmarks": [], "todos": []}
        save(data)
        return data


def save(data):
    path = data_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError as e:
        print("storage.save failed:", e)


def normalize_url(url):
    text = (url or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return text
    return "https://" + text


def list_bookmarks():
    return list(load().get("bookmarks") or [])


def add_bookmark(alias, url):
    alias = (alias or "").strip()
    url = normalize_url(url)
    if not alias or not url:
        raise ValueError("alias and url required")
    data = load()
    item = {"id": str(uuid.uuid4()), "alias": alias, "url": url}
    data["bookmarks"].append(item)
    save(data)
    return item


def update_bookmark(bookmark_id, alias, url):
    alias = (alias or "").strip()
    url = normalize_url(url)
    if not alias or not url:
        raise ValueError("alias and url required")
    data = load()
    for item in data["bookmarks"]:
        if item.get("id") == bookmark_id:
            item["alias"] = alias
            item["url"] = url
            save(data)
            return item
    raise KeyError(bookmark_id)


def delete_bookmark(bookmark_id):
    data = load()
    data["bookmarks"] = [b for b in data["bookmarks"] if b.get("id") != bookmark_id]
    save(data)


def list_todos():
    return list(load().get("todos") or [])


def add_todo(text):
    text = (text or "").strip()
    if not text:
        raise ValueError("text required")
    data = load()
    item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "done": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["todos"].append(item)
    save(data)
    return item


def update_todo(todo_id, text=None, done=None):
    data = load()
    for item in data["todos"]:
        if item.get("id") == todo_id:
            if text is not None:
                text = text.strip()
                if not text:
                    raise ValueError("text required")
                item["text"] = text
            if done is not None:
                item["done"] = bool(done)
            save(data)
            return item
    raise KeyError(todo_id)


def delete_todo(todo_id):
    data = load()
    data["todos"] = [t for t in data["todos"] if t.get("id") != todo_id]
    save(data)


def clear_completed_todos():
    data = load()
    before = len(data["todos"])
    data["todos"] = [t for t in data["todos"] if not t.get("done")]
    removed = before - len(data["todos"])
    save(data)
    return removed
