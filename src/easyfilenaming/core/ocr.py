"""OCR 引擎封装:统一 RapidOCR,懒加载;文件读取走 numpy 缓冲以支持任意编码路径。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


class OcrError(Exception):
    """图片解码或推理失败。"""


@dataclass
class OcrLine:
    """一行 OCR 结果。box 为四点坐标 [[x, y] * 4]。

    几何属性基于包围盒(拍照倾斜时为近似值,同页内行间比较仍成立)。
    """

    box: List[List[float]]
    text: str
    score: float

    @property
    def left(self) -> float:
        return min(p[0] for p in self.box)

    @property
    def right(self) -> float:
        return max(p[0] for p in self.box)

    @property
    def top(self) -> float:
        return min(p[1] for p in self.box)

    @property
    def bottom(self) -> float:
        return max(p[1] for p in self.box)

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def y_center(self) -> float:
        return (self.top + self.bottom) / 2


class OcrEngine:
    """RapidOCR 的薄封装;首次调用才加载模型(冷启动数秒)。"""

    def __init__(self) -> None:
        self._engine = None

    def _ensure(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:  # pragma: no cover - 环境问题
                raise OcrError(
                    "RapidOCR 未安装或加载失败:" + str(exc)
                ) from exc
            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_path: str) -> List[OcrLine]:
        """对单张图片做 OCR,返回行列表;解码失败抛 OcrError。"""
        import cv2
        import numpy as np

        data = np.fromfile(image_path, dtype=np.uint8)  # 支持非 ASCII 路径
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise OcrError("无法解码图片: " + image_path)
        try:
            result, _elapse = self._ensure()(img)
        except OcrError:
            raise
        except Exception as exc:  # 推理链路故障(如 onnxruntime 加载失败)
            raise OcrError("OCR 推理失败: " + repr(exc)) from exc
        lines: List[OcrLine] = []
        if result:
            for box, text, score in result:
                lines.append(
                    OcrLine(box=[[float(x), float(y)] for x, y in box],
                            text=str(text), score=float(score))
                )
        return lines
