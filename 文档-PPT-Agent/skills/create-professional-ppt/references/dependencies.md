# 依赖与渲染环境

## 推荐运行时

- Node.js；
- PptxGenJS；
- Python 3；
- LibreOffice；
- Poppler `pdftoppm`；
- 可选：Pillow，用于生成总览图；
- 可选：markitdown，用于抽取 PPTX 文本；
- 可选：react-icons、React、sharp，用于生成图标素材。

优先使用工作区或 Codex 已提供的依赖，不无条件安装新包。必须安装时先说明用途和影响。

## 字体

- 先检查目标环境已有字体；
- 为标题、正文、数字和代码标识设置回退；
- 构建和 LibreOffice 渲染使用一致的 Fontconfig；
- 正式交付后在用户实际 PowerPoint 环境抽查代表页。

## 工具入口

```bash
python3 scripts/validate_editable_pptx.py --help
bash scripts/render_and_verify.sh <pptx> <空输出目录> [预期页数] [标题文件]
python3 scripts/make_qa_overviews.py <逐页图片目录> <输出目录>
```

## 安全

- 不把依赖安装到用户源码目录；
- 不打包凭据、令牌、私钥或 Cookie；
- 渲染使用新的空目录，避免混入旧版本页面；
- 外部工具失败时保留日志，不删除已有正式成果。
