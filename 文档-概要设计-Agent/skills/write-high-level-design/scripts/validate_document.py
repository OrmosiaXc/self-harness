from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from common import (
    chapter_profile,
    chapters_for_workspace,
    content_safety_findings,
    current_timestamp,
    read_task_fields,
    resolve_workspace,
    source_carrier_terms,
    update_state,
)


PLACEHOLDER_PATTERN = re.compile(r"\[待编写\]|\[待补充\]|TBD|资料编号：待补充")
HEADING_PATTERN = re.compile(r"^(#{2,6})\s+(.+?)\s*$", re.MULTILINE)
MIN_LEAF_SECTION_CHARACTERS = 120
MIN_LEAF_SECTION_PARAGRAPHS = 2
MIN_REPEATED_PARAGRAPH_CHARACTERS = 40
MAX_DETAILED_ISSUES = 20


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    location: str


def markdown_data_rows(path: Path) -> list[str]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---") and "需求编号" not in stripped and "编号" not in stripped:
            rows.append(stripped)
    return rows


def check_required_structure(workspace: Path) -> list[Issue]:
    required_paths = (
        "00-任务说明/编写任务.md",
        "00-任务说明/长任务计划.md",
        "00-任务说明/会话交接.md",
        "01-资料投递/所有参考资料放这里",
        "01-资料投递/外部资料与源码索引.md",
        "02-资料识别/资料使用清单.md",
        "02-资料识别/源码与材料理解台账.md",
        "02-资料识别/模板蒸馏规范.md",
        "02-资料识别/参考样本蒸馏规范.md",
        "02-资料识别/QA经验候选.md",
        "03-过程成果/00-章节索引.md",
        "03-过程成果/01-当前提纲.md",
        "03-过程成果/02-章节草稿",
        "03-过程成果/08-分章预览",
        "03-过程成果/04-问题与假设.md",
        "03-过程成果/05-需求追踪矩阵.md",
        "03-过程成果/07-Word版式质检报告.md",
        "03-过程成果/09-Word编辑预检报告.md",
        "04-调整意见/调整要求.md",
        "05-交付成果/02-正式版",
        ".agent/state.json",
    )
    return [
        Issue("错误", "STRUCTURE_MISSING", "缺少必需的工作区文件或目录", relative_path)
        for relative_path in required_paths
        if not (workspace / relative_path).exists()
    ]


def check_task(workspace: Path, final_mode: bool) -> list[Issue]:
    fields = read_task_fields(workspace)
    issues: list[Issue] = []
    for field in ("文档名称", "项目名称", "章节配置"):
        if not fields.get(field):
            severity = "错误" if final_mode else "警告"
            issues.append(Issue(severity, "TASK_FIELD_EMPTY", f"编写任务中的“{field}”尚未填写", "00-任务说明/编写任务.md"))
    return issues


def load_manifest(workspace: Path) -> dict:
    manifest_path = workspace / ".agent" / "source-manifest" / "source-manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def check_sources(workspace: Path, final_mode: bool) -> list[Issue]:
    manifest = load_manifest(workspace)
    if not manifest:
        return [Issue("错误", "SOURCE_MANIFEST_MISSING", "资料清单尚未生成或格式无效", ".agent/source-manifest/source-manifest.json")]
    sources = manifest.get("sources", [])
    issues: list[Issue] = []
    if not sources:
        issues.append(Issue("错误", "SOURCE_EMPTY", "没有可用的项目资料", "01-资料投递/所有参考资料放这里"))
    pending = [source.get("relative_path", "") for source in sources if source.get("effective_role") == "待确认"]
    if pending:
        severity = "错误" if final_mode else "警告"
        issues.append(Issue(severity, "SOURCE_ROLE_PENDING", f"仍有 {len(pending)} 份资料用途待确认", "02-资料识别/资料使用清单.md"))
    templates = [source for source in sources if source.get("effective_role") == "正式交付模板"]
    if len(templates) > 1:
        issues.append(Issue("错误", "MULTIPLE_TEMPLATES", "存在多个正式交付模板", "01-资料投递/指定交付模板放这里"))
    inaccessible = [source for source in sources if source.get("access_status") not in (None, "可访问")]
    if inaccessible:
        issues.append(Issue("错误", "EXTERNAL_SOURCE_INACCESSIBLE", f"有 {len(inaccessible)} 个外部资料或源码路径不可访问", "01-资料投递/外部资料与源码索引.md"))
    return issues


