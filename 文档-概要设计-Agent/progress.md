# Agent 工程进度

## Current State / 当前状态

- Last Updated：2026-08-26
- 最后更新：2026-08-26
- 当前目标：完成参考材料内容与载体隔离，不回退既有 QA 回流、分章交付和 Word 质检策略
- 活动功能：无；`feat-007 参考材料内容与载体隔离` 已完成

## What's Done / 已完成

- [x] 技术类概要设计八章章节配置与内容边界
- [x] 合同、需求、源码、详细设计和模板的证据分级
- [x] Python/Java 外部源码只读分析与成果目录隔离
- [x] 资料理解台账、模板蒸馏、追踪矩阵和长任务检查点
- [x] 指定外部成果目录发布和源码目录防误写
- [x] DOCX 批注及作者属性清理、全页渲染和视觉确认
- [x] README、START-HERE、策略、工作流、契约、配置和评测用例同步更新
- [x] 参考样本量化蒸馏与样本事实隔离
- [x] 叶子小节深度、重复套话和正式成果泄漏门禁
- [x] 分章 Markdown/DOCX 预览与显式总稿合并
- [x] 修订范围章节哈希校验和 Word 编辑前置检查
- [x] QA 通用经验主题文件、有界索引和候选提升流程
- [x] 参考材料实际内容与文件载体的分层使用规则
- [x] 默认不暴露参考文件名、资料编号、本地路径和编写依赖说明
- [x] 用户显式要求后可启用不含本机绝对路径的逻辑依赖清单
- [x] 章节内部证据注释不进入正式 Markdown 和 DOCX

## What's Next / 后续建议

1. 使用真实合同、模板、参考样本和 Python/Java 源码建立一个新工作区。
2. 观察内容深度门禁在真实项目中的误报情况，只调整阈值，不降低样本隔离和泄漏保护。
3. 新 QA 经验先进入工作区候选清单，经评审后再提升到共享经验索引。
4. 首次在真实项目中启用“写入逻辑依赖”时，复核依赖清单只包含逻辑资源名、用途、必选性、版本或校验信息。

## 风险与约束

- 外部源码、合同和模板只读；不得在原项目目录生成任何成果或缓存。
- Word 的分页受字体和本机 Office/LibreOffice 环境影响，自动结构检查不能替代逐页目视确认。
- Word/WPS 占用与 macOS 文件保护属性只能预检和报告，不能未经授权自动移除。
- 内容深度阈值是通用下限，仍需按章节职责人工复核，不能用字数替代设计判断。
- 技术类概要设计默认不展开数据库详细设计、部署实施、运维和用户操作。
- 参考文件名检查依赖最新资料清单；新增或替换资料后需重新执行 `inspect`。

## 验证证据

- Python 语法：`PYTHONPYCACHEPREFIX=/private/tmp/hld-agent-pycache python3 -m compileall -q agent.py skills/write-high-level-design/scripts`
- Skill 结构：`python3 /Users/xiaochen/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/write-high-level-design`
- 端到端冒烟：`TMPDIR=/private/tmp XDG_CACHE_HOME=/private/tmp/hld-agent-cache python3 skills/write-high-level-design/scripts/run_smoke_test.py`
- Harness：`node /Users/xiaochen/.agents/skills/harness-creator/scripts/validate-harness.mjs --target .`
- 结果：完整冒烟通过；浅层小节、本机路径、资料编号、未授权参考文件名和范围外章节均按预期阻断；显式逻辑依赖开关不放开绝对路径；Harness 为 100/100。
