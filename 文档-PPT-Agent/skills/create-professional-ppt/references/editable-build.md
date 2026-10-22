# 可编辑 PPT 构建规范

## 工程结构

建议每个 PPT 工程包含：

```text
project/
├── sources/
├── notes/
├── images/
├── resources/
├── scripts/
├── exports/
├── analysis/
└── qa_render/
```

正式交付应保留构建源码、资源、依赖说明和验证报告，使 PPT 可重建。

正式重建以已确认的 CyberPPT 效果图为视觉基准，并同时读取 `slide_content_lock`、`blueprint_component_signature`、`visual_element_registry` 和 `page_manifest`。效果图只用于对照，不能整页贴入 PPTX。

## PptxGenJS 基础规则

- 使用新建的 presentation 实例，设置作者、标题、主题和 16:9 画布。
- 颜色使用不带 `#` 的 6 位十六进制值；透明度使用独立属性。
- 不复用会被库原地修改的 options 对象；用工厂函数返回新对象。
- 列表使用原生 bullet，不在文本中输入 Unicode 圆点。
- 多段文本使用独立段落或 `breakLine`。
- 对齐要求精确时设置 `margin: 0`。
- 文本框使用 `fit: "shrink"`，禁止自动增高突破框体。
- 图片保持比例，使用 contain 或 cover 逻辑并登记实际坐标。
- 每个对象设置稳定的 objectName，便于定位和验证。

## 布局防错

统一封装：

- `addText`：默认字体、内边距、缩小适配、对象命名、文字容量估算；
- `addShape`：坐标登记和对象命名；
- `addImage`：比例计算、替代文本和边界登记；
- `addHeader` / `addFooter`：统一页首页脚；
- `addCard` / `addStep` / `addTable`：复用稳定布局。

构建阶段记录：

- 画布越界；
- 页脚冲突；
- 文字溢出候选；
- 页面对象数量；
- 图片覆盖比例。

静态估算只是早期预警，不能替代渲染。

## 可编辑边界

原生对象优先：

- 标题、正文、注释；
- 流程框和箭头；
- 架构分层；
- 表格、矩阵和时间线；
- PowerPoint 图表；
- 简单曲线和网格。

可使用图片：

- 系统截图；
- 真实分析结果；
- 照片和复杂插图；
- 设计效果图中的局部素材。

不能使用图片：

- 整页截图替代最终页面；
- 把本可用文本和形状构建的流程整体栅格化；
- 无真实数据支撑的结果图。

## 标题留白内容页

使用 `content-only-integration` 时：

- 页面保持完整目标画布，不裁剪也不放大内容；
- 标题区、页码和全局页眉页脚由父任务拥有；
- 子章节只在内容区放置可见对象；
- 背景使用幻灯片背景属性，避免整页形状侵入标题区；
- 页面 ID、标题和最终页码保存在页面清单与标题映射，不靠可见标题定位；
- 合并时保留原生对象和备注，不用截图或缩放页面。

结构验证时启用标题保留区检查，例如：

```bash
python3 scripts/validate_editable_pptx.py chapter.pptx \
  --json report.json \
  --markdown report.md \
  --content-only \
  --reserved-title-height-in 1.15
```

页脚由父任务保留时，再传入 `--reserved-footer-height-in`。

## 演讲者备注

每页备注至少包含：

- 本页目的；
- 推荐讲解顺序；
- 核心口径；
- 证据或来源；
- 易误解边界；
- 下一页衔接。

备注不是页面正文的全文复制。

## 字体

优先选择目标环境已有的中文字体，并提供回退方案。构建和渲染必须使用一致字体配置；最终仍需在用户实际 PowerPoint 环境抽查。
