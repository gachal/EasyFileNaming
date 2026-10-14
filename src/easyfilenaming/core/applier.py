"""两阶段应用改名:先全部改为临时名,再改为最终名。

两阶段可安全处理交换改名(a→b 且 b→a)与大小写-only 改名
(大小写不敏感文件系统上直接 rename 会失败或互相覆盖)。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .rename_plan import PlanEntry
from .scanner import TMP_PREFIX

ProgressCb = Optional[Callable[[int, int], None]]


@dataclass
class Failure:
    path: str
    stage: str  # phase1 | phase2 | rollback
    error: str


@dataclass
class ApplyResult:
    renamed: List[dict] = field(default_factory=list)   # [{"old":..,"new":..}]
    failed: List[Failure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


class Applier:
    def apply(
        self,
        entries: List[PlanEntry],
        progress: ProgressCb = None,
    ) -> ApplyResult:
        """执行改名。entries 里只处理 final 非空且与现名不同的行。

        单个文件失败不影响其余文件;phase2 失败时尽力回滚为原名。
        返回结果同时携带可直接写盘的撤销记录(renamed 列表)。
        """
        result = ApplyResult()
        actions: List[PlanEntry] = []
        for e in entries:
            if not e.final:
                continue
            if e.final == e.stem:
                continue
            actions.append(e)

        total = len(actions)
        # 阶段一:原名 → 临时名
        tmp_paths: List[Optional[str]] = []
        for i, e in enumerate(actions):
            if progress:
                progress(i, total)
            tmp = os.path.join(
                e.directory, "{}{}{}".format(TMP_PREFIX, i, e.ext)
            )
            try:
                os.replace(e.path, tmp)
                tmp_paths.append(tmp)
            except OSError as exc:
                tmp_paths.append(None)
                result.failed.append(
                    Failure(e.path, "phase1", str(exc))
                )
        # 阶段二:临时名 → 最终名
        for i, e in enumerate(actions):
            tmp = tmp_paths[i]
            if tmp is None:
                continue
            dst = os.path.join(e.directory, e.final + e.ext)
            try:
                os.replace(tmp, dst)
                result.renamed.append({"old": e.path, "new": dst})
            except OSError as exc:
                result.failed.append(
                    Failure(e.path, "phase2", str(exc))
                )
                try:  # 尽力还原原名,避免留下 .efn_tmp_ 文件
                    os.replace(tmp, e.path)
                except OSError:
                    result.failed.append(
                        Failure(e.path, "rollback", "临时文件留在:" + tmp)
                    )
        if progress:
            progress(total, total)
        return result
