---
name: write-high-level-design
description: Create, review, revise, and package evidence-backed Chinese software high-level design documents from contracts, templates, reference samples, detailed designs, source code, interfaces, and project materials. Use whenever Codex needs to create or continue a long-running 概要设计/总体设计/HLD task, read source repositories without modifying them, distill reference-document structure without copying project facts, enforce section depth and traceability, generate single-chapter previews, apply scoped revisions, render every DOCX page, or publish Markdown and Word deliverables.
---

# 编写概要设计

将普通用户操作限制为新建工作区、投递资料、确认提纲、提交调整和获取成果。由 Agent 维护资料分类、章节稿、追踪关系、质量报告和内部状态。

## 确定 Agent 根目录

将本 Skill 目录的上两级目录作为 Agent 根目录。所有项目工作区必须位于 `<agent-root>/workspaces/`。

开始文档任务时先读取 `<agent-root>/shared-library/08-经验回流/经验索引.md`，只加载与当前阶段有关的主题；当前用户指令和项目工作区规则优先。

## 执行流程

### 新建文档

1. 运行 `python3 <agent-root>/agent.py new "文档名称"`。
2. 引导用户编辑 `00-任务说明/编写任务.md`。
3. 引导用户把所有普通资料放入 `01-资料投递/所有参考资料放这里/`。
4. 仅把必须套用的 Word 模板放入 `01-资料投递/指定交付模板放这里/`。

### 整理资料和提纲

1. 运行 `python3 <agent-root>/agent.py inspect "文档名称"`，同时生成资料清单和参考样本蒸馏规范。
2. 读取 [source-classification.md](references/source-classification.md)，检查生成的资料使用清单。
3. 读取 [reference-material-boundary.md](references/reference-material-boundary.md)，分离可吸收的材料内容与不得暴露的材料载体信息。
4. 存在外部资料或源码索引时，读取 [evidence-and-code-reading.md](references/evidence-and-code-reading.md)，逐项更新源码与材料理解台账。
5. 存在目录、内容或样式参考时，只采用参考样本蒸馏规范中的结构、密度和图表特征；填写参考样本禁用词并确认不继承项目事实。
6. 存在指定 Word 模板时，读取 [template-word-qa.md](references/template-word-qa.md)，完成模板蒸馏后再写正文。
7. 遇到会改变设计方向的冲突时询问用户；其他缺失写入问题与假设。
8. 运行 `python3 <agent-root>/agent.py outline "文档名称"`。
9. 技术类概要设计模式读取 [technical-spec-profile.md](references/technical-spec-profile.md)，检查八章主线、排除项和模块展开深度。
10. 在标准模式下等待用户确认提纲。

### 编写章节

1. 读取 [content-guidance.md](references/content-guidance.md) 和 [chapter-guidance.md](references/chapter-guidance.md)。
2. 按资料清单和提纲逐章编写 `03-过程成果/02-章节草稿/` 中的文件。
3. 先写事实、证据状态和边界，再写设计结论；资料编号、源码证据、文件名和本地路径只记录在台账、追踪矩阵或章节注释中，不写入面向读者的正文。
4. 系统概要设计中的每个功能模块按七项固定结构展开，不退化为功能清单或源码清单。
5. 叶子小节至少形成两个有效正文块，或使用足够的表格、清单、流程图等结构化内容；避免重复套话和用标题数量代替设计深度。
6. 用户需要逐章查看时运行 `python3 <agent-root>/agent.py render-chapter "文档名称" --chapter <编号> --format all`；不主动合并总文档。
7. 同步更新章节索引、问题与假设、需求追踪矩阵、长任务计划和会话交接。
8. 按 [style-guidance.md](references/style-guidance.md) 统一术语、表格和图表。
9. 长任务开始、阶段切换和会话结束时读取 [long-task-lifecycle.md](references/long-task-lifecycle.md) 并写入检查点。

### 应用调整

1. 运行 `python3 <agent-root>/agent.py revise-plan "文档名称"`。
2. 读取生成的修订影响分析、章节哈希清单和快照。
3. 只修订受影响章节；检查关联的提纲、图表和追踪矩阵。
4. 运行结构质量检查；范围外章节哈希发生变化时停止归档。
5. 运行 `python3 <agent-root>/agent.py revise-done "文档名称" --summary "修改摘要"` 归档调整。

### 交付

1. 读取 [quality-rubric.md](references/quality-rubric.md)。
2. 运行 `python3 <agent-root>/agent.py validate "文档名称" --mode final`。
3. 修复错误级问题；警告需要接受或记录原因。
4. 修改或替换已有 Word 时先运行 `python3 <agent-root>/agent.py preflight-word "文档名称" [--docx <路径>]`。
5. 运行 `python3 <agent-root>/agent.py render "文档名称" --format all`；只有用户明确要求正式合并时执行，指定外部成果目录时使用 `--publish-dir`。
6. 运行 `python3 <agent-root>/agent.py qa "文档名称"`，验证 DOCX 包结构、内容泄漏并渲染全部页面。
7. 逐页检查截图，修复缺字、截断、溢出、孤立标题、空白页、目录和图片问题。
8. 运行 `python3 <agent-root>/agent.py qa "文档名称" --confirm-visual`，完成交付状态。

## 资料使用约束

- 保留用户投递的原始文件，不移动、不重命名、不修改。
- 将目录结构参考限制为标题层级，将内容参考限制为写作角度，将样式参考限制为表达和版式。
- 不将历史样例中的事实、名称、指标或版本写入当前项目。
- 将未确认分类、资料冲突和缺失项显式列出。
- 将项目资料放在项目工作区，不写入本 Skill 的 `references/`。
- 外部源码和资料路径可以登记在索引中，但保持只读；所有分析和文档成果写入工作区或用户明确指定的成果目录。
- 项目专属合同编码、模块清单、算法结论和模板参数写入项目工作区，不写入共享 Skill。
- 参考材料的实际内容可以按其用途和证据强度吸收、改写或转化为正文；不得因隐藏材料载体而丢失有效需求和事实。
- 默认不在正式内容中写文件名、资料编号、本地路径、投递目录或“本文依赖某本地资源”等编写过程说明。
- 只有用户明确要求时，才将 `编写任务.md` 中的“本地资源依赖说明”改为“写入逻辑依赖”；该例外不自动允许本机绝对路径。

## 确定性脚本

- `scripts/new_document.py`：创建标准工作区，不覆盖已有目录。
- `scripts/inspect_sources.py`：扫描和分类资料，保留用户修正。
- `scripts/distill_reference_samples.py`：蒸馏内容、目录和样式参考的结构、密度与图表特征。
- `scripts/build_outline.py`：生成标准提纲、章节骨架和章节索引。
- `scripts/prepare_revision.py`：分析调整意见影响范围并创建修订计划。
- `scripts/complete_revision.py`：归档已处理的调整意见。
- `scripts/validate_document.py`：执行结构或正式交付质量检查。
- `scripts/render_document.py`：合并章节并生成 Markdown/DOCX。
- `scripts/preflight_word.py`：在编辑或替换 Word 前检查占用、权限、扩展属性和包结构。
- `scripts/checkpoint.py`：记录长任务活动项、产物、验证和安全重启点。
- `scripts/qa_document.py`：检查 DOCX 结构、渲染页面并生成 Word 版式质检报告。

## 详细工作规则

需要完整阶段控制时读取 [workflow.md](references/workflow.md)。不要一次加载所有参考文件；只读取当前阶段需要的文件。
