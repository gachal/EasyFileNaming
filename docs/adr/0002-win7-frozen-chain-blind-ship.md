# Win7 冻结依赖链与盲发风险对策

Win7 上 Python 仅剩 3.8(2024-10 EOL),onnxruntime 官方只测试 Win10/Server 2019,社区确认 ≤1.12.x 是能在 Win7 SP1 上加载的最后一线(1.15 起源码编译都不支持 Win7;1.12.1 提供 cp38 的 win32/win_amd64 wheel),PyInstaller 官方只支持 Win8+、需锁 5.13.2。而开发方只有 Apple Silicon mac(虚拟机无法运行 x86 Win7),**没有任何真机 Win7 验证条件**(用户已确认)。决定:Windows 构建整链冻结(python 3.8 + onnxruntime 1.12.1 + rapidocr-onnxruntime 1.4.4 + opencv-python 4.10.0.84〔最后支持 py3.8 的版本〕+ wxPython 4.2.1 + PyInstaller 5.13.2),版本写入 lockfile 不再升级;所有 ONNX 模型导出时 opset 钉在 ≤16(onnxruntime 1.12 的算子上限);首次启动内置自诊断——用打包内样本图跑一次完整 OCR,失败则生成含环境信息的日志供用户回传;README 明示「需 Win7 SP1 64 位」。

## Consequences

- 冻结链无安全更新;任何依赖升级都要当作破坏性变更对待。
- 灰度策略已确认(2026-10-14):用户选择直接正式发布、不做灰度验证。因此自诊断、错误提示引导回传日志、以及「识别链加载失败时降级为无 AI 的规则重命名模式」从兜底手段升级为 v1 必备功能。
- 若真机上链路不通,兜底方案是降级为「无 AI 的规则重命名」模式,而非整包不可用。
