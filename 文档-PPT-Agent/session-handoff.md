# Agent 会话交接

## Current Objective / 当前目标

维护一套可直接用于专业、严谨、可编辑 PPT 制作的通用 Agent。

## Current State / 当前状态

- 首版目录、Skill、提示词、工作区模板和验证脚本已构建。
- 已增加 CyberPPT 整套效果图到 PptxGenJS 可编辑重建的双阶段流程。
- 已增加技术大纲、全局构建契约、父任务调度和子章节独立交付体系。
- 已增加标题留白内容页模式、页面标题映射和父任务集成回归。
- 所有项目特有事实均与通用运行规则分离。
- `./init.sh --full`、Skill 校验、Harness 100/100 和真实 PPT 渲染试跑均通过。
- 下一次维护前应先运行 `./init.sh --full`。

## Decisions Made / 已确定的关键决策

1. 技术大纲、全局构建契约与 CyberPPT 效果图是相互独立的阶段门禁。
2. 文档和源码结论必须进入事实台账，不能凭 README 或记忆改写。
3. 领导汇报采用“目的—流程—结果—边界”，算法名只作必要依据。
4. 可编辑性以 PowerPoint 原生对象和 PPTX 结构检查为准，不以“看起来像 PPT”判断。
5. 视觉 QA 必须基于渲染图片，并至少经历一次修复复验。
6. 旧版清理只在新版复制和验证完成后执行。
7. 父任务统一拥有技术大纲、字体、色板、区域、标题、页码和最终集成；子章节只拥有自己的资料、内容、效果图、构建和 QA。
8. 子章节任务采用扁平单层模型，独立写入目录，不通过彼此聊天同步。
9. `content-only-integration` 页面保留空白标题区，只构建内容区，标题由父任务按独立映射添加。

## Files Changed / 关键文件

- `AGENTS.md`
- `skills/create-professional-ppt/`
- `workspaces/_新PPT模板/`
- `agent.py`
- `init.sh`
- `config/quality-gates.yaml`
- `config/skill-dependencies.yaml`
- `skills/create-professional-ppt/references/cyberppt-blueprint-to-editable.md`
- `skills/create-professional-ppt/references/parallel-chapter-orchestration.md`
- `skills/create-professional-ppt/references/content-only-integration.md`
- `skills/create-professional-ppt/references/shared-build-contract.md`

## Next Session Startup / 安全重启

1. 读取 `AGENTS.md`、`feature_list.json`、`progress.md` 和本文件。
2. 运行 `./init.sh --full`。
3. 制作 PPT 时完整读取 `skills/create-professional-ppt/SKILL.md`。
4. 读取技术大纲、全局构建契约、页面标题映射和父任务调度台账。
5. 从对应 `workspaces/<PPT名称>/00-任务说明/当前状态.md` 继续。

## Blockers / Risks / 阻塞项

- 无。

## Validation / 本次验证

- 修改前目标工程 `./init.sh --full`：通过；
- 增强后暂存工程与正式目标工程 `./init.sh --full`：均通过；
- JSON 与 YAML 语法检查：通过；
- `SKILL.md` 187 行，内部引用校验：通过；
- 新工作区创建、必备文件、默认构建模式和重复创建拒绝冒烟测试：通过；
- 标题保留区对象检测单元检查：通过。
- 暂存工程与正式目标目录逐文件比对：一致。

## Recommended Next Step / 推荐下一步

- 使用一个真实的多章节 PPT 项目验证效果图、子章节并行、标题留白页面和父任务合并的完整链路。
