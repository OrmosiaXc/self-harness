#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PYTHONPYCACHEPREFIX="${TMPDIR:-/private/tmp}/hld-agent-pycache"
export TMPDIR="${TMPDIR:-/private/tmp}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/private/tmp/hld-agent-cache}"
mkdir -p "$PYTHONPYCACHEPREFIX" "$XDG_CACHE_HOME"

echo "=== 文档-概要设计-Agent 初始化检查 ==="
python3 -m compileall -q agent.py skills/write-high-level-design/scripts
python3 /Users/xiaochen/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/write-high-level-design
python3 agent.py --help >/dev/null

if [ "${1:-}" = "--full" ]; then
  python3 skills/write-high-level-design/scripts/run_smoke_test.py
fi

echo "=== 检查通过 ==="
echo "维护 Agent：读取 feature_list.json、progress.md、session-handoff.md。"
echo "编写文档：完整读取 skills/write-high-level-design/SKILL.md。"
echo "Next steps：保持工作目录 clean、restartable，再选择一个未完成功能继续。"
