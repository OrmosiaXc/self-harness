# PPT 构建工程

建议结构：

```text
05-构建工程/
├── sources/
├── notes/
├── images/
├── resources/
├── scripts/
├── exports/
├── analysis/
└── chapters/
```

## 最低要求

- 构建脚本可从头生成 PPTX；
- 每页备注有独立来源；
- 图片有来源和用途；
- 字体与运行依赖有说明；
- 构建阶段输出布局报告；
- 多章节项目按 `chapters/<chapter-id>/` 隔离资料、效果图、构建和 QA；
- 子章节页面只在全局契约的内容区构建，标题区和全局元素由父任务保留；
- 每个子章节交付契约快照、页面清单和独立 QA 证据；
- 正式导出不覆盖旧版本。

通用 PPTX 结构验证脚本位于：

`skills/create-professional-ppt/scripts/validate_editable_pptx.py`
