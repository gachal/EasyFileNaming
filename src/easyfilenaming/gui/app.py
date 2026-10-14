"""wx 应用入口。"""
from __future__ import annotations

import os
import sys


def main() -> None:
    import wx

    from .main_frame import MainFrame

    app = wx.App(False)
    frame = MainFrame(None, title="EasyFileNaming — 按内容批量改名")
    frame.Show()
    app.MainLoop()
    # wx 4.2.1 在较新 macOS 上解释器卸载时段错误(已实测 MainLoop 正常
    # 结束后仍崩溃);此时全部落盘工作已完成,直接结束进程绕过 C++ 卸载。
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
