# -*- coding: utf-8 -*-
import unittest

import main


class TestWindowsToolExstyle(unittest.TestCase):
    def test_adds_toolwindow_and_clears_appwindow(self):
        style = main._WS_EX_APPWINDOW | 0x1
        result = main._windows_tool_exstyle(style)
        self.assertEqual(result & main._WS_EX_TOOLWINDOW, main._WS_EX_TOOLWINDOW)
        self.assertEqual(result & main._WS_EX_APPWINDOW, 0)
        self.assertEqual(result & 0x1, 0x1)

    def test_idempotent_when_already_toolwindow(self):
        style = main._WS_EX_TOOLWINDOW
        self.assertEqual(main._windows_tool_exstyle(style), main._WS_EX_TOOLWINDOW)

    def test_topmost_flags_do_not_use_showwindow(self):
        flags = main._WINDOWS_TOPMOST_FLAGS
        self.assertEqual(flags & main._SWP_SHOWWINDOW, 0)
        self.assertEqual(flags & main._SWP_NOACTIVATE, main._SWP_NOACTIVATE)
        self.assertEqual(flags & main._SWP_NOMOVE, main._SWP_NOMOVE)
        self.assertEqual(flags & main._SWP_NOSIZE, main._SWP_NOSIZE)


if __name__ == "__main__":
    unittest.main()
