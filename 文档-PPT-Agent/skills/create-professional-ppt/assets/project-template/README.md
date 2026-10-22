# 可编辑 PPT 构建工程起点

本目录提供稳定的工程组件，不包含任何具体项目内容。

- `scripts/pptx_helpers.js`：文本适配、坐标登记、页脚保护和布局报告；
- `resources/fonts.conf`：常见 macOS/Linux 字体目录示例；
- `package.json`：PptxGenJS 构建依赖示例。

启动实际 PPT 工程时可以复制所需文件，然后根据已确认的逐页目录编写项目专用 `build_editable_pptx.js`。不要在通用模板中固化项目页数、标题、单位、指标或算法事实。
