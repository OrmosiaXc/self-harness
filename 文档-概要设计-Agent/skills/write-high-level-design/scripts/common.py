from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


AGENT_ROOT_ENV = "HLD_AGENT_ROOT"
INVALID_NAME_PATTERN = re.compile(r"[\\/:*?\"<>|]")
CONFIG_VALUE_SEPARATOR = re.compile(r"[，,、；;\n]+")
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![\w.])/(?:Users|private/(?:var|tmp)|var/folders)/[^\s<>'\"`|]+"),
    re.compile(r"\b[A-Za-z]:\\Users\\[^\s<>'\"`|]+", re.IGNORECASE),
    re.compile(r"\bfile://[^\s<>'\"`|]+", re.IGNORECASE),
)
INTERNAL_ARTIFACT_PATTERN = re.compile(
    r"(?<![\w.-])(?:workspaces/|\.agent/|qa/|HLD_AGENT_ROOT|"
    r"源码与材料理解台账|模板蒸馏规范|长任务计划|会话交接)(?![\w.-])",
    re.IGNORECASE,
)
CODE_IDENTIFIER_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9]*(?:Controller|ServiceImpl|Service|Repository|Mapper|Manager|Handler|Client|Dao|DTO|VO|PO|Entity)\b"
)
REFERENCE_DEPENDENCY_PATTERNS = (
    re.compile(
        r"(?:本文档|本章节|本章|本节|本报告).{0,12}(?:编写|生成).{0,12}"
        r"(?:依赖|参考|引用|使用|读取).{0,32}(?:本地|参考)?(?:资料|资源|文件)"
    ),
    re.compile(
        r"(?:编写|生成)(?:本|该)?(?:文档|章节|内容).{0,24}"
        r"(?:依赖|参考|引用|使用|读取).{0,24}(?:本地|参考)?(?:资料|资源|文件)"
    ),
)


def agent_root() -> Path:
    configured_root = os.environ.get(AGENT_ROOT_ENV)
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def validate_document_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ValueError("文档名称不能为空")
    if len(normalized) > 100:
        raise ValueError("文档名称不能超过 100 个字符")
    if normalized in {".", "..", "_新文档模板"} or INVALID_NAME_PATTERN.search(normalized):
        raise ValueError("文档名称包含不允许的路径字符")
    return normalized


def ensure_within(path: Path, root: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"路径不在允许范围内：{resolved_path}")
    return resolved_path


def resolve_workspace(value: str | Path) -> Path:
    root = agent_root()
    raw_path = Path(value).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [Path.cwd() / raw_path, root / "workspaces" / raw_path, root / raw_path]
    existing = next((candidate for candidate in candidates if candidate.exists()), None)
    workspace = (existing or (root / "workspaces" / raw_path)).resolve()
    allowed_roots = (root / "workspaces", root / "examples")
    if not any(workspace == allowed.resolve() or allowed.resolve() in workspace.parents for allowed in allowed_roots):
        raise ValueError("工作区必须位于 workspaces/ 或 examples/ 中")
    if workspace.name == "_新文档模板":
        raise ValueError("不能直接操作新文档模板")
    if not workspace.exists():
        raise FileNotFoundError(f"工作区不存在：{workspace}")
    return workspace


def read_task_fields(workspace: Path) -> dict[str, str]:
    task_file = workspace / "00-任务说明" / "编写任务.md"
    if not task_file.exists():
        return {}
    fields: dict[str, str] = {}
    for line in task_file.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^-\s*([^：:]+)[：:]\s*(.*)$", line.strip())
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def split_config_values(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in CONFIG_VALUE_SEPARATOR.split(value) if item.strip()))


def local_resource_dependency_enabled(task_fields: dict[str, str]) -> bool:
    configured = task_fields.get("本地资源依赖说明", "不写入").strip()
    return "写入" in configured and "不写入" not in configured


