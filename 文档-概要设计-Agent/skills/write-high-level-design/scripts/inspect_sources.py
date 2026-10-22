from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from common import current_timestamp, read_task_fields, resolve_workspace, update_state
from distill_reference_samples import distill_workspace


SUPPORTED_SUFFIXES = {
    ".docx", ".doc", ".pdf", ".xlsx", ".xls", ".csv", ".tsv", ".pptx",
    ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".png", ".jpg",
    ".jpeg", ".svg", ".drawio", ".zip",
}
VALID_ROLES = {"强制要求", "项目事实", "目录结构参考", "内容参考", "样式参考", "正式交付模板", "不使用", "待确认"}


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    relative_path: str
    detected_role: str
    effective_role: str
    can_be_fact: str
    scope: str
    user_correction: str
    size: int
    modified_at: str
    sha256: str
    source_kind: str = "workspace-file"
    read_only: str = "是"
    access_status: str = "可访问"
    hash_scope: str = "file-content"


@dataclass(frozen=True)
class ExternalEntry:
    source_type: str
    name: str
    path: Path
    purpose: str
    read_only: str


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def existing_corrections(table_path: Path) -> dict[str, str]:
    if not table_path.exists():
        return {}
    corrections: dict[str, str] = {}
    for line in table_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "编号" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[-1]:
            corrections[cells[1].replace("\\|", "|")] = cells[-1]
    return corrections


def classify_source(path: Path, designated_template: bool) -> tuple[str, str, str]:
    if designated_template:
        return "正式交付模板", "否", "最终文档版式或内容载体"

    name = path.name.lower()
    if any(keyword in name for keyword in ("合同", "招标", "采购", "任务书", "验收要求", "强制要求")):
        return "强制要求", "是", "约束范围、交付和设计结论"
    if any(keyword in name for keyword in ("样式", "排版", "格式规范", "品牌", "视觉规范")):
        return "样式参考", "否", "仅参考格式、编号、表格、图形和语气"
    if any(keyword in name for keyword in ("目录", "大纲", "章节结构")):
        return "目录结构参考", "否", "仅参考标题层级和顺序"
    if any(keyword in name for keyword in ("概要设计", "总体设计", "详细设计", "设计说明", "范文", "样例", "参考文档")):
        return "内容参考", "否", "参考覆盖范围和表达方法，不继承项目事实"
    if any(keyword in name for keyword in ("需求", "接口", "数据字典", "数据库", "表结构", "架构图", "部署图", "流程图", "会议纪要", "现状", "调研")):
        return "项目事实", "是", "作为当前项目事实依据，超出资料内容不得补写"
    if "模板" in name:
        return "待确认", "待确认", "确认是目录、内容、样式参考还是正式交付模板"
    return "待确认", "待确认", "确认后使用"


def normalized_correction(correction: str) -> str:
    stripped = correction.strip()
    for role in VALID_ROLES:
        if role in stripped:
            return role
    return ""


def external_index(workspace: Path) -> Path:
    return workspace / "01-资料投递" / "外部资料与源码索引.md"


def parse_external_entries(workspace: Path) -> list[ExternalEntry]:
    index_path = external_index(workspace)
    if not index_path.exists():
        return []
    entries: list[ExternalEntry] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---") or "绝对路径" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5 or not cells[2]:
            continue
        entries.append(
            ExternalEntry(
                source_type=cells[0],
                name=cells[1] or Path(cells[2]).name,
                path=Path(cells[2]).expanduser(),
                purpose=cells[3] or "按索引用途读取",
                read_only=cells[4] or "是",
            )
        )
    return entries


def classify_external(entry: ExternalEntry) -> tuple[str, str, str]:
    source_type = entry.source_type.lower()
    if any(keyword in source_type for keyword in ("合同", "要求", "招标", "采购")):
        return "强制要求", "是", entry.purpose
    if "模板" in source_type:
        return "正式交付模板", "否", entry.purpose
    if any(keyword in source_type for keyword in ("源码", "代码", "java", "python")):
        return "项目事实", "是", entry.purpose
    if any(keyword in source_type for keyword in ("详细设计", "设计")):
        return "内容参考", "否", entry.purpose
    if "索引" in source_type:
        return "目录结构参考", "否", entry.purpose
    return classify_source(entry.path, False)


def path_metadata_hash(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.resolve()}|{stat.st_mode}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_files(workspace: Path) -> list[tuple[Path, bool]]:
    roots = (
        (workspace / "01-资料投递" / "所有参考资料放这里", False),
        (workspace / "01-资料投递" / "指定交付模板放这里", True),
        (workspace / "04-调整意见" / "新增资料放这里", False),
    )
    files: list[tuple[Path, bool]] = []
    for root, designated in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_SUFFIXES:
                files.append((path, designated))
    return sorted(files, key=lambda item: item[0].relative_to(workspace).as_posix())


