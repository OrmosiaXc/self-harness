#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parents[3]
AGENT_ENTRY = AGENT_ROOT / "agent.py"
TEST_PROJECT_NAME = "冒烟测试PPT"


def run_command(arguments: list[str], expected_code: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        arguments,
        cwd=AGENT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != expected_code:
        raise AssertionError(
            f"命令退出码异常：{arguments}\n"
            f"期望：{expected_code}，实际：{completed.returncode}\n"
            f"stdout：{completed.stdout}\n"
            f"stderr：{completed.stderr}"
        )
    return completed


def main() -> None:
    run_command([sys.executable, str(AGENT_ENTRY), "validate-agent"])
    with tempfile.TemporaryDirectory(prefix="document-ppt-agent-") as temporary_directory:
        output_root = Path(temporary_directory) / "workspaces"
        run_command(
            [
                sys.executable,
                str(AGENT_ENTRY),
                "new",
                TEST_PROJECT_NAME,
                "--output-root",
                str(output_root),
            ]
        )
        workspace = output_root / TEST_PROJECT_NAME
        state = json.loads((workspace / ".agent" / "state.json").read_text(encoding="utf-8"))
        if state.get("build_mode") != "content-only-integration":
            raise AssertionError("新工作区未继承标题留白内容页模式")
        if state.get("chapter_tasks") != []:
            raise AssertionError("新工作区的子章节任务状态必须为空数组")
        run_command(
            [
                sys.executable,
                str(AGENT_ENTRY),
                "validate-workspace",
                str(workspace),
            ]
        )
        duplicate = run_command(
            [
                sys.executable,
                str(AGENT_ENTRY),
                "new",
                TEST_PROJECT_NAME,
                "--output-root",
                str(output_root),
            ],
            expected_code=1,
        )
        if "禁止覆盖" not in duplicate.stderr:
            raise AssertionError("重复新建工作区没有返回预期的禁止覆盖提示")
    print("文档-PPT-Agent 冒烟测试通过")


if __name__ == "__main__":
    main()
