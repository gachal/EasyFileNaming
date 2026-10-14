"""扫描文件夹,收集待识别的图片文件。"""
from __future__ import annotations

import os
from typing import List

#: 支持的图片扩展名(v1 不含 heic,见 GLOSSARY 决策)
SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

#: 应用自身的两阶段改名临时前缀(core.applier 使用)
TMP_PREFIX = ".efn_tmp_"


def scan_folder(folder: str, recursive: bool = True) -> List[str]:
    """返回待处理图片的绝对路径列表,按路径排序。

    跳过隐藏文件/目录与应用临时文件(TMP_PREFIX 前缀)。
    """
    found: List[str] = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                path = os.path.join(root, name)
                if _is_target(path):
                    found.append(path)
    else:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and _is_target(path):
                found.append(path)
    return sorted(found)


def _is_target(path: str) -> bool:
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    return (
        not name.startswith(".")
        and not name.startswith(TMP_PREFIX)
        and ext in SUPPORTED_EXTS
    )
