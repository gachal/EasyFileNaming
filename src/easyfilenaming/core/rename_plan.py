"""改名方案:识别结果 → 旧名/新名映射,含清洗、重名去重、与现有文件的冲突处理。"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .settings import Settings
from .title_extractor import ExtractedTitle

# 行状态
ST_OK = "已识别"
ST_UNRECOGNIZED = "未识别"
ST_NO_CHANGE = "无需改名"
ST_DONE = "已改名"
ST_FAILED = "失败"


@dataclass
class PlanEntry:
    path: str                       # 原绝对路径
    proposed: Optional[str] = None  # 识别建议名(已清洗截断)
    status: str = ST_UNRECOGNIZED
    confidence: float = 0.0
    method: str = ""
    final: Optional[str] = None     # 去重后的最终名(不含扩展名);应用阶段使用
    note: str = ""

    @property
    def directory(self) -> str:
        return os.path.dirname(self.path)

    @property
    def ext(self) -> str:
        return os.path.splitext(self.path)[1]

    @property
    def stem(self) -> str:
        return os.path.splitext(os.path.basename(self.path))[0]


@dataclass
class RenamePlan:
    entries: List[PlanEntry] = field(default_factory=list)
    folder: str = ""

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.entries:
            out[e.status] = out.get(e.status, 0) + 1
        return out


def _fs_case_insensitive() -> bool:
    # Windows 与 macOS 默认卷均大小写不敏感
    return os.name == "nt" or sys.platform == "darwin"


def _with_date(name: str, path: str) -> str:
    import time
    try:
        stamp = time.strftime("%Y%m%d", time.localtime(os.path.getmtime(path)))
    except OSError:
        return name
    return "{}-{}".format(name, stamp)


def build_plan(
    folder: str,
    paths: List[str],
    titles: Dict[str, Optional[ExtractedTitle]],
    settings: Settings,
    case_insensitive: Optional[bool] = None,
) -> RenamePlan:
    """把识别结果组装成改名方案。

    - 未识别/标题为空 → ST_UNRECOGNIZED,final 留空(预览表可人工填);
    - 建议名与现名相同 → ST_NO_CHANGE;
    - 重名:同目录冲突(含未参与改名的现有文件)自动追加 -2/-3…;
    - append_date 打开时在名称后追加文件修改日期(日期不同则不冲突)。
    """
    ci = _fs_case_insensitive() if case_insensitive is None else case_insensitive
    plan = RenamePlan(folder=folder)
    for path in paths:
        title = titles.get(path)
        entry = PlanEntry(path=path)
        if title is None:
            plan.entries.append(entry)
            continue
        name = title.text
        if settings.append_date:
            name = _with_date(name, path)
        entry.proposed = name
        entry.confidence = title.confidence
        entry.method = title.method
        # 全等才算「无需改名」:大小写-only 差异也算改名(规范化命名)
        entry.final = name
        entry.status = ST_NO_CHANGE if entry.stem == name else ST_OK
        plan.entries.append(entry)

    _deduplicate(plan, ci)
    return plan


def _deduplicate(plan: RenamePlan, ci: bool) -> None:
    """同目录内去重:先登记目录里不参与改名的现有文件名。"""
    by_dir: Dict[str, List[PlanEntry]] = {}
    for e in plan.entries:
        by_dir.setdefault(e.directory, []).append(e)

    for directory, entries in by_dir.items():
        renaming = {e.path for e in entries}
        used = set()
        try:
            existing = os.listdir(directory)
        except OSError:
            existing = []
        for name in existing:
            if os.path.join(directory, name) in renaming:
                continue
            used.add(name.lower() if ci else name)

        for e in entries:
            if not e.final or e.status != ST_OK:
                continue
            key = (e.final + e.ext).lower() if ci else (e.final + e.ext)
            if key in used:
                n = 2
                while True:
                    cand = "{}-{}{}".format(e.final, n, e.ext)
                    ckey = cand.lower() if ci else cand
                    if ckey not in used:
                        e.final = "{}-{}".format(e.final, n)
                        key = ckey
                        break
                    n += 1
            used.add(key)
