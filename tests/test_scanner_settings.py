"""文件夹扫描 + 设置持久化。"""
from __future__ import annotations

import os

from easyfilenaming.core import scanner, settings as settings_mod
from easyfilenaming.core.settings import Settings


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x")


def test_scan_recursive_and_filters(tmp_path):
    _touch(str(tmp_path / "a.jpg"))
    _touch(str(tmp_path / "B.PNG"))
    _touch(str(tmp_path / "sub" / "c.webp"))
    _touch(str(tmp_path / "sub" / "deep" / "d.jpeg"))
    _touch(str(tmp_path / "e.txt"))            # 不支持格式
    _touch(str(tmp_path / ".hidden.png"))      # 隐藏文件
    _touch(str(tmp_path / ".efn_tmp_0.jpg"))   # 应用临时文件

    found = scanner.scan_folder(str(tmp_path), recursive=True)
    names = [os.path.basename(p) for p in found]
    assert sorted(names) == ["B.PNG", "a.jpg", "c.webp", "d.jpeg"]
    assert str(tmp_path / "sub" / "c.webp") in found

    top_only = scanner.scan_folder(str(tmp_path), recursive=False)
    assert sorted(os.path.basename(p) for p in top_only) == [
        "B.PNG", "a.jpg",
    ]


def test_settings_roundtrip():
    s = Settings(recursive=False, min_confidence=0.75, max_title_len=20,
                 append_date=True)
    settings_mod.save(s)
    loaded = settings_mod.load()
    assert loaded == s


def test_all_core_modules_importable():
    # 覆盖每个核心模块,防止改坏导入路径(如 __version__ 层级)
    import easyfilenaming  # noqa: F401
    from easyfilenaming.core import (  # noqa: F401
        applier, diagnostics, ocr, rename_plan, scanner, title_extractor,
        undo,
    )
    assert easyfilenaming.__version__
