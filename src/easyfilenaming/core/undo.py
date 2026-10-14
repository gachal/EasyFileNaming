"""撤销日志:每次应用改名写一条 JSON 记录,支持列出与恢复。

日志文件位于 <数据目录>/undo/undo-<时间戳>-<序号>.json,
结构:{"folder": str, "time": str, "records": [{"old": abs_path, "new": abs_path}]}
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import List, Tuple

from . import settings as _settings

UNDO_DIR = "undo"


def undo_dir() -> str:
    return os.path.join(_settings.data_dir(), UNDO_DIR)


@dataclass
class UndoLogInfo:
    path: str     # 日志文件绝对路径
    time: str     # 应用时间(本地时间字符串)
    folder: str   # 当时处理的文件夹
    count: int    # 改名条数


def save_undo_log(records: List[dict], folder: str) -> str:
    """写入一条撤销日志,返回日志文件路径。records 为 [{"old","new"}]。"""
    os.makedirs(undo_dir(), exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(
        undo_dir(), "undo-{}-{}.json".format(stamp, len(records))
    )
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(
            undo_dir(), "undo-{}-{}.json".format(stamp, n)
        )
    payload = {
        "folder": folder,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "records": records,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def list_undo_logs() -> List[UndoLogInfo]:
    """列出全部撤销日志,新的在前。损坏的日志跳过。"""
    out: List[UndoLogInfo] = []
    try:
        names = os.listdir(undo_dir())
    except OSError:
        return out
    for name in sorted(names, reverse=True):
        if not name.startswith("undo-") or not name.endswith(".json"):
            continue
        path = os.path.join(undo_dir(), name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            out.append(UndoLogInfo(
                path=path,
                time=str(payload.get("time", "?")),
                folder=str(payload.get("folder", "?")),
                count=len(payload.get("records", [])),
            ))
        except (OSError, ValueError):
            continue
    return out


def restore_log(log_path: str) -> Tuple[int, int, List[str]]:
    """按日志恢复原名(两阶段,可还原交换类改名)。

    阶段一:所有 new → 临时名;阶段二:临时名 → old。
    old 被无关文件占用或 new 已不存在的记录跳过并记入说明。
    返回 (恢复数, 跳过数, 跳过原因列表)。
    """
    with open(log_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    records = [r for r in payload.get("records", []) if r.get("old")
               and r.get("new")]
    restored = 0
    skipped = 0
    notes: List[str] = []
    new_paths = {r["new"] for r in records}

    # 阶段一:可恢复的记录先把 new 挪去临时名
    pending = []  # [(tmp_path, old)]
    for i, rec in enumerate(records):
        old, new = rec["old"], rec["new"]
        if not os.path.exists(new):
            skipped += 1
            notes.append("文件已不在:{}".format(new))
            continue
        if os.path.exists(old) and old not in new_paths:
            skipped += 1
            notes.append("原名已被无关文件占用:{}".format(old))
            continue
        tmp = "{}.efn_undo_{}".format(new, i)
        try:
            os.replace(new, tmp)
            pending.append((tmp, old))
        except OSError as exc:
            skipped += 1
            notes.append("恢复失败 {} : {}".format(new, exc))

    # 阶段二:临时名 → 原名
    for tmp, old in pending:
        try:
            os.replace(tmp, old)
            restored += 1
        except OSError as exc:
            skipped += 1
            notes.append("恢复失败 {} : {}".format(tmp, exc))
    return restored, skipped, notes
