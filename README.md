# EasyFileNaming

按图片内容批量重命名图片文件的桌面工具(macOS + Windows,Windows 兼容 Win7 SP1 64 位)。

选择文件夹 → 本地 OCR 识别(完全离线、免费)→ 预览表确认 → 批量改名 → 可一键撤销。

v1 面向**文档图**(票据/表格/合同拍照件):提取版面标题(如「收益分配表」)作为文件名。实物照片识别(类别清单)规划在 v2。

## 使用

1. `选择文件夹` — 选要处理的目录(可勾选「含子文件夹」,支持 jpg/jpeg/png/bmp/webp);
2. `开始识别` — 后台逐张 OCR,进度条可取消;
3. 预览表 — 「新文件名」列可直接改;黄色「未识别」行可手动补名(留空则保持原名);
4. `应用改名` — 确认后落盘,重名自动加 `-2/-3` 后缀;
5. `撤销…` — 从历史记录恢复整批原名;
6. `自诊断` — 内置样本图跑一次完整识别链,失败可导出报告回传。

## 从源码运行(mac)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-mac.txt -e .
.venv/bin/python main.py
```

## 构建

- **mac**:`bash build/build_mac.sh` → `dist/EasyFileNaming.app`。按架构分别出包(universal2 单包不可行:多数依赖无 universal2 wheel):默认 arm64(Apple Silicon 原生,需 arm64 版 python3.12,如 python.org 官方 pkg);`EFN_MAC_ARCH=x86_64` 出 Intel 包(在 Apple Silicon 上覆盖两代机器,经 Rosetta)。分发前需签名公证,脚本内有命令示例。
- **Windows**:`build\build_win.bat`(需在 Windows 机器上、装有 Python 3.8)→ `dist\EasyFileNaming.exe`
  - 依赖链冻结(onnxruntime 1.12.1 / opencv 4.10 / PyInstaller 5.13.2,见 `docs/adr/0002`),勿随手升级
  - 要求 Win7 **SP1 64 位**;识别链在目标机加载失败时应用会提示运行自诊断,并降级为手动命名模式

## 开发

```bash
.venv/bin/python -m pytest tests/      # 单元测试(核心逻辑全覆盖,无需模型)
.venv/bin/vermin -t=3.8- src/ main.py  # 保证代码兼容 py3.8(Win7 冻结链)
```

代码结构:`src/easyfilenaming/core` 为零 GUI 依赖的业务核心(扫描/OCR/标题提取/改名方案/应用/撤销/设置/自诊断);`src/easyfilenaming/gui` 为 wxPython 界面层。

关键决策见 `docs/adr/`(GUI 单栈选型、Win7 冻结链与盲发对策、识别引擎统一),术语见 `GLOSSARY.md`。
