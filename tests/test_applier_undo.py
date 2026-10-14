"""两阶段应用改名 + 撤销日志回滚。"""
from __future__ import annotations

import os

from easyfilenaming.core.applier import Applier
from easyfilenaming.core.rename_plan import PlanEntry
from easyfilenaming.core import undo


def entry(path, final):
    e = PlanEntry(path=path)
    e.final = final
    e.status = "已识别"
    return e


def _touch(path, content=b"img"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content)


def test_apply_and_undo_roundtrip(tmp_path):
    a = str(tmp_path / "photo1.jpg")
    b = str(tmp_path / "photo2.jpg")
    _touch(a, b"AAA")
    _touch(b, b"BBB")

    # 交换改名:a→photo2,b→photo1(直接 rename 会互相覆盖,两阶段可解)
    result = Applier().apply([
        entry(a, "photo2"), entry(b, "photo1"),
    ])
    assert result.ok, [f.error for f in result.failed]
    with open(str(tmp_path / "photo2.jpg"), "rb") as fh:
        assert fh.read() == b"AAA"
    with open(str(tmp_path / "photo1.jpg"), "rb") as fh:
        assert fh.read() == b"BBB"
    # 不留临时文件
    assert not [n for n in os.listdir(str(tmp_path))
                if n.startswith(".efn_tmp_")]

    log = undo.save_undo_log(result.renamed, str(tmp_path))
    restored, skipped, _notes = undo.restore_log(log)
    assert (restored, skipped) == (2, 0)
    with open(a, "rb") as fh:
        assert fh.read() == b"AAA"
    with open(b, "rb") as fh:
        assert fh.read() == b"BBB"


def test_case_only_rename_on_case_insensitive_fs(tmp_path):
    # macOS 开发卷默认大小写不敏感:invoice → Invoice 必须走两阶段
    p = str(tmp_path / "invoice.jpg")
    _touch(p, b"C")
    result = Applier().apply([entry(p, "Invoice")])
    assert result.ok, [f.error for f in result.failed]
    assert os.path.exists(str(tmp_path / "Invoice.jpg"))
    assert not os.path.exists(str(tmp_path / ".efn_tmp_0.jpg"))


def test_no_tmp_left_when_phase2_fails(tmp_path):
    # 目标名造一个同名目录迫使 phase2 失败 → 应回滚原名且不留临时文件
    p = str(tmp_path / "x.jpg")
    _touch(p)
    os.makedirs(str(tmp_path / "y.jpg"))  # 目录占住目标文件名
    result = Applier().apply([entry(p, "y")])
    assert not result.ok
    assert os.path.exists(p)  # 原名已还原
    leftovers = [n for n in os.listdir(str(tmp_path))
                 if n.startswith(".efn_tmp_")]
    assert leftovers == []


def test_skip_no_change_and_empty_final(tmp_path):
    p = str(tmp_path / "same.jpg")
    _touch(p)
    e1 = entry(p, "same")          # 与现名相同 → 跳过
    e2 = PlanEntry(path=p)          # final 为空 → 跳过
    result = Applier().apply([e1, e2])
    assert result.ok and result.renamed == []


def test_undo_lists_logs(tmp_path):
    logs = undo.list_undo_logs()
    assert logs == []
    _touch(str(tmp_path / "f.jpg"))
    e = entry(str(tmp_path / "f.jpg"), "g")
    result = Applier().apply([e])
    undo.save_undo_log(result.renamed, str(tmp_path))
    logs = undo.list_undo_logs()
    assert len(logs) == 1
    assert logs[0].count == 1
