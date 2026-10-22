from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from common import current_timestamp, document_name, load_state, resolve_workspace, state_file, write_human_status


@dataclass(frozen=True)
class Checkpoint:
    step: str
    status: str
    next_action: str
    artifacts: tuple[str, ...]
    verification: str
    blocker: str


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def append_plan_checkpoint(workspace: Path, checkpoint: Checkpoint, timestamp: str) -> None:
    plan_path = workspace / "00-任务说明" / "长任务计划.md"
    content = plan_path.read_text(encoding="utf-8") if plan_path.exists() else "# 长任务计划\n"
    if "## 检查点记录" not in content:
        content = content.rstrip() + "\n\n## 检查点记录\n\n| 时间 | 工作项 | 状态 | 验证 | 下一步 |\n|---|---|---|---|---|\n"
    row = (
        f"| {timestamp} | {escape_table_cell(checkpoint.step)} | {checkpoint.status} | "
        f"{escape_table_cell(checkpoint.verification)} | {escape_table_cell(checkpoint.next_action)} |\n"
    )
    plan_path.write_text(content.rstrip() + "\n" + row, encoding="utf-8")


def write_handoff(workspace: Path, state: dict, checkpoint: Checkpoint) -> None:
    artifacts = state.get("artifacts", [])
    completed = state.get("completed_steps", [])
    lines = [
        "# 会话交接",
        "",
        "## 当前状态",
        "",
        f"- 文档：{state['document_name']}",
        f"- 阶段：{state['phase']}",
        f"- 完成度：{state['completion']}%",
        f"- 当前工作项：{state['active_work_item']}",
        "",
        "## 已完成步骤",
        "",
        *([f"- {item}" for item in completed] or ["- 尚无已完成步骤"]),
        "",
        "## 关键文件",
        "",
        *([f"- `{item}`" for item in artifacts] or ["- 尚无已登记产物"]),
        "",
        "## 验证证据",
        "",
        f"- {state['last_verification']}",
        "",
        "## 遗留问题",
        "",
        f"- {checkpoint.blocker}",
        "",
        "## 下一会话第一步",
        "",
        checkpoint.next_action,
        "",
    ]
    (workspace / "00-任务说明" / "会话交接.md").write_text("\n".join(lines), encoding="utf-8")


def record_checkpoint(workspace: Path, checkpoint: Checkpoint) -> dict:
    previous = load_state(workspace)
    timestamp = current_timestamp()
    completed_steps = list(previous.get("completed_steps", []))
    if checkpoint.status == "completed" and checkpoint.step not in completed_steps:
        completed_steps.append(checkpoint.step)
    artifacts = list(dict.fromkeys([*previous.get("artifacts", []), *checkpoint.artifacts]))
    history = list(previous.get("history", []))
    history.append(
        {
            "step": checkpoint.step,
            "status": checkpoint.status,
            "verification": checkpoint.verification,
            "updated_at": timestamp,
        }
    )
    state = {
        "schema_version": "1.0",
        "document_name": document_name(workspace),
        "phase": previous.get("phase", "writing"),
        "completion": previous.get("completion", 0),
        "active_work_item": checkpoint.step,
        "completed_steps": completed_steps,
        "artifacts": artifacts,
        "last_verification": checkpoint.verification or previous.get("last_verification", "尚未执行"),
        "next_action": checkpoint.next_action,
        "blocker": checkpoint.blocker,
        "safe_restart": "读取编写任务、当前状态、长任务计划、会话交接和本状态文件",
        "history": history[-50:],
        "updated_at": timestamp,
    }
    target = state_file(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_human_status(workspace, state)
    append_plan_checkpoint(workspace, checkpoint, timestamp)
    write_handoff(workspace, state, checkpoint)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="记录概要设计长任务检查点")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--step", required=True, help="当前或刚完成的工作项")
    parser.add_argument("--status", choices=("in_progress", "completed", "blocked"), required=True)
    parser.add_argument("--next", dest="next_action", required=True, help="下一步唯一动作")
    parser.add_argument("--artifact", action="append", default=[], help="本阶段产物，可重复传入")
    parser.add_argument("--verification", default="尚未执行", help="验证命令或结果")
    parser.add_argument("--blocker", default="无", help="真实阻塞事项")
    args = parser.parse_args()
    workspace = resolve_workspace(args.workspace)
    checkpoint = Checkpoint(
        step=args.step,
        status=args.status,
        next_action=args.next_action,
        artifacts=tuple(args.artifact),
        verification=args.verification,
        blocker=args.blocker,
    )
    state = record_checkpoint(workspace, checkpoint)
    print(f"检查点已记录：{state_file(workspace)}")
    print(f"下一步：{state['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
