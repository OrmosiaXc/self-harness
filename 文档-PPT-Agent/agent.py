#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent
WORKSPACES_ROOT = AGENT_ROOT / "workspaces"
WORKSPACE_TEMPLATE = WORKSPACES_ROOT / "_新PPT模板"
SKILL_ROOT = AGENT_ROOT / "skills" / "create-professional-ppt"
SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")

REQUIRED_AGENT_FILES = (
    "AGENTS.md",
    "README.md",
    "START-HERE.md",
    "feature_list.json",
    "progress.md",
    "session-handoff.md",
    "init.sh",
    "config/quality-gates.yaml",
    "config/skill-dependencies.yaml",
    "skills/create-professional-ppt/SKILL.md",
    "skills/create-professional-ppt/references/cyberppt-blueprint-to-editable.md",
    "skills/create-professional-ppt/references/parallel-chapter-orchestration.md",
    "skills/create-professional-ppt/references/content-only-integration.md",
    "skills/create-professional-ppt/references/shared-build-contract.md",
    "skills/create-professional-ppt/references/prompts.md",
    "skills/create-professional-ppt/references/source-extraction-notes.md",
    "skills/create-professional-ppt/templates/PPT逐页内容目录模板.md",
    "skills/create-professional-ppt/templates/全局构建契约模板.yaml",
    "skills/create-professional-ppt/templates/子章节任务包模板.md",
    "skills/create-professional-ppt/templates/页面标题映射模板.md",
    "skills/create-professional-ppt/templates/子章节交付清单模板.md",
    "skills/create-professional-ppt/templates/父任务集成验收模板.md",
    "skills/create-professional-ppt/templates/构建状态模板.json",
    "skills/create-professional-ppt/scripts/validate_editable_pptx.py",
    "skills/create-professional-ppt/scripts/run_smoke_test.py",
)

REQUIRED_WORKSPACE_FILES = (
    ".agent/state.json",
    "00-任务说明/制作任务.md",
    "00-任务说明/当前状态.md",
    "00-任务说明/长任务计划.md",
    "00-任务说明/会话交接.md",
    "00-任务说明/全局构建契约.yaml",
    "00-任务说明/父任务调度台账.md",
    "01-资料投递/外部资料与源码索引.md",
    "02-资料识别/资料使用清单.md",
    "02-资料识别/事实与证据台账.md",
    "02-资料识别/资料冲突与缺失.md",
    "03-内容规划/PPT逐页内容目录.md",
    "03-内容规划/目录确认记录.md",
    "03-内容规划/技术大纲.md",
    "03-内容规划/子章节任务拆分.md",
    "03-内容规划/页面标题映射.md",
    "04-视觉预览/视觉风格说明.md",
    "04-视觉预览/确认记录.md",
    "04-视觉预览/效果图构建清单.md",
    "05-构建工程/README.md",
    "05-构建工程/chapters/README.md",
    "06-质量检查/视觉QA报告.md",
    "06-质量检查/PPTX结构验证报告.md",
    "06-质量检查/父任务集成验收.md",
    "07-交付成果/交付说明.md",
    "08-调整意见/调整要求.md",
    "08-调整意见/调整记录.md",
)

REQUIRED_WORKSPACE_STATE_FIELDS = (
    "project",
    "status",
    "phase",
    "build_mode",
    "technical_outline_confirmed",
    "global_contract_status",
    "global_contract_version",
    "parallel_chapters",
    "chapter_tasks",
    "integration_status",
)

VALID_BUILD_MODES = {"full-slide", "content-only-integration"}

LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_project_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("PPT 名称不能为空")
    if cleaned in {".", ".."} or any(separator in cleaned for separator in ("/", "\\", "\0")):
        raise ValueError("PPT 名称不能包含路径分隔符或特殊路径")
    if cleaned.startswith("."):
        raise ValueError("PPT 名称不能以点开头")
    return cleaned


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        f"{json.dumps(value, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def create_workspace(name: str, output_root: Path) -> Path:
    project_name = validate_project_name(name)
    target_root = output_root.resolve()
    target = (target_root / project_name).resolve()
    if not is_within(target, target_root):
        raise ValueError("目标目录超出指定工作区根目录")
    if target.exists():
        raise FileExistsError(f"工作区已存在，禁止覆盖：{target}")
    if not WORKSPACE_TEMPLATE.is_dir():
        raise FileNotFoundError(f"缺少工作区模板：{WORKSPACE_TEMPLATE}")

    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WORKSPACE_TEMPLATE, target)
    state_path = target / ".agent" / "state.json"
    state = load_json(state_path)
    if not isinstance(state, dict):
        raise ValueError("工作区状态模板必须是 JSON 对象")
    state.update(
        {
            "project": project_name,
            "status": "received",
            "phase": "task_definition",
            "created_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            "updated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        }
    )
    write_json(state_path, state)
    return target


def validate_required_files(root: Path, required_files: tuple[str, ...]) -> ValidationResult:
    result = ValidationResult()
    for relative_path in required_files:
        path = root / relative_path
        if not path.is_file():
            result.errors.append(f"缺少文件：{relative_path}")
        elif path.stat().st_size == 0:
            result.errors.append(f"文件为空：{relative_path}")
    return result


