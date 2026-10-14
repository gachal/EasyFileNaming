"""改名方案:去重、与现有文件冲突、大小写不敏感、日期后缀。"""
from __future__ import annotations

import os

from easyfilenaming.core.rename_plan import (
    ST_NO_CHANGE, ST_OK, ST_UNRECOGNIZED, build_plan,
)
from easyfilenaming.core.settings import Settings
from easyfilenaming.core.title_extractor import ExtractedTitle


def title(text):
    return ExtractedTitle(text=text, method="layout", confidence=0.95)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x")


def test_dedup_among_entries_and_existing(tmp_path):
    _touch(str(tmp_path / "a.jpg"))
    _touch(str(tmp_path / "b.jpg"))
    _touch(str(tmp_path / "收益分配表.jpg"))  # 目录里已有的同名文件

    paths = [str(tmp_path / "a.jpg"), str(tmp_path / "b.jpg")]
    titles = {p: title("收益分配表") for p in paths}
    plan = build_plan(str(tmp_path), paths, titles, Settings(),
                      case_insensitive=True)

    finals = [e.final for e in plan.entries]
    # 已有文件占用基名,两张依次得 -2 / -3
    assert finals == ["收益分配表-2", "收益分配表-3"]
    assert all(e.status == ST_OK for e in plan.entries)


def test_same_name_marks_no_change(tmp_path):
    p = str(tmp_path / "收益分配表.jpg")
    _touch(p)
    plan = build_plan(str(tmp_path), [p], {p: title("收益分配表")},
                      Settings(), case_insensitive=True)
    e = plan.entries[0]
    assert e.status == ST_NO_CHANGE
    assert e.final == "收益分配表"


def test_case_only_difference_is_rename(tmp_path):
    # 大小写不敏感卷上仅大小写不同也算改名(两阶段可安全处理)
    p = str(tmp_path / "invoice.jpg")
    _touch(p)
    plan = build_plan(str(tmp_path), [p], {p: title("Invoice")},
                      Settings(), case_insensitive=True)
    assert plan.entries[0].status == ST_OK


def test_unrecognized_keeps_empty_final(tmp_path):
    p = str(tmp_path / "x.jpg")
    _touch(p)
    plan = build_plan(str(tmp_path), [p], {p: None}, Settings(),
                      case_insensitive=True)
    e = plan.entries[0]
    assert e.status == ST_UNRECOGNIZED
    assert e.final is None


def test_append_date(tmp_path):
    import time
    p = str(tmp_path / "x.jpg")
    _touch(p)
    stamp = time.strftime("%Y%m%d", time.localtime(os.path.getmtime(p)))
    plan = build_plan(str(tmp_path), [p], {p: title("报销单")},
                      Settings(append_date=True), case_insensitive=True)
    assert plan.entries[0].final == "报销单-" + stamp
