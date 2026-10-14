"""标题提取(版面启发式)的纯逻辑测试。"""
from __future__ import annotations

from easyfilenaming.core.ocr import OcrLine
from easyfilenaming.core.title_extractor import extract_title, sanitize_name


def line(text, score, x, y, w, h):
    box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return OcrLine(box=box, text=text, score=score)


def test_layout_big_title_on_top():
    lines = [
        line("收益分配表", 0.98, 300, 40, 400, 70),   # 大标题
        line("编号 姓名 金额", 0.95, 100, 200, 600, 30),
        line("001 张三 12000", 0.93, 100, 260, 600, 30),
        line("002 李四 8500", 0.92, 100, 320, 600, 30),
        line("合计 20500", 0.94, 100, 380, 400, 30),
    ]
    t = extract_title(lines)
    assert t is not None
    assert t.text == "收益分配表"
    assert t.method == "layout"
    assert t.confidence == 0.98


def test_topline_uniform_document():
    # 普通文档:所有行同高 → 取最靠上的行
    lines = [
        line("会议纪要正文第一行", 0.9, 100, 100, 500, 30),
        line("第二行内容", 0.9, 100, 140, 500, 30),
        line("第三行内容", 0.9, 100, 180, 500, 30),
    ]
    t = extract_title(lines)
    assert t is not None
    assert t.text == "会议纪要正文第一行"
    assert t.method == "topline"


def test_all_low_confidence_returns_none():
    lines = [line("低置信", 0.3, 10, 10, 100, 20)]
    assert extract_title(lines, min_confidence=0.6) is None


def test_empty_lines_returns_none():
    assert extract_title([]) is None
    assert extract_title([line("  ", 0.99, 0, 0, 10, 10)]) is None


def test_illegal_chars_sanitized():
    assert sanitize_name('2026/10 报告:上半年"汇总"') == "202610报告上半年汇总"
    assert sanitize_name("a\\b/c*d?e<f>g|") == "abcdefg"


def test_truncation_max_len():
    long_text = "超" * 50
    lines = [line(long_text, 0.99, 0, 0, 900, 30)]
    t = extract_title(lines, max_len=30)
    assert t is not None
    assert len(t.text) == 30


def test_big_text_outside_top_zone_not_title():
    # 页面下方的大字(如页脚公章)不应当选标题
    lines = [
        line("普通标题行", 0.95, 100, 50, 300, 30),
        line("第一段内容", 0.95, 100, 120, 300, 30),
        line("第二段内容", 0.95, 100, 170, 300, 30),
        line("某某公司专用章", 0.95, 400, 600, 300, 80),  # 下方大字
    ]
    t = extract_title(lines)
    assert t is not None
    assert t.text == "普通标题行"
