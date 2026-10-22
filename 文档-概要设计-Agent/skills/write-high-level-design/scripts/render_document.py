from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from common import agent_root, chapters_for_workspace, current_timestamp, document_name, read_task_fields, resolve_workspace, update_state
from preflight_word import assert_output_available
from validate_document import validate


PLACEHOLDER_TOKENS = ("[待编写]", "[待补充]", "TBD", "资料编号：待补充")


def reader_facing_markdown(content: str) -> str:
    return re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()


def assemble_markdown(workspace: Path) -> str:
    fields = read_task_fields(workspace)
    title = document_name(workspace).replace('"', "'")
    lines = [
        "---",
        f'title: "{title}"',
        'lang: "zh-CN"',
        f'date: "{current_timestamp()[:10]}"',
        "---",
        "",
        f"# {title}",
        "",
        "| 项目 | 内容 |",
        "|---|---|",
        f"| 项目名称 | {fields.get('项目名称', '')} |",
        f"| 文档名称 | {title} |",
        f"| 输出格式 | {fields.get('输出格式', 'Markdown + DOCX')} |",
        f"| 计划读者 | {fields.get('计划读者', '')} |",
        "",
    ]
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    for chapter in chapters_for_workspace(workspace):
        chapter_path = chapter_dir / chapter.filename
        if not chapter_path.exists():
            raise FileNotFoundError(f"缺少章节文件：{chapter_path}")
        content = reader_facing_markdown(chapter_path.read_text(encoding="utf-8"))
        lines.extend([content, ""])
    return "\n".join(lines).strip() + "\n"


def assemble_chapter_markdown(workspace: Path, chapter_number: int) -> tuple[str, str]:
    chapter = next((item for item in chapters_for_workspace(workspace) if item.number == chapter_number), None)
    if chapter is None:
        raise ValueError(f"章节编号无效：{chapter_number}")
    chapter_path = workspace / "03-过程成果" / "02-章节草稿" / chapter.filename
    if not chapter_path.exists():
        raise FileNotFoundError(f"缺少章节文件：{chapter_path}")
    title = f"第{chapter.number:02d}章 {chapter.title}"
    content = (
        "---\n"
        f'title: "{document_name(workspace)}-{title}"\n'
        'lang: "zh-CN"\n'
        f'date: "{current_timestamp()[:10]}"\n'
        "---\n\n"
        f"# {document_name(workspace)}\n\n"
        f"{reader_facing_markdown(chapter_path.read_text(encoding='utf-8'))}\n"
    )
    return title, content


def ensure_complete(content: str) -> None:
    remaining = [token for token in PLACEHOLDER_TOKENS if token in content]
    if remaining:
        raise ValueError("正式交付稿仍包含占位符：" + "、".join(remaining))


def reference_template(workspace: Path) -> Path:
    designated_dir = workspace / "01-资料投递" / "指定交付模板放这里"
    designated = sorted(path for path in designated_dir.glob("*.docx") if path.is_file()) if designated_dir.exists() else []
    index_path = workspace / "01-资料投递" / "外部资料与源码索引.md"
    external: list[Path] = []
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or stripped.startswith("|---") or "绝对路径" in stripped:
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) >= 3 and "模板" in cells[0] and cells[2]:
                path = Path(cells[2]).expanduser().resolve()
                if path.is_file() and path.suffix.lower() == ".docx":
                    external.append(path)
    candidates = list(dict.fromkeys([*(path.resolve() for path in designated), *external]))
    if len(candidates) > 1:
        raise ValueError("指定交付模板目录中存在多个 DOCX，请只保留一个主模板")
    if candidates:
        return candidates[0]
    default_template = agent_root() / "skills" / "write-high-level-design" / "assets" / "default-template.docx"
    if not default_template.exists():
        raise FileNotFoundError(f"默认 Word 模板不存在：{default_template}")
    return default_template


