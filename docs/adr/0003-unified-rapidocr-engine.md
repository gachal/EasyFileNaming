# 识别引擎统一为 RapidOCR

mac 侧本可分叉使用系统自带 Vision 框架(免模型、中文识别强),Win7 侧用 RapidOCR(PaddleOCR 模型转 ONNX)。决定:两平台统一使用 RapidOCR(rapidocr-onnxruntime 1.4.4,PP-OCRv4 mobile 模型约 15MB、Apache-2.0、CPU 单张亚秒级)——同一引擎、同一模型、同一标题提取逻辑;差别只在 lockfile:Win7 冻结 onnxruntime 1.12.1,mac 用新版 onnxruntime,代码不变。

## Considered Options

- mac 用 Vision 分叉:省包体积,但两平台识别结果不一致、维护两套提取逻辑,否决。

## Consequences

- mac 安装包增大几十 MB(模型 + onnxruntime),可接受(已决定模型打进安装包、完全离线)。
- 识别行为跨平台一致,预览结果不受用户所用平台影响。
- mac 侧系统 Vision 框架保留为备选:若实测 RapidOCR 中文质量不满意,再评估启用分叉的代价。
