# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from pathlib import Path

import storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["EGGPLANT_PET_HOME"] = self.tmp.name
        # 避免模块缓存路径；每次用 data_path() 读 env

    def tearDown(self):
        os.environ.pop("EGGPLANT_PET_HOME", None)

    def test_normalize_url_adds_https(self):
        self.assertEqual(storage.normalize_url("github.com"), "https://github.com")
        self.assertEqual(storage.normalize_url("https://a.com"), "https://a.com")
        self.assertEqual(storage.normalize_url("http://a.com"), "http://a.com")

    def test_load_missing_returns_empty_and_creates_file(self):
        data = storage.load()
        self.assertEqual(data["bookmarks"], [])
        self.assertEqual(data["todos"], [])
        self.assertTrue(storage.data_path().is_file())

    def test_load_corrupt_recovers(self):
        p = storage.data_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        corrupt = "{not json"
        p.write_text(corrupt, encoding="utf-8")
        data = storage.load()
        self.assertEqual(data, storage.DEFAULT_DATA)
        bak = p.with_name(p.name + ".bak")
        self.assertTrue(bak.is_file())
        self.assertEqual(bak.read_text(encoding="utf-8"), corrupt)
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")), storage.DEFAULT_DATA)

    def test_bookmark_crud(self):
        b = storage.add_bookmark("GH", "github.com")
        self.assertEqual(b["alias"], "GH")
        self.assertEqual(b["url"], "https://github.com")
        self.assertTrue(b["id"])
        self.assertEqual(len(storage.list_bookmarks()), 1)
        storage.update_bookmark(b["id"], "GitHub", "https://github.com/x")
        self.assertEqual(storage.list_bookmarks()[0]["alias"], "GitHub")
        storage.delete_bookmark(b["id"])
        self.assertEqual(storage.list_bookmarks(), [])

    def test_add_bookmark_rejects_empty(self):
        with self.assertRaises(ValueError):
            storage.add_bookmark("", "https://a.com")
        with self.assertRaises(ValueError):
            storage.add_bookmark("a", "  ")

    def test_update_todo_missing_id_raises_keyerror(self):
        with self.assertRaises(KeyError):
            storage.update_todo("missing-id", text="nope")

    def test_todo_crud_and_clear_completed(self):
        t1 = storage.add_todo("写周报")
        t2 = storage.add_todo("开会")
        storage.update_todo(t1["id"], done=True)
        storage.update_todo(t2["id"], text="开会纪要")
        n = storage.clear_completed_todos()
        self.assertEqual(n, 1)
        todos = storage.list_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["text"], "开会纪要")
        self.assertFalse(todos[0]["done"])


if __name__ == "__main__":
    unittest.main()
