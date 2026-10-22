#!/usr/bin/env bash
set -euo pipefail

agent_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${agent_root}"

export PYTHONPYCACHEPREFIX="${TMPDIR:-/private/tmp}/document-ppt-agent-pycache"
mkdir -p "${PYTHONPYCACHEPREFIX}"

echo "=== 文档-PPT-Agent 初始化检查 ==="
python3 -m compileall -q agent.py skills/create-professional-ppt/scripts
python3 agent.py validate-agent

quick_validate="${PPT_SKILL_QUICK_VALIDATE:-}"
if [[ -n "${quick_validate}" && -f "${quick_validate}" ]]; then
  python3 "${quick_validate}" skills/create-professional-ppt
else
  echo "提示：未配置 PPT_SKILL_QUICK_VALIDATE，已使用 Agent 内部 Skill 校验。"
fi

if [[ "${1:-}" == "--full" ]]; then
  python3 skills/create-professional-ppt/scripts/run_smoke_test.py
fi

echo "=== 检查通过 ==="
echo "制作 PPT：完整读取 skills/create-professional-ppt/SKILL.md。"
echo "维护 Agent：读取 feature_list.json、progress.md 和 session-handoff.md。"
