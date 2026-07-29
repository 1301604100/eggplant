# -*- coding: utf-8 -*-
import unittest

from chat import reply


class TestChatReply(unittest.TestCase):
    def test_greeting_keyword(self):
        text = reply("你好呀")
        self.assertTrue(text)
        self.assertNotEqual(text, "")

    def test_hello_english(self):
        text = reply("hello")
        self.assertTrue(text)

    def test_empty_returns_empty(self):
        self.assertEqual(reply(""), "")
        self.assertEqual(reply("   "), "")

    def test_default_fallback(self):
        text = reply("量子力学公式推导")
        self.assertTrue(text)


if __name__ == "__main__":
    unittest.main()
