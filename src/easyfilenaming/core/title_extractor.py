"""从 OCR 行集合提取「标题」作为新文件名(版面启发式,纯逻辑,可离线测试)。

规则(按优先级,详见 GLOSSARY「标题」):
1. layout:页面顶部 45% 区域内、行高明显高于同行中位数 → 取行高最大者;
2. topline:行高无显著差异(普通文档)→ 取顶部区域最靠上的行;
3. prefix:以上都取不到有效文本 → 全文拼接截断。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .ocr import OcrLine

#: Windows/mac 文件名非法字符与控制字符
_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WS = re.compile(r"\s+")


@dataclass
class ExtractedTitle:
    text: str        # 清洗后的文件名(不含扩展名)
    method: str      # layout | topline | prefix
    confidence: float  # 所用行的 OCR 置信度


def sanitize_name(text: str) -> str:
    """替换文件名非法字符、去空白(中文命名场景空白无意义)。"""
    return _WS.sub("", _ILLEGAL.sub(" ", text)).strip()


def extract_title(
    lines: List[OcrLine],
    min_confidence: float = 0.6,
    max_len: int = 30,
) -> Optional[ExtractedTitle]:
    """提取标题;无可用文本(全低置信/空)时返回 None,调用方标记「未识别」。"""
    trusted = [
        ln for ln in lines
        if ln.score >= min_confidence and ln.text.strip()
    ]
    if not trusted:
        return None

    top = min(ln.top for ln in trusted)
    bottom = max(ln.bottom for ln in trusted)
    zone_h = max(bottom - top, 1e-6)
    top_zone = [ln for ln in trusted if (ln.top - top) <= 0.45 * zone_h]
    if not top_zone:  # 理论不可达,保守兜底
        top_zone = trusted

    cands = [ln for ln in top_zone if len(ln.text.strip()) >= 2] or top_zone

    tallest = max(cands, key=lambda ln: (ln.height, -ln.y_center, len(ln.text)))
    heights = sorted(ln.height for ln in cands)
    mid = len(heights) // 2
    if len(heights) % 2:
        median_h = heights[mid]
    else:  # 偶数个取中间均值,避免两行时大标题被自己抬高门槛
        median_h = (heights[mid - 1] + heights[mid]) / 2

    if tallest.height >= median_h * 1.15:
        chosen, method = tallest, "layout"
    else:
        chosen = min(cands, key=lambda ln: (ln.y_center, -ln.height))
        method = "topline"

    name = sanitize_name(chosen.text)[:max_len]
    if name:
        return ExtractedTitle(name, method, chosen.score)

    # 兜底:整页拼接前缀
    joined = sanitize_name(
        "".join(ln.text for ln in trusted)
    )[:max_len]
    if not joined:
        return None
    return ExtractedTitle(joined, "prefix", min(ln.score for ln in trusted))
