from __future__ import annotations

import argparse
from pathlib import Path

from common import Chapter, chapters_for_workspace, current_timestamp, document_name, resolve_workspace, update_state


TEMPLATE_MARKER = "资料识别完成后由 Agent 生成"


def render_outline(workspace: Path) -> str:
    lines = [f"# {document_name(workspace)}提纲", ""]
    for chapter in chapters_for_workspace(workspace):
        lines.extend([f"## {chapter.number} {chapter.title}", ""])
        lines.extend(f"- {chapter.number}.{index} {title}" for index, title in enumerate(chapter.sections, start=1))
        lines.append("")
    lines.extend(
        [
            "> 本提纲是配置骨架。Agent 应根据资料台账、合同覆盖清单和源码事实细化，但不得删除强制要求覆盖的主题。",
            "> 技术类概要设计中的系统概要设计必须按全部功能点逐模块展开七项固定内容。",
            "",
        ]
    )
    return "\n".join(lines)


def render_chapter(chapter_number: int, chapter_title: str, sections: tuple[str, ...]) -> str:
    lines = [
        f"<!-- 状态：待编写；资料编号：待补充；最近更新：{current_timestamp()} -->",
        f"# {chapter_number} {chapter_title}",
        "",
    ]
    for index, section in enumerate(sections, start=1):
        lines.extend([f"## {chapter_number}.{index} {section}", "", "> [待编写] 根据资料使用清单补充内容、依据和待确认项。", ""])
    return "\n".join(lines)


def render_index(chapters: tuple[Chapter, ...]) -> str:
    lines = [
        "# 章节索引",
        "",
        "| 章节 | 状态 | 待确认事项 | 最近更新 | 文件 |",
        "|---|---|---|---|---|",
    ]
    today = current_timestamp()
    for chapter in chapters:
        lines.append(f"| {chapter.number} {chapter.title} | 待编写 | 待识别 | {today} | [{chapter.filename}](02-章节草稿/{chapter.filename}) |")
    lines.append("")
    return "\n".join(lines)


def can_overwrite(path: Path, force: bool) -> bool:
    if force or not path.exists():
        return True
    content = path.read_text(encoding="utf-8")
    return TEMPLATE_MARKER in content or "提纲生成后由 Agent 自动维护" in content


def build_outline(workspace: Path, force: bool) -> None:
    chapters = chapters_for_workspace(workspace)
    process_dir = workspace / "03-过程成果"
    outline_file = process_dir / "01-当前提纲.md"
    index_file = process_dir / "00-章节索引.md"
    if not can_overwrite(outline_file, force):
        raise FileExistsError("当前提纲包含人工或 Agent 修改内容；如确认覆盖，请使用 --force")
    process_dir.mkdir(parents=True, exist_ok=True)
    outline_file.write_text(render_outline(workspace), encoding="utf-8")
    if can_overwrite(index_file, force):
        index_file.write_text(render_index(chapters), encoding="utf-8")

    chapter_dir = process_dir / "02-章节草稿"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    for chapter in chapters:
        chapter_file = chapter_dir / chapter.filename
        if force or not chapter_file.exists():
            chapter_file.write_text(render_chapter(chapter.number, chapter.title, chapter.sections), encoding="utf-8")
    update_state(workspace, "outline_pending", 25, "查看并确认 03-过程成果/01-当前提纲.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成概要设计提纲和章节骨架")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--force", action="store_true", help="覆盖 Agent 生成的提纲和章节骨架")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        build_outline(workspace, args.force)
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        parser.error(str(error))
    print(f"已生成提纲和章节骨架：{workspace / '03-过程成果'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
