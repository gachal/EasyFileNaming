# GUI 采用 wxPython 4.2.1 单栈

需求要求 macOS + Windows 且 Windows 兼容 Win7。事实核实(2026-10):Python 3.8 是最后支持 Win7 的版本;Electron 22 / Tauri / .NET 7+ 均已官方放弃 Win7;Qt 系中 PyQt5/PySide2 没有 macOS arm64 wheel(universal2 不可行)。wxPython 4.2.1 同时提供 cp38 的 Windows wheel 与 macOS universal2 wheel(PyPI 已核实),是唯一「单代码库 + 两平台原生运行」的方案。决定:单一 wxPython 4.2.1 + Python 3.8 代码库;识别、改名方案、撤销等业务核心放在独立的无 GUI 依赖包中。

## Considered Options

- PySide2 单栈:表格控件更强,但 mac(Apple Silicon)只能走 Rosetta 2,开发与分发机均为 Apple Silicon,否决。
- PySide2(Win)+ PySide6(mac)混栈:双 GUI 维护、双 CI,未找到同类先例,否决。

## Consequences

- 预览表(千行 + 缩略图 + 行内编辑)需用 wx 虚拟模式列表较笨重地实现,放弃 Qt 模型/视图的精致交互。
- 业务核心包必须保持零 GUI 依赖,为将来更换 GUI 留退路。
- wxPython 4.3.x 起不再提供 py3.8 wheel,本栈停留在 4.2.1 线。
- mac 包按架构分别构建(2026-10-14 修订):universal2 单包不可行——PyPI 上 Pillow/numpy/opencv/onnxruntime 均只发 arm64 与 x86_64 分立 wheel,PyInstaller 报 "not a fat binary";默认构建 arm64,x86_64 包覆盖 Intel mac 与 Apple Silicon(经 Rosetta)。
