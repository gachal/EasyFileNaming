"""pytest 公共夹具:src 布局导入 + 数据目录打桩到 tmp。"""
from __future__ import annotations

import os
import sys

import pytest

SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """把设置/撤销日志的数据目录指到临时目录,避免污染真实用户目录。

    undo 模块经 `_settings.data_dir` 动态取值,与 settings 模块是同一
    模块对象,故只需打桩一处。
    """
    from easyfilenaming.core import settings as settings_mod

    target = str(tmp_path / "appdata")
    monkeypatch.setattr(settings_mod, "data_dir", lambda: target)
    yield target