def chapter_status(path: Path) -> tuple[str, int]:
    if not path.exists():
        return "缺失", 0
    content = path.read_text(encoding="utf-8")
    placeholder_count = len(PLACEHOLDER_PATTERN.findall(content))
    if placeholder_count:
        return "待编写" if content.count("[待编写]") >= 3 else "需完善", placeholder_count
    return "已完成", 0


def update_chapter_index(workspace: Path) -> None:
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    lines = [
        "# 章节索引",
        "",
        "| 章节 | 状态 | 待确认事项 | 最近更新 | 文件 |",
        "|---|---|---|---|---|",
    ]
    for chapter in chapters_for_workspace(workspace):
        path = chapter_dir / chapter.filename
        status, placeholder_count = chapter_status(path)
        pending = f"{placeholder_count} 个占位项" if placeholder_count else "见问题与假设"
        modified = current_timestamp() if not path.exists() else datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        lines.append(f"| {chapter.number} {chapter.title} | {status} | {pending} | {modified} | [{chapter.filename}](02-章节草稿/{chapter.filename}) |")
    lines.append("")
    (workspace / "03-过程成果" / "00-章节索引.md").write_text("\n".join(lines), encoding="utf-8")


def check_chapters(workspace: Path, final_mode: bool) -> list[Issue]:
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    issues: list[Issue] = []
    for chapter in chapters_for_workspace(workspace):
        path = chapter_dir / chapter.filename
        if not path.exists():
            issues.append(Issue("错误", "CHAPTER_MISSING", f"缺少第 {chapter.number} 章“{chapter.title}”", path.relative_to(workspace).as_posix()))
            continue
        content = path.read_text(encoding="utf-8")
        placeholders = PLACEHOLDER_PATTERN.findall(content)
        if final_mode and placeholders:
            issues.append(Issue("错误", "PLACEHOLDER_REMAINING", f"第 {chapter.number} 章仍有 {len(placeholders)} 个占位项", path.relative_to(workspace).as_posix()))
        body = re.sub(r"^#+\s+.*$|<!--.*?-->|>\s*\[待编写\].*$", "", content, flags=re.MULTILINE | re.DOTALL).strip()
        if final_mode and len(body) < 120:
            issues.append(Issue("警告", "CHAPTER_TOO_SHORT", f"第 {chapter.number} 章正文过短，可能未充分展开", path.relative_to(workspace).as_posix()))
    if final_mode:
        issues.extend(check_section_depth(workspace))
        issues.extend(check_repeated_content(workspace))
        issues.extend(check_content_safety(workspace))
    return issues


def leaf_sections(content: str) -> list[tuple[str, str]]:
    matches = list(HEADING_PATTERN.finditer(content))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        next_match = matches[index + 1] if index + 1 < len(matches) else None
        if next_match and len(next_match.group(1)) > level:
            continue
        body_end = next_match.start() if next_match else len(content)
        sections.append((match.group(2).strip(), content[match.end():body_end].strip()))
    return sections


