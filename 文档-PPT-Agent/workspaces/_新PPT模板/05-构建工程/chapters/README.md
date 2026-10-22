# 子章节构建区

父任务按 `chapter-id` 创建独立目录。每个子章节使用以下结构：

```text
chapters/<chapter-id>/
├── 00-task/
├── 01-sources/
├── 02-evidence/
├── 03-content/
├── 04-blueprints/
├── 05-build/
├── 06-qa/
└── 07-delivery/
```

每个目录仅由对应子章节任务写入。父任务只读取交付物、记录验收结论并完成最终集成。