def validate_json_file(path: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        result.errors.append(f"JSON 无效：{path.relative_to(AGENT_ROOT)}：{error}")
    return result


def validate_skill_frontmatter(skill_path: Path) -> ValidationResult:
    result = ValidationResult()
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "---":
        result.errors.append("SKILL.md 缺少 YAML frontmatter")
        return result
    try:
        end_index = lines.index("---", 1)
    except ValueError:
        result.errors.append("SKILL.md frontmatter 未闭合")
        return result
    frontmatter = "\n".join(lines[1:end_index])
    if not re.search(r"^name:\s*create-professional-ppt\s*$", frontmatter, re.MULTILINE):
        result.errors.append("SKILL.md 的 name 必须是 create-professional-ppt")
    if not re.search(r"^description:\s*\S+", frontmatter, re.MULTILINE):
        result.errors.append("SKILL.md 缺少 description")
    if len(lines) > 500:
        result.warnings.append(f"SKILL.md 共 {len(lines)} 行，建议控制在 500 行以内")
    return result


def validate_skill_links(skill_path: Path) -> ValidationResult:
    result = ValidationResult()
    content = skill_path.read_text(encoding="utf-8")
    for target_value in LINK_PATTERN.findall(content):
        if target_value.startswith(("http://", "https://", "#")):
            continue
        target = (skill_path.parent / target_value).resolve()
        if not is_within(target, SKILL_ROOT):
            result.errors.append(f"SKILL.md 引用超出 Skill 目录：{target_value}")
        elif not target.exists():
            result.errors.append(f"SKILL.md 引用不存在：{target_value}")
    return result


def validate_feature_state(path: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        result.errors.append(f"feature_list.json 无效：{error}")
        return result
    features = value.get("features") if isinstance(value, dict) else None
    if not isinstance(features, list) or not features:
        result.errors.append("feature_list.json 必须包含非空 features 数组")
        return result
    active_count = sum(
        feature.get("status") == "in-progress"
        for feature in features
        if isinstance(feature, dict)
    )
    if active_count > 1:
        result.errors.append("feature_list.json 同时存在多个 in-progress 功能")
    return result


def validate_agent() -> ValidationResult:
    result = validate_required_files(AGENT_ROOT, REQUIRED_AGENT_FILES)
    if result.errors:
        return result
    result.merge(validate_skill_frontmatter(SKILL_ROOT / "SKILL.md"))
    result.merge(validate_skill_links(SKILL_ROOT / "SKILL.md"))
    result.merge(validate_feature_state(AGENT_ROOT / "feature_list.json"))
    for relative_path in (
        "skills/create-professional-ppt/evals/evals.json",
        "skills/create-professional-ppt/templates/构建状态模板.json",
        "workspaces/_新PPT模板/.agent/state.json",
    ):
        result.merge(validate_json_file(AGENT_ROOT / relative_path))
    result.merge(validate_required_files(WORKSPACE_TEMPLATE, REQUIRED_WORKSPACE_FILES))
    return result


def resolve_workspace(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    direct = (AGENT_ROOT / candidate).resolve()
    if direct.exists():
        return direct
    return (WORKSPACES_ROOT / candidate).resolve()


def validate_workspace(path: Path) -> ValidationResult:
    result = ValidationResult()
    resolved = path.resolve()
    if resolved == WORKSPACE_TEMPLATE.resolve():
        result.warnings.append("当前检查的是工作区模板")
    if not resolved.is_dir():
        result.errors.append(f"工作区不存在：{resolved}")
        return result
    result.merge(validate_required_files(resolved, REQUIRED_WORKSPACE_FILES))
    state_path = resolved / ".agent" / "state.json"
    if state_path.is_file() and state_path.stat().st_size > 0:
        try:
            state = load_json(state_path)
            if not isinstance(state, dict):
                result.errors.append("工作区 state.json 必须是 JSON 对象")
            else:
                missing_fields = [
                    field_name
                    for field_name in REQUIRED_WORKSPACE_STATE_FIELDS
                    if field_name not in state
                ]
                result.errors.extend(
                    f"工作区 state.json 缺少字段：{field_name}"
                    for field_name in missing_fields
                )
                build_mode = state.get("build_mode")
                if build_mode not in VALID_BUILD_MODES:
                    result.errors.append(f"工作区 build_mode 无效：{build_mode}")
                if not isinstance(state.get("chapter_tasks"), list):
                    result.errors.append("工作区 chapter_tasks 必须是数组")
        except (OSError, json.JSONDecodeError) as error:
            result.errors.append(f"工作区 state.json 无效：{error}")
    return result


def print_result(result: ValidationResult) -> None:
    for warning in result.warnings:
        print(f"警告：{warning}")
    for error in result.errors:
        print(f"错误：{error}")
    print("检查通过" if result.passed else "检查未通过")


def show_status(workspace: Path) -> None:
    state_path = workspace / ".agent" / "state.json"
    if not state_path.is_file():
        raise FileNotFoundError(f"缺少状态文件：{state_path}")
    state = load_json(state_path)
    print(json.dumps(state, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="文档-PPT-Agent 工作区与结构管理")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="新建 PPT 工作区")
    new_parser.add_argument("name", help="PPT 名称")
    new_parser.add_argument(
        "--output-root",
        type=Path,
        default=WORKSPACES_ROOT,
        help="工作区根目录，默认使用 Agent 内 workspaces",
    )

    subparsers.add_parser("validate-agent", help="验证 Agent 工程结构")

    workspace_parser = subparsers.add_parser("validate-workspace", help="验证 PPT 工作区")
    workspace_parser.add_argument("workspace", help="工作区名称或路径")

    status_parser = subparsers.add_parser("status", help="显示 PPT 工作区状态")
    status_parser.add_argument("workspace", help="工作区名称或路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "new":
        target = create_workspace(args.name, args.output_root)
        result = validate_workspace(target)
        print_result(result)
        if not result.passed:
            raise SystemExit(1)
        print(f"已创建：{target}")
        return
    if args.command == "validate-agent":
        result = validate_agent()
        print_result(result)
        if not result.passed:
            raise SystemExit(1)
        return
    workspace = resolve_workspace(args.workspace)
    if args.command == "validate-workspace":
        result = validate_workspace(workspace)
        print_result(result)
        if not result.passed:
            raise SystemExit(1)
        return
    if args.command == "status":
        show_status(workspace)
        return
    raise AssertionError(f"未处理的命令：{args.command}")


if __name__ == "__main__":
    try:
        main()
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error