def section_metrics(body: str) -> tuple[int, int, int]:
    without_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    without_markup = re.sub(r"!\[[^\]]*]\([^)]+\)|[`*_>#|:-]", "", without_comments)
    characters = len(re.sub(r"\s+", "", without_markup))
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", without_comments)
        if block.strip() and not block.lstrip().startswith(("|---", "> [待编写]"))
    ]
    table_rows = sum(
        1
        for line in without_comments.splitlines()
        if line.strip().startswith("|") and not re.match(r"^\|\s*[-:| ]+\|?$", line.strip())
    )
    list_items = sum(1 for line in without_comments.splitlines() if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line))
    images = len(re.findall(r"!\[[^\]]*]\([^)]+\)", without_comments))
    return characters, len(paragraphs), table_rows + list_items + images


def check_section_depth(workspace: Path) -> list[Issue]:
    if read_task_fields(workspace).get("内容深度门禁", "启用") == "关闭":
        return []
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    shallow: list[Issue] = []
    total_sections = 0
    for path in sorted(chapter_dir.glob("*.md")):
        for title, body in leaf_sections(path.read_text(encoding="utf-8")):
            total_sections += 1
            characters, paragraphs, structured_units = section_metrics(body)
            too_short = characters < MIN_LEAF_SECTION_CHARACTERS and structured_units < 3
            too_thin = paragraphs < MIN_LEAF_SECTION_PARAGRAPHS and characters < 220 and structured_units < 3
            if too_short or too_thin:
                shallow.append(
                    Issue(
                        "错误",
                        "SECTION_TOO_SHALLOW",
                        f"“{title}”内容展开不足：{characters} 个非空白字符、{paragraphs} 个正文块、{structured_units} 个结构化条目",
                        path.relative_to(workspace).as_posix(),
                    )
                )
    issues = shallow[:MAX_DETAILED_ISSUES]
    if len(shallow) > MAX_DETAILED_ISSUES:
        issues.append(
            Issue(
                "错误",
                "SECTION_TOO_SHALLOW_SUMMARY",
                f"共 {len(shallow)}/{total_sections} 个叶子小节内容展开不足，仅列出前 {MAX_DETAILED_ISSUES} 个",
                "03-过程成果/02-章节草稿",
            )
        )
    return issues


