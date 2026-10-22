# Agent 工程会话交接

## Current Objective / 当前目标

- 目标：在保留既有 QA 回流、分章交付和 Word 质检策略的基础上，将参考材料的实际内容与文件载体信息彻底分离。
- 状态：`feat-007` 已实现并完成临时副本全量验证。
- 分支/提交：本 Agent 为本地目录，当前未依赖 Git 提交。

## Completed This Session / 本轮完成

- 技术类概要设计八章结构，以及功能需求、性能需求、建设原则、建设思路、总体架构、业务流程和数据流程等必备子章节。
- 面向功能点逐项展开功能架构、职责边界、业务流程、处理逻辑、输入输出、异常约束，并与合同追踪矩阵对应。
- 删除数据库详细设计、部署、运维和用户使用内容；技术路线改用“选型依据与决策原则、适用范围与约束、组件引入与变更控制”。
- 新增资料索引、源码与材料理解台账、模板蒸馏、长任务计划、会话交接和 Word 版式质检产物。
- 新增外部源码只读保护、指定成果目录发布、证据状态、检查点和全页 Word QA。
- 新增 `shared-library/08-经验回流/`，采用主题文件加有界索引，项目偏好和项目事实不进入共享层。
- 新增参考样本量化蒸馏，自动提取标题、段落、表格、图片和篇幅特征，不复制样本正文。
- 新增叶子小节深度、重复套话、本机路径、内部产物、参考禁用词和代码式英文标识检查。
- 新增 `render-chapter`、`preflight-word`，总文档只在用户明确要求时合并。
- 修订计划记录全部章节哈希，范围外章节变化会阻止归档。
- 新增参考材料内容/载体边界：已验证的实际内容可进入正文，文件名、资料编号、路径和内部产物默认不进入。
- 新增“本地资源依赖说明”任务开关；只有用户明确要求时允许写入逻辑资源名，绝对路径仍默认禁止。
- 新增正文与 DOCX 载体泄漏扫描，并在正式 Markdown 组装时移除章节内部取证注释。

## 验证证据

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| Python 语法 | `PYTHONPYCACHEPREFIX=/private/tmp/hld-agent-pycache python3 -m compileall -q agent.py skills/write-high-level-design/scripts` | 通过 | 无语法错误 |
| Skill 结构 | `python3 /Users/xiaochen/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/write-high-level-design` | 通过 | `Skill is valid!` |
| 端到端流程 | `TMPDIR=/private/tmp XDG_CACHE_HOME=/private/tmp/hld-agent-cache python3 skills/write-high-level-design/scripts/run_smoke_test.py` | 通过 | 含正式 DOCX、12 页渲染和视觉确认 |
| 专项门禁 | 端到端冒烟内置失败用例 | 通过 | 浅层小节、路径泄漏、范围外章节修改均被阻断 |
| JSON | `find . -name '*.json' -type f -print0 \| xargs -0 -n1 python3 -m json.tool` | 通过 | 所有 JSON 语法有效 |
| Harness | `node /Users/xiaochen/.agents/skills/harness-creator/scripts/validate-harness.mjs --target .` | 通过 | 100/100 |

本轮 `feat-007` 于 2026-08-26 重新执行上述全部验证；冒烟用例新增资料编号、参考文件名、逻辑依赖开关和绝对路径保护检查。

## Files Changed / 主要变更文件

- `AGENTS.md`、`agent/system.md`、`agent/policies/`、`agent/workflows/`：启动、范围、证据和长任务约束。
- `skills/write-high-level-design/SKILL.md` 与 `references/`：技术类概要设计方法、模板和代码阅读路线。
- `skills/write-high-level-design/scripts/` 与 `agent.py`：外部索引、动态章节、检查点、发布保护和 Word QA。
- `shared-library/08-经验回流/`、`agent/workflows/experience-feedback.md`：QA 候选分级、主题文件和索引。
- `distill_reference_samples.py`、`preflight_word.py`：参考样本蒸馏和 Word 编辑预检。
- `reference-material-boundary.md`、`source-output-boundary.md`：参考材料内容吸收、载体隔离和逻辑依赖例外。
- `common.py`、`validate_document.py`、`qa_document.py`、`render_document.py`：内容深度、载体泄漏、内部注释清理、分章预览和章节哈希边界。
- `workspaces/_新文档模板/`：任务、计划、索引、理解台账、模板蒸馏、追踪矩阵和质检产物。
- `contracts/`、`config/`、`evals/`：输入、资料清单、质量门禁和回归用例。
- `feature_list.json`、`progress.md`、`session-handoff.md`、`init.sh`：Agent 工程自身的可续作 Harness。

## 关键决策

- 项目源码只作为证据读取，所有分析和交付产物写入 Agent 工作区或用户明确指定的成果目录。
- 合同事实、源码现状、目标设计和待确认项采用不同证据状态，不把源码实现直接等同于合同目标。
- 技术类概要设计采用八章配置；原九章标准配置仍保留为显式可选项。
- DOCX 清理采用保留原 XML 命名空间的定点替换，避免破坏 Office 兼容性。
- 当前用户和工作区规则优先于共享 QA 经验；另一个项目的清理授权不得继承。
- 参考样本只用于形式和内容展开方式，必须配置禁用词并在正式输出中执行泄漏扫描。
- 历史版本默认保留；即使工作区选择只保留当前版，删除仍需用户明确指令。
- 隐藏参考材料载体不得导致需求、事实和技术说明丢失；二者分别由证据边界和交付泄漏门禁控制。
- 资料编号只保留在章节 HTML 注释、台账和追踪矩阵中；正式 Markdown 与 DOCX 不携带该内部取证信息。

## Blockers / Risks / 阻塞与风险

- 当前无阻塞。
- 首次真实项目需观察章节深度阈值和参考文件名门禁是否存在误报，并继续验证复杂 Word 模板和 macOS 文件保护场景。

## Next Session / 下次启动

1. 阅读 `AGENTS.md`、`feature_list.json` 和 `progress.md`。
2. 阅读本文件确认真实项目验证是否已经执行。
3. 运行 `./init.sh` 建立快速基线；进行交付前运行 `./init.sh --full`。
4. 若是编写文档任务，完整读取 `skills/write-high-level-design/SKILL.md` 和经验索引，再从工作区状态继续。

## Recommended Next Step / 推荐下一步

- 用真实资料新建工作区，验证参考材料实际内容保留、载体隔离、参考样本蒸馏、分章预览和完整 Word 交付闭环。
