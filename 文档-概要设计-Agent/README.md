# 文档-概要设计-Agent

这是一个面向中文软件概要设计文档的可复用 Agent 工程。它把用户操作、公共资源和 Agent 内部实现分开：用户只投递资料或登记外部只读路径、确认提纲、提交调整和获取成果；Agent 负责合同追踪、源码取证、资料分类、参考样本与模板蒸馏、章节拆分、内容深度检查、长任务状态、质量检查、版本快照、Word 全页渲染和正式交付。参考材料的有效内容可以按证据边界进入正文，但文件名、本地路径、资料编号和内部台账默认不对读者暴露。

默认章节配置是“技术类概要设计”，重点覆盖概述、功能与性能需求、系统总体设计、专项体系、逐功能模块概要设计和技术选型边界，不包含数据库详细设计、部署实施、运行维护和用户操作。需要全量九章时可在 `编写任务.md` 中改为“标准全量概要设计”。

主要入口见 `START-HERE.md`。核心能力以 Open Agent Skills 目录格式放在 `skills/write-high-level-design/`。

## 命令入口

通常由 Agent 自动执行，人工排障时可使用：

```bash
python3 agent.py new "项目名称"
python3 agent.py inspect "项目名称"
python3 agent.py distill "项目名称"
python3 agent.py outline "项目名称"
python3 agent.py render-chapter "项目名称" --chapter 3 --format all
python3 agent.py validate "项目名称" --mode structure
python3 agent.py render "项目名称" --format all
python3 agent.py preflight-word "项目名称"
python3 agent.py qa "项目名称"
```

执行 `python3 agent.py --help` 查看完整参数。