def normalized_paragraphs(content: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", content):
        stripped = block.strip()
        if not stripped or stripped.startswith(("#", "|", "<!--", "> [待编写]")):
            continue
        normalized = re.sub(r"\s+", "", re.sub(r"[`*_>#-]", "", stripped))
        if len(normalized) >= MIN_REPEATED_PARAGRAPH_CHARACTERS:
            paragraphs.append(normalized)
    return paragraphs


def check_repeated_content(workspace: Path) -> list[Issue]:
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    counts = Counter(
        paragraph
        for path in chapter_dir.glob("*.md")
        for paragraph in normalized_paragraphs(path.read_text(encoding="utf-8"))
    )
    repeated = [(paragraph, count) for paragraph, count in counts.items() if count >= 3]
    return [
        Issue(
            "错误",
            "REPEATED_BOILERPLATE",
            f"同一段落在正文中重复 {count} 次，疑似机械套写：{paragraph[:48]}……",
            "03-过程成果/02-章节草稿",
        )
        for paragraph, count in sorted(repeated, key=lambda item: (-item[1], item[0]))[:10]
    ]


def check_content_safety(workspace: Path) -> list[Issue]:
    fields = read_task_fields(workspace)
    source_file_names, source_ids = source_carrier_terms(workspace)
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    issues: list[Issue] = []
    for path in sorted(chapter_dir.glob("*.md")):
        reader_content = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        for code, value in content_safety_findings(
            reader_content,
            fields,
            source_file_names,
            source_ids,
        ):
            severity = "警告" if code == "CODE_IDENTIFIER_EXPOSED" else "错误"
            messages = {
                "LOCAL_PATH_LEAK": "正文包含本机绝对路径",
                "INTERNAL_ARTIFACT_LEAK": "正文包含 Agent 内部工作产物名称或路径",
                "REFERENCE_TERM_LEAK": "正文包含配置的参考样本禁用词",
                "CODE_IDENTIFIER_EXPOSED": "正文包含代码式英文标识，宜改为中文职责描述",
                "SOURCE_ID_EXPOSED": "正文包含 Agent 内部资料编号",
                "REFERENCE_FILE_EXPOSED": "正文包含参考材料文件名，但未启用逻辑依赖说明",
                "REFERENCE_DEPENDENCY_EXPOSED": "正文包含参考材料的编写依赖说明，但未获用户明确要求",
            }
            issues.append(Issue(severity, code, f"{messages[code]}：{value}", path.relative_to(workspace).as_posix()))
    return issues[:MAX_DETAILED_ISSUES]


def check_final_artifacts(workspace: Path) -> list[Issue]:
    issues: list[Issue] = []
    trace_path = workspace / "03-过程成果" / "05-需求追踪矩阵.md"
    if not markdown_data_rows(trace_path):
        issues.append(Issue("错误", "TRACEABILITY_EMPTY", "需求追踪矩阵没有有效数据行", trace_path.relative_to(workspace).as_posix()))
    outline = workspace / "03-过程成果" / "01-当前提纲.md"
    if outline.exists() and "资料识别完成后由 Agent 生成" in outline.read_text(encoding="utf-8"):
        issues.append(Issue("错误", "OUTLINE_NOT_BUILT", "当前提纲仍是初始占位内容", outline.relative_to(workspace).as_posix()))
    ledger = workspace / "02-资料识别" / "源码与材料理解台账.md"
    if ledger.exists() and "状态：待取证" in ledger.read_text(encoding="utf-8"):
        issues.append(Issue("错误", "SOURCE_LEDGER_PENDING", "源码与材料理解台账尚未完成取证", ledger.relative_to(workspace).as_posix()))
    manifest = load_manifest(workspace)
    templates = [source for source in manifest.get("sources", []) if source.get("effective_role") == "正式交付模板"]
    distillation = workspace / "02-资料识别" / "模板蒸馏规范.md"
    if templates and distillation.exists() and "状态：待分析" in distillation.read_text(encoding="utf-8"):
        issues.append(Issue("错误", "TEMPLATE_NOT_DISTILLED", "指定模板尚未完成蒸馏分析", distillation.relative_to(workspace).as_posix()))
    reference_sources = [
        source
        for source in manifest.get("sources", [])
        if source.get("effective_role") in {"目录结构参考", "内容参考", "样式参考"}
    ]
    reference_distillation = workspace / "02-资料识别" / "参考样本蒸馏规范.md"
    if reference_sources and reference_distillation.exists() and "- [ ] 已确认样本只用于形式和内容展开方式。" in reference_distillation.read_text(encoding="utf-8"):
        issues.append(
            Issue(
                "错误",
                "REFERENCE_SAMPLE_NOT_CONFIRMED",
                "存在参考样本，但尚未确认样本隔离和采用规则",
                reference_distillation.relative_to(workspace).as_posix(),
            )
        )
    if chapter_profile(workspace) == "technical":
        issues.extend(check_technical_profile(workspace))
    return issues


def check_technical_profile(workspace: Path) -> list[Issue]:
    issues: list[Issue] = []
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    heading_text = "\n".join(
        line
        for path in chapter_dir.glob("*.md")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    )
    forbidden_headings = ("数据库详细设计", "部署与运行设计", "部署实施", "用户使用手册", "用户操作说明")
    for title in forbidden_headings:
        if title in heading_text:
            issues.append(Issue("错误", "TECHNICAL_PROFILE_SCOPE_LEAK", f"技术类概要设计出现排除章节“{title}”", "03-过程成果/02-章节草稿"))

    chapter_two = chapter_dir / "02-需求分析.md"
    if chapter_two.exists():
        content = chapter_two.read_text(encoding="utf-8")
        for topic in ("功能需求分析", "性能需求分析"):
            if topic not in content:
                issues.append(Issue("错误", "REQUIREMENT_SECTION_MISSING", f"需求分析缺少“{topic}”", chapter_two.relative_to(workspace).as_posix()))

    chapter_three = chapter_dir / "03-系统总体设计.md"
    if chapter_three.exists():
        content = chapter_three.read_text(encoding="utf-8")
        for topic in ("建设原则", "建设思路", "总体架构设计", "业务流程", "数据流程"):
            if topic not in content:
                issues.append(Issue("错误", "OVERALL_DESIGN_SECTION_MISSING", f"系统总体设计缺少“{topic}”", chapter_three.relative_to(workspace).as_posix()))

    chapter_seven = chapter_dir / "07-系统概要设计.md"
    if chapter_seven.exists():
        content = chapter_seven.read_text(encoding="utf-8")
        module_topics = ("模块概述", "功能架构", "功能逻辑", "业务流程", "技术实现", "数据与接口", "异常与边界")
        missing = [topic for topic in module_topics if topic not in content]
        if missing:
            issues.append(
                Issue(
                    "错误",
                    "MODULE_DESIGN_DEPTH_MISSING",
                    "系统概要设计缺少模块统一展开项：" + "、".join(missing),
                    chapter_seven.relative_to(workspace).as_posix(),
                )
            )
    return issues


def render_report(mode: str, issues: list[Issue]) -> str:
    error_count = sum(issue.severity == "错误" for issue in issues)
    warning_count = sum(issue.severity == "警告" for issue in issues)
    status = "未通过" if error_count else "通过"
    lines = [
        "# 质量检查报告",
        "",
        f"- 检查模式：{mode}",
        f"- 检查时间：{current_timestamp()}",
        f"- 结果：{status}",
        f"- 错误：{error_count}",
        f"- 警告：{warning_count}",
        "",
        "## 检查发现",
        "",
        "| 级别 | 代码 | 内容 | 位置 |",
        "|---|---|---|---|",
    ]
    if issues:
        lines.extend(f"| {issue.severity} | {issue.code} | {issue.message} | {issue.location} |" for issue in issues)
    else:
        lines.append("| 提示 | OK | 未发现问题 | - |")
    lines.extend(["", "错误级问题必须清零；警告应修复或记录接受理由。", ""])
    return "\n".join(lines)


def validate(workspace: Path, mode: str) -> list[Issue]:
    final_mode = mode == "final"
    issues = [
        *check_required_structure(workspace),
        *check_task(workspace, final_mode),
        *check_sources(workspace, final_mode),
        *check_chapters(workspace, final_mode),
    ]
    if final_mode:
        issues.extend(check_final_artifacts(workspace))
    update_chapter_index(workspace)

    report_path = workspace / "03-过程成果" / "06-质量检查报告.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(mode, issues), encoding="utf-8")
    json_path = workspace / ".agent" / "reviews" / "latest.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps({"mode": mode, "checked_at": current_timestamp(), "issues": [asdict(issue) for issue in issues]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    error_count = sum(issue.severity == "错误" for issue in issues)
    if error_count:
        update_state(workspace, "reviewing", 80 if final_mode else 35, "修复质量报告中的错误", f"{error_count} 个错误")
    elif final_mode:
        update_state(workspace, "ready_to_deliver", 90, "生成并检查正式交付版")
    else:
        update_state(workspace, "writing", 40, "根据已确认提纲编写或完善章节")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="检查概要设计工作区和文档质量")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--mode", choices=("structure", "final"), default="structure")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        issues = validate(workspace, args.mode)
    except (ValueError, FileNotFoundError, OSError) as error:
        parser.error(str(error))
    errors = sum(issue.severity == "错误" for issue in issues)
    warnings = sum(issue.severity == "警告" for issue in issues)
    print(f"质量检查完成：{errors} 个错误，{warnings} 个警告")
    print(workspace / "03-过程成果" / "06-质量检查报告.md")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