def build_records(workspace: Path, corrections: dict[str, str]) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for index, (path, designated) in enumerate(collect_files(workspace), start=1):
        relative_path = path.relative_to(workspace).as_posix()
        detected_role, can_be_fact, scope = classify_source(path, designated)
        correction = corrections.get(relative_path, "")
        corrected_role = normalized_correction(correction)
        effective_role = corrected_role or detected_role
        if corrected_role:
            can_be_fact = "是" if corrected_role in {"强制要求", "项目事实"} else "否" if corrected_role != "待确认" else "待确认"
        stat = path.stat()
        records.append(
            SourceRecord(
                source_id=f"R-{index:03d}",
                relative_path=relative_path,
                detected_role=detected_role,
                effective_role=effective_role,
                can_be_fact=can_be_fact,
                scope=scope,
                user_correction=correction,
                size=stat.st_size,
                modified_at=current_timestamp() if stat.st_mtime <= 0 else datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                sha256=file_hash(path),
            )
        )
    for entry in parse_external_entries(workspace):
        index = len(records) + 1
        location = f"外部只读：{entry.path}"
        exists = entry.path.exists()
        detected_role, can_be_fact, scope = classify_external(entry)
        correction = corrections.get(location, "")
        corrected_role = normalized_correction(correction)
        effective_role = corrected_role or detected_role
        if corrected_role:
            can_be_fact = "是" if corrected_role in {"强制要求", "项目事实"} else "否" if corrected_role != "待确认" else "待确认"
        if not exists:
            effective_role = "待确认"
            can_be_fact = "待确认"
        modified_at = current_timestamp()
        size = 0
        sha256 = hashlib.sha256(str(entry.path).encode("utf-8")).hexdigest()
        hash_scope = "path-only"
        if exists:
            stat = entry.path.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
            size = stat.st_size if entry.path.is_file() else 0
            if entry.path.is_file():
                sha256 = file_hash(entry.path)
                hash_scope = "file-content"
            else:
                sha256 = path_metadata_hash(entry.path)
                hash_scope = "directory-metadata"
        records.append(
            SourceRecord(
                source_id=f"R-{index:03d}",
                relative_path=location,
                detected_role=detected_role,
                effective_role=effective_role,
                can_be_fact=can_be_fact,
                scope=scope,
                user_correction=correction,
                size=size,
                modified_at=modified_at,
                sha256=sha256,
                source_kind=entry.source_type or "external",
                read_only=entry.read_only,
                access_status="可访问" if exists else "路径不存在",
                hash_scope=hash_scope,
            )
        )
    return records


def render_table(records: list[SourceRecord]) -> str:
    lines = [
        "# 资料使用清单",
        "",
        "Agent 不移动或修改原始资料。需要纠正时只编辑最后一列，例如：`改为内容参考，不能作为项目事实`。",
        "",
        "| 编号 | 文件/路径 | 来源类型 | 识别用途 | 可以作为事实依据 | 只读 | 访问状态 | 使用范围 | 用户修正 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for record in records:
        path = record.relative_path.replace("|", "\\|")
        role = record.effective_role
        correction = record.user_correction.replace("|", "\\|")
        lines.append(
            f"| {record.source_id} | {path} | {record.source_kind} | {role} | {record.can_be_fact} | "
            f"{record.read_only} | {record.access_status} | {record.scope} | {correction} |"
        )
    if not records:
        lines.append("| - | 尚未发现支持的资料文件 | - | 待确认 | 待确认 | 是 | - | 请投递资料 | |")
    lines.append("")
    return "\n".join(lines)


def render_issues(workspace: Path, records: list[SourceRecord]) -> str:
    fields = read_task_fields(workspace)
    issues: list[tuple[str, str]] = []
    if not fields.get("项目名称"):
        issues.append(("警告", "编写任务中的项目名称尚未填写。"))
    if not records:
        issues.append(("错误", "尚未发现任何支持的参考资料。"))
    pending = [record.relative_path for record in records if record.effective_role == "待确认"]
    if pending:
        issues.append(("警告", f"有 {len(pending)} 份资料用途待确认：" + "、".join(pending)))
    templates = [record.relative_path for record in records if record.effective_role == "正式交付模板"]
    if len(templates) > 1:
        issues.append(("错误", "发现多个正式交付模板，请只保留一个或在任务说明中明确主模板。"))
    if not templates:
        issues.append(("提示", "未指定项目交付模板，将使用 Agent 默认 Word 参考模板。"))
    inaccessible = [record.relative_path for record in records if record.access_status != "可访问"]
    if inaccessible:
        issues.append(("错误", f"有 {len(inaccessible)} 个外部路径不可访问：" + "、".join(inaccessible)))

    lines = ["# 资料冲突与缺失", ""]
    if not issues:
        lines.extend(["未发现阻塞性冲突或缺失。", ""])
    else:
        lines.extend(["| 级别 | 内容 |", "|---|---|"])
        lines.extend(f"| {level} | {message} |" for level, message in issues)
        lines.append("")
    lines.append("资料之间出现事实冲突时，Agent 应记录双方资料编号、版本和影响章节，不得静默选择。")
    lines.append("")
    return "\n".join(lines)


def inspect_workspace(workspace: Path) -> list[SourceRecord]:
    table_path = workspace / "02-资料识别" / "资料使用清单.md"
    corrections = existing_corrections(table_path)
    records = build_records(workspace, corrections)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.write_text(render_table(records), encoding="utf-8")
    issues_path = table_path.parent / "资料冲突与缺失.md"
    issues_path.write_text(render_issues(workspace, records), encoding="utf-8")

    manifest_path = workspace / ".agent" / "source-manifest" / "source-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "1.0", "generated_at": current_timestamp(), "sources": [asdict(record) for record in records]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    distillation_path = distill_workspace(workspace, manifest)
    update_state(
        workspace,
        "sources_classified",
        15,
        "按索引逐项阅读资料和源码，更新理解台账与模板蒸馏规范",
        artifact=distillation_path.relative_to(workspace).as_posix(),
        verification=f"已登记 {len(records)} 个资料来源",
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="识别和登记概要设计参考资料")
    parser.add_argument("workspace", help="工作区名称或路径")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        records = inspect_workspace(workspace)
    except (ValueError, FileNotFoundError, OSError) as error:
        parser.error(str(error))
    print(f"已识别 {len(records)} 份资料：{workspace / '02-资料识别' / '资料使用清单.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