def validate_docx_package(path: Path) -> None:
    required_entries = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
    with zipfile.ZipFile(path) as archive:
        damaged = archive.testzip()
        if damaged:
            raise ValueError(f"DOCX 压缩包包含损坏文件：{damaged}")
        names = set(archive.namelist())
        missing = required_entries - names
        if missing:
            raise ValueError("DOCX 缺少必需组件：" + "、".join(sorted(missing)))
        ET.fromstring(archive.read("word/document.xml"))
        ET.fromstring(archive.read("word/styles.xml"))


def sanitized_xml(name: str, payload: bytes) -> bytes:
    if name == "word/document.xml":
        for element_name in ("commentRangeStart", "commentRangeEnd", "commentReference"):
            payload = re.sub(rb"<w:" + element_name.encode("ascii") + rb"\b[^>]*/>", b"", payload)
        return payload
    if name == "[Content_Types].xml":
        return re.sub(
            rb"<Override\b(?=[^>]*\bPartName=[\"']/word/comments[^\"']*[\"'])[^>]*/>",
            b"",
            payload,
        )
    elif name == "word/_rels/document.xml.rels":
        return re.sub(
            rb"<Relationship\b(?=[^>]*\bType=[\"'][^\"']*/comments[\"'])[^>]*/>",
            b"",
            payload,
        )
    elif name == "docProps/core.xml":
        for element_name in (b"dc:creator", b"cp:lastModifiedBy"):
            payload = re.sub(
                rb"(<" + element_name + rb"\b[^>]*>).*?(</" + element_name + rb">)",
                rb"\1\2",
                payload,
                flags=re.DOTALL,
            )
        return payload
    return payload


def sanitize_docx(path: Path) -> None:
    temporary = path.with_name(f"{path.stem}.sanitized.docx")
    xml_parts = {
        "[Content_Types].xml",
        "word/_rels/document.xml.rels",
        "word/document.xml",
        "docProps/core.xml",
    }
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            if item.filename.startswith("word/comments") or item.filename.startswith("word/_rels/comments"):
                continue
            payload = source.read(item.filename)
            if item.filename in xml_parts:
                payload = sanitized_xml(item.filename, payload)
            target.writestr(item, payload)
    temporary.replace(path)


def render_docx(workspace: Path, markdown_path: Path, output_path: Path) -> None:
    assert_output_available(output_path)
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise FileNotFoundError("未找到 pandoc，无法生成 DOCX；Markdown 合并稿仍可使用")
    template = reference_template(workspace)
    resource_paths = [workspace, workspace / "03-过程成果" / "03-图表"]
    command = [
        pandoc,
        str(markdown_path),
        "--from=gfm",
        "--to=docx",
        "--toc",
        f"--reference-doc={template}",
        f"--resource-path={os.pathsep.join(str(path) for path in resource_paths)}",
        "--output",
        str(output_path),
    ]
    subprocess.run(command, check=True, cwd=workspace)
    sanitize_docx(output_path)
    validate_docx_package(output_path)


def render_chapter(workspace: Path, chapter_number: int, output_format: str) -> list[Path]:
    title, content = assemble_chapter_markdown(workspace, chapter_number)
    preview_dir = workspace / "03-过程成果" / "08-分章预览"
    machine_dir = workspace / ".agent" / "normalized-sources" / "chapters"
    preview_dir.mkdir(parents=True, exist_ok=True)
    machine_dir.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace(" ", "-")
    markdown_source = machine_dir / f"{chapter_number:02d}.md"
    markdown_source.write_text(content, encoding="utf-8")
    outputs: list[Path] = []
    if output_format in {"markdown", "all"}:
        markdown_output = preview_dir / f"{safe_title}-预览.md"
        markdown_output.write_text(content, encoding="utf-8")
        outputs.append(markdown_output)
    if output_format in {"docx", "all"}:
        docx_output = preview_dir / f"{safe_title}-预览.docx"
        render_docx(workspace, markdown_source, docx_output)
        outputs.append(docx_output)
    update_state(
        workspace,
        "reviewing",
        70,
        f"查看第 {chapter_number} 章分章预览并提交调整意见",
        active_work_item=f"第 {chapter_number} 章独立审阅",
        artifact=outputs[-1].relative_to(workspace).as_posix() if outputs else None,
        verification="分章预览已生成，未触发总文档合并",
    )
    return outputs