def source_carrier_terms(workspace: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    manifest_path = workspace / ".agent" / "source-manifest" / "source-manifest.json"
    if not manifest_path.exists():
        return (), ()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return (), ()

    file_names: set[str] = set()
    source_ids: set[str] = set()
    for source in manifest.get("sources", []):
        source_id = str(source.get("source_id", "")).strip()
        if source_id:
            source_ids.add(source_id)
        raw_path = str(source.get("relative_path", "")).strip()
        if raw_path.startswith("外部只读："):
            raw_path = raw_path[len("外部只读："):].strip()
        file_name = raw_path.replace("\\", "/").rstrip("/").rsplit("/", maxsplit=1)[-1]
        if len(file_name) >= 4:
            file_names.add(file_name)
    return tuple(sorted(file_names)), tuple(sorted(source_ids))


def exact_term_present(text: str, term: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9_-]+", term):
        return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(term)}(?![A-Za-z0-9_-])", text) is not None
    return term in text


def content_safety_findings(
    text: str,
    task_fields: dict[str, str],
    source_file_names: tuple[str, ...] = (),
    source_ids: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for pattern in ABSOLUTE_PATH_PATTERNS:
        findings.extend(("LOCAL_PATH_LEAK", match.group(0)) for match in pattern.finditer(text))
    findings.extend(("INTERNAL_ARTIFACT_LEAK", match.group(0)) for match in INTERNAL_ARTIFACT_PATTERN.finditer(text))
    findings.extend(("CODE_IDENTIFIER_EXPOSED", match.group(0)) for match in CODE_IDENTIFIER_PATTERN.finditer(text))
    findings.extend(("SOURCE_ID_EXPOSED", source_id) for source_id in source_ids if exact_term_present(text, source_id))
    if not local_resource_dependency_enabled(task_fields):
        findings.extend(("REFERENCE_FILE_EXPOSED", file_name) for file_name in source_file_names if exact_term_present(text, file_name))
        for pattern in REFERENCE_DEPENDENCY_PATTERNS:
            findings.extend(("REFERENCE_DEPENDENCY_EXPOSED", match.group(0)) for match in pattern.finditer(text))
    for forbidden_term in split_config_values(task_fields.get("参考样本禁用词", "")):
        if forbidden_term in text:
            findings.append(("REFERENCE_TERM_LEAK", forbidden_term))
    return list(dict.fromkeys(findings))


def document_name(workspace: Path) -> str:
    return read_task_fields(workspace).get("文档名称") or workspace.name


def state_file(workspace: Path) -> Path:
    return workspace / ".agent" / "state.json"


def load_state(workspace: Path) -> dict[str, Any]:
    target = state_file(workspace)
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def update_state(
    workspace: Path,
    phase: str,
    completion: int,
    next_action: str,
    blocker: str = "无",
    active_work_item: str | None = None,
    artifact: str | None = None,
    verification: str | None = None,
) -> None:
    target = state_file(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = load_state(workspace)
    artifacts = list(dict.fromkeys([*previous.get("artifacts", []), *([artifact] if artifact else [])]))
    history = list(previous.get("history", []))
    if previous.get("updated_at"):
        history.append(
            {
                "phase": previous.get("phase", ""),
                "completion": previous.get("completion", 0),
                "active_work_item": previous.get("active_work_item", ""),
                "updated_at": previous.get("updated_at", ""),
            }
        )
    history = history[-20:]
    state: dict[str, Any] = {
        "schema_version": "1.0",
        "document_name": document_name(workspace),
        "phase": phase,
        "completion": completion,
        "active_work_item": active_work_item or previous.get("active_work_item") or next_action,
        "completed_steps": previous.get("completed_steps", []),
        "artifacts": artifacts,
        "last_verification": verification or previous.get("last_verification", "尚未执行"),
        "next_action": next_action,
        "blocker": blocker,
        "safe_restart": "读取编写任务、当前状态、长任务计划、会话交接和本状态文件",
        "history": history,
        "updated_at": current_timestamp(),
    }
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_human_status(workspace, state)


def write_human_status(workspace: Path, state: dict[str, Any]) -> None:
    phase_names = {
        "created": "已创建",
        "sources_classified": "资料已识别",
        "outline_pending": "提纲待确认",
        "writing": "编写中",
        "revision_planned": "调整影响已分析",
        "reviewing": "评审中",
        "ready_to_deliver": "待交付",
        "qa_pending": "Word 质检中",
        "completed": "已完成",
    }
    content = (
        "# 当前状态\n\n"
        f"- 文档：{state['document_name']}\n"
        f"- 阶段：{phase_names.get(str(state['phase']), state['phase'])}\n"
        f"- 完成度：{state['completion']}%\n"
        f"- 最近更新：{state['updated_at']}\n"
        f"- 当前工作项：{state.get('active_work_item', state['next_action'])}\n"
        f"- 下一步：{state['next_action']}\n"
        f"- 阻塞事项：{state.get('blocker', '无')}\n"
        f"- 最近验证：{state.get('last_verification', '尚未执行')}\n"
        f"- 安全重启：{state.get('safe_restart', '读取工作区状态文件')}\n"
    )
    status_file = workspace / "00-任务说明" / "当前状态.md"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(content, encoding="utf-8")


@dataclass(frozen=True)
class Chapter:
    number: int
    title: str
    sections: tuple[str, ...]

    @property
    def filename(self) -> str:
        return f"{self.number:02d}-{self.title}.md"


STANDARD_CHAPTERS = (
    Chapter(1, "引言", ("编写目的", "项目背景", "文档范围", "术语与缩写", "参考资料")),
    Chapter(2, "项目与系统概述", ("建设目标", "系统边界", "用户与角色", "相关系统", "业务场景", "设计约束")),
    Chapter(3, "总体架构设计", ("架构目标", "设计原则", "系统上下文", "逻辑架构", "技术架构", "关键机制", "架构决策")),
    Chapter(4, "功能模块设计", ("模块划分", "模块职责与边界", "模块协作", "主要流程", "异常与扩展点")),
    Chapter(5, "数据设计", ("数据架构", "核心实体与关系", "数据存储", "数据流转与一致性", "数据生命周期", "备份恢复与安全")),
    Chapter(6, "接口设计", ("接口总体说明", "内部接口", "外部接口", "认证与授权", "超时重试与幂等", "异常和版本兼容")),
    Chapter(7, "部署与运行设计", ("环境与网络区域", "部署架构", "部署单元与配置", "容量与伸缩", "高可用与容灾", "监控与运维")),
    Chapter(8, "安全设计", ("身份认证", "权限控制", "数据保护", "安全审计", "边界防护", "安全运维与合规")),
    Chapter(9, "非功能设计", ("性能", "可靠性与可用性", "可扩展性", "兼容性", "可维护性", "可观测性", "验证方法")),
)


TECHNICAL_SPEC_CHAPTERS = (
    Chapter(1, "概述", ("项目概述", "参考依据", "术语和缩略语", "文档范围与边界")),
    Chapter(2, "需求分析", ("功能需求分析", "性能需求分析", "安全与合规需求", "需求追踪说明")),
    Chapter(
        3,
        "系统总体设计",
        ("建设原则", "建设思路", "总体架构设计", "业务流程", "数据流程", "可靠性与可观测性", "系统约束与风险控制"),
    ),
    Chapter(
        4,
        "数据资源体系设计",
        ("设计目标", "数据资源统一组织", "数据架构", "数据规划", "文件与对象数据", "外部数据接口", "数据安全", "数据库设计边界"),
    ),
    Chapter(
        5,
        "算法任务与计算体系设计",
        ("设计目标", "体系架构", "任务模型", "调度与并发", "数据准备", "算法集成契约", "通用结果", "阶段追溯", "异常处理"),
    ),
    Chapter(
        6,
        "密码应用与软件供应链安全体系设计",
        ("设计目标", "体系边界", "密码应用体系", "软件供应链安全体系", "安全控制与审计"),
    ),
    Chapter(
        7,
        "系统概要设计",
        ("子系统划分", "功能模块覆盖清单", "模块概述", "功能架构", "功能逻辑", "业务流程", "技术实现", "数据与接口", "异常与边界"),
    ),
    Chapter(
        8,
        "技术路线",
        ("平台技术路线", "算法技术路线", "实时处理技术路线", "数据存储技术路线", "查询与可视化技术路线", "密码与安全技术路线", "软件供应链技术路线", "技术选型边界"),
    ),
)


def chapter_profile(workspace: Path) -> str:
    configured = read_task_fields(workspace).get("章节配置", "技术类概要设计")
    return "standard" if "标准全量" in configured or "九章" in configured else "technical"


def chapters_for_workspace(workspace: Path) -> tuple[Chapter, ...]:
    return STANDARD_CHAPTERS if chapter_profile(workspace) == "standard" else TECHNICAL_SPEC_CHAPTERS
