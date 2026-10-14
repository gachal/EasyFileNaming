"""自诊断:用内置样本图跑一次完整 OCR 链路,产出环境报告(ADR-0002 盲发兜底)。"""
from __future__ import annotations

import os
import platform
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import List

from .. import __version__
from .ocr import OcrEngine, OcrError
from .settings import data_dir

SAMPLE_NAME = "diagnostic_sample.jpg"


def sample_path() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "resources", SAMPLE_NAME)


@dataclass
class DiagnosticReport:
    ok: bool = False
    error: str = ""
    seconds: float = 0.0
    ocr_lines: List[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)


def run_diagnostic() -> DiagnosticReport:
    report = DiagnosticReport(env=_env_info())
    start = time.time()
    try:
        engine = OcrEngine()
        lines = engine.recognize(sample_path())
        report.ocr_lines = [ln.text for ln in lines]
        report.seconds = round(time.time() - start, 2)
        if not lines:
            report.ok = False
            report.error = "OCR 跑通但没有识别出任何文字(样本图异常?)"
        else:
            report.ok = True
    except OcrError as exc:
        report.error = str(exc)
    except Exception:
        report.error = traceback.format_exc(limit=8)
    report.seconds = round(time.time() - start, 2)
    return report


def _env_info() -> dict:
    info = {
        "app_version": __version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "system_encoding": sys.getfilesystemencoding(),
    }
    try:
        import onnxruntime
        info["onnxruntime"] = onnxruntime.__version__
    except Exception:
        info["onnxruntime"] = "加载失败"
    try:
        import cv2
        info["opencv"] = cv2.__version__
    except Exception:
        info["opencv"] = "加载失败"
    return info


def report_text(report: DiagnosticReport) -> str:
    lines = [
        "EasyFileNaming 自诊断报告",
        "=" * 40,
        "结果: " + ("通过" if report.ok else "失败"),
        "耗时: {} 秒".format(report.seconds),
        "错误: " + (report.error or "无"),
        "",
        "环境:",
    ]
    lines += ["  {}: {}".format(k, v) for k, v in report.env.items()]
    lines += ["", "样本图识别文本:"]
    sample = ["  " + t for t in report.ocr_lines]
    lines += sample or ["  (无)"]
    return "\n".join(lines)


def write_report(report: DiagnosticReport) -> str:
    """把报告写入数据目录,返回文件路径(供用户回传)。"""
    os.makedirs(data_dir(), exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(data_dir(), "diagnostic-{}.txt".format(stamp))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_text(report))
    return path