def read_only_source_roots(workspace: Path) -> list[Path]:
    index_path = workspace / "01-资料投递" / "外部资料与源码索引.md"
    if not index_path.exists():
        return []
    roots: list[Path] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---") or "绝对路径" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 5 and cells[2] and any(keyword in cells[0].lower() for keyword in ("源码", "代码", "java", "python")):
            roots.append(Path(cells[2]).expanduser().resolve())
    return roots


def publish_outputs(workspace: Path, outputs: list[Path], publish_dir: str) -> list[Path]:
    destination = Path(publish_dir).expanduser().resolve()
    for source_root in read_only_source_roots(workspace):
        if destination == source_root or source_root in destination.parents:
            raise ValueError(f"成果目录不能位于只读源码目录中：{destination}")
    destination.mkdir(parents=True, exist_ok=True)
    published: list[Path] = []
    for output in outputs:
        target = destination / output.name
        shutil.copy2(output, target)
        published.append(target)
    return published


def render(workspace: Path, output_format: str, allow_incomplete: bool, publish_dir: str | None = None) -> list[Path]:
    content = assemble_markdown(workspace)
    if not allow_incomplete:
        issues = validate(workspace, "final")
        errors = [issue for issue in issues if issue.severity == "错误"]
        if errors:
            raise ValueError(f"正式交付前质量检查未通过，共 {len(errors)} 个错误")
        ensure_complete(content)

    preview_dir = workspace / "05-交付成果" / "01-预览版"
    formal_dir = workspace / "05-交付成果" / "02-正式版"
    machine_dir = workspace / ".agent" / "normalized-sources"
    for directory in (preview_dir, formal_dir, machine_dir):
        directory.mkdir(parents=True, exist_ok=True)

    name = document_name(workspace)
    assembled_path = machine_dir / "assembled.md"
    assembled_path.write_text(content, encoding="utf-8")
    preview_path = preview_dir / f"{name}-预览.md"
    preview_path.write_text(content, encoding="utf-8")
    outputs = [preview_path]

    target_dir = preview_dir if allow_incomplete else formal_dir
    suffix = "-预览" if allow_incomplete else ""
    if output_format in {"markdown", "all"}:
        markdown_output = target_dir / f"{name}{suffix}.md"
        markdown_output.write_text(content, encoding="utf-8")
        if markdown_output not in outputs:
            outputs.append(markdown_output)
    if output_format in {"docx", "all"}:
        docx_output = target_dir / f"{name}{suffix}.docx"
        render_docx(workspace, assembled_path, docx_output)
        outputs.append(docx_output)

    generated_outputs = [output for output in outputs if output.parent == target_dir]
    if publish_dir and not allow_incomplete:
        outputs.extend(publish_outputs(workspace, generated_outputs, publish_dir))

    if allow_incomplete:
        update_state(workspace, "reviewing", 85, "查看预览稿并完成占位项和质量问题")
    else:
        update_state(
            workspace,
            "qa_pending",
            95,
            "运行 agent.py qa，检查全部页面后确认正式交付",
            active_work_item="DOCX 结构与全页版式质检",
            artifact=next((path.as_posix() for path in generated_outputs if path.suffix == ".docx"), None),
            verification="正式 Markdown/DOCX 已生成，Word 全页质检待执行",
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="合并章节并生成概要设计交付文件")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--format", choices=("markdown", "docx", "all"), default="all")
    parser.add_argument("--chapter", type=int, help="仅生成指定章节预览，不合并总文档")
    parser.add_argument("--allow-incomplete", action="store_true", help="允许带占位符生成预览稿")
    parser.add_argument("--publish-dir", help="将正式成果复制到用户明确指定的外部目录")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        if args.chapter is not None:
            if args.publish_dir:
                raise ValueError("分章预览不能发布到外部目录")
            outputs = render_chapter(workspace, args.chapter, args.format)
        else:
            outputs = render(workspace, args.format, args.allow_incomplete, args.publish_dir)
    except (ValueError, FileNotFoundError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print("已生成：")
    for output in outputs:
        print(f"- {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
