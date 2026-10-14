"""用户设置:JSON 持久化于平台数据目录。"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Settings:
    recursive: bool = True          # 递归处理子文件夹
    min_confidence: float = 0.6     # OCR 行置信度阈值,低于则不参与标题提取
    max_title_len: int = 30         # 文件名最大字符数
    append_date: bool = False       # 名称后追加文件修改日期(YYYYMMDD)
    diagnostic_ok: Optional[bool] = None  # 首次自诊断结果(ADR-0002)


def data_dir() -> str:
    """平台数据目录(配置与撤销日志都放这里)。"""
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "EasyFileNaming")
    if os.uname().sysname == "Darwin":  # macOS
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support",
            "EasyFileNaming",
        )
    return os.path.join(os.path.expanduser("~"), ".easyfilenaming")


def settings_path() -> str:
    return os.path.join(data_dir(), "settings.json")


def load() -> Settings:
    try:
        with open(settings_path(), "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        known = set(Settings.__dataclass_fields__)
        return Settings(**{k: v for k, v in raw.items() if k in known})
    except (OSError, ValueError):
        return Settings()


def save(s: Settings) -> None:
    os.makedirs(data_dir(), exist_ok=True)
    tmp = settings_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(asdict(s), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, settings_path())
