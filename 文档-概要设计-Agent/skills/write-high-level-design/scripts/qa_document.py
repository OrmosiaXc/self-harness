from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from common import (
    content_safety_findings,
    current_timestamp,
    read_task_fields,
    resolve_workspace,
    source_carrier_terms,
    timestamp_slug,
    update_state,
)


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
CORE_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
WORDPROCESSING_DRAWING_NAMESPACE = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PLACEHOLDERS = ("[待编写]", "[待补充]", "TBD", "资料编号：待补充")
ERROR = "错误"
WARNING = "警告"


@dataclass(frozen=True)
class QaIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class DocxAudit:
    paragraph_count: int
    heading_count: int
    table_count: int
    image_count: int
    page_field_count: int
    toc_field_count: int
    author: str
    last_modified_by: str
    issues: tuple[QaIssue, ...]


def word_tag(name: str) -> str:
    return f"{{{WORD_NAMESPACE}}}{name}"


def find_docx(workspace: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"DOCX 不存在：{path}")
        return path
    formal_dir = workspace / "05-交付成果" / "02-正式版"
    candidates = sorted(formal_dir.glob("*.docx"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"正式版目录中没有 DOCX：{formal_dir}")
    return candidates[0]


def xml_part(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    if name not in archive.namelist():
        return None
    return ET.fromstring(archive.read(name))


def core_property(core: ET.Element | None, namespace: str, name: str) -> str:
    if core is None:
        return ""
    element = core.find(f"{{{namespace}}}{name}")
    return element.text.strip() if element is not None and element.text else ""


def audit_docx(
    path: Path,
    task_fields: dict[str, str] | None = None,
    source_file_names: tuple[str, ...] = (),
    source_ids: tuple[str, ...] = (),
) -> DocxAudit:
    issues: list[QaIssue] = []
    with zipfile.ZipFile(path) as archive:
        damaged = archive.testzip()
        if damaged:
            issues.append(QaIssue(ERROR, "PACKAGE_DAMAGED", f"DOCX 包含损坏组件：{damaged}"))
        document = xml_part(archive, "word/document.xml")
        if document is None:
            raise ValueError("DOCX 缺少 word/document.xml")
        paragraphs = document.findall(f".//{word_tag('p')}")
        headings = [
            paragraph
            for paragraph in paragraphs
            if any(
                (style.get(word_tag("val")) or "").lower().startswith(("heading", "title", "标题"))
                for style in paragraph.findall(f"./{word_tag('pPr')}/{word_tag('pStyle')}")
            )
        ]
        tables = document.findall(f".//{word_tag('tbl')}")
        drawings = document.findall(f".//{word_tag('drawing')}") + document.findall(f".//{word_tag('pict')}")
        drawing_properties = document.findall(f".//{{{WORDPROCESSING_DRAWING_NAMESPACE}}}docPr")
        instructions = " ".join(
            element.text or ""
            for element in document.findall(f".//{word_tag('instrText')}")
        ).upper()
        text = "".join(element.text or "" for element in document.findall(f".//{word_tag('t')}"))
        remaining = [token for token in PLACEHOLDERS if token in text]
        if remaining:
            issues.append(QaIssue(ERROR, "PLACEHOLDER_REMAINING", "正式 DOCX 仍含占位符：" + "、".join(remaining)))
        if not headings:
            issues.append(QaIssue(ERROR, "HEADING_STYLE_MISSING", "未检测到真实 Heading/标题样式"))
        if "word/comments.xml" in archive.namelist():
            issues.append(QaIssue(ERROR, "COMMENTS_REMAINING", "DOCX 仍包含批注"))
        if document.findall(f".//{word_tag('ins')}") or document.findall(f".//{word_tag('del')}"):
            issues.append(QaIssue(ERROR, "TRACKED_CHANGES_REMAINING", "DOCX 仍包含修订痕迹"))
        if document.findall(f".//{word_tag('vanish')}"):
            issues.append(QaIssue(WARNING, "HIDDEN_TEXT_FOUND", "DOCX 包含隐藏文本属性"))
        missing_alt_text = [
            element
            for element in drawing_properties
            if not (element.get("descr") or element.get("title") or "").strip()
        ]
        if missing_alt_text:
            issues.append(QaIssue(WARNING, "IMAGE_ALT_TEXT_MISSING", f"有 {len(missing_alt_text)} 幅图未设置替代文本"))

        relationships = xml_part(archive, "word/_rels/document.xml.rels")
        if relationships is not None:
            external_relationships = [
                relation
                for relation in relationships.findall(f"{{{RELATIONSHIP_NAMESPACE}}}Relationship")
                if relation.get("TargetMode") == "External"
            ]
            if external_relationships:
                issues.append(QaIssue(WARNING, "EXTERNAL_RELATIONSHIP", f"存在 {len(external_relationships)} 个外部关系，请确认必要性"))

        core = xml_part(archive, "docProps/core.xml")
        author = core_property(core, DC_NAMESPACE, "creator")
        last_modified_by = core_property(core, CORE_NAMESPACE, "lastModifiedBy")
        if author or last_modified_by:
            issues.append(QaIssue(WARNING, "METADATA_IDENTITY", "文档属性包含作者或最后修改者，请确认是否需要清理"))
        safety_text = "\n".join(
            [
                text,
                author,
                last_modified_by,
                *(element.get("descr") or "" for element in drawing_properties),
                *(element.get("title") or "" for element in drawing_properties),
            ]
        )
        for code, value in content_safety_findings(
            safety_text,
            task_fields or {},
            source_file_names,
            source_ids,
        ):
            severity = WARNING if code == "CODE_IDENTIFIER_EXPOSED" else ERROR
            messages = {
                "LOCAL_PATH_LEAK": "DOCX 正文或元数据包含本机绝对路径",
                "INTERNAL_ARTIFACT_LEAK": "DOCX 正文或元数据包含 Agent 内部工作产物",
                "REFERENCE_TERM_LEAK": "DOCX 包含配置的参考样本禁用词",
                "CODE_IDENTIFIER_EXPOSED": "DOCX 包含代码式英文标识，宜改为中文职责描述",
                "SOURCE_ID_EXPOSED": "DOCX 包含 Agent 内部资料编号",
                "REFERENCE_FILE_EXPOSED": "DOCX 包含未获显式授权的参考材料文件名",
                "REFERENCE_DEPENDENCY_EXPOSED": "DOCX 包含未获显式授权的参考材料依赖说明",
            }
            issues.append(QaIssue(severity, code, f"{messages[code]}：{value}"))

    return DocxAudit(
        paragraph_count=len(paragraphs),
        heading_count=len(headings),
        table_count=len(tables),
        image_count=len(drawings),
        page_field_count=instructions.count("PAGE"),
        toc_field_count=instructions.count("TOC"),
        author=author,
        last_modified_by=last_modified_by,
        issues=tuple(issues),
    )


def find_render_script() -> Path | None:
    root = Path.home() / ".codex" / "plugins" / "cache" / "openai-primary-runtime" / "documents"
    candidates = sorted(root.glob("*/skills/documents/render_docx.py"), reverse=True)
    return candidates[0] if candidates else None


def render_python() -> str:
    bundled = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "bin" / "python3"
    return str(bundled) if bundled.exists() else sys.executable


def render_pages(docx_path: Path, output_dir: Path) -> tuple[list[Path], str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = "/private/tmp"
    env["XDG_CACHE_HOME"] = "/private/tmp/hld-agent-cache"
    Path(env["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
    render_script = find_render_script()
    if render_script:
        command = [render_python(), str(render_script), str(docx_path), "--output_dir", str(output_dir), "--emit_pdf"]
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
        pages = sorted(output_dir.glob("page-*.png"), key=page_number)
        if result.returncode == 0 and pages:
            return pages, "documents render_docx.py"
        detail = (result.stderr or result.stdout).strip()
    else:
        detail = "未找到 documents render_docx.py"

    libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not libreoffice:
        raise RuntimeError(f"{detail}；同时未找到 LibreOffice")
    result = subprocess.run(
        [libreoffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(docx_path)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return [], "LibreOffice PDF（未生成逐页 PNG）"


def page_number(path: Path) -> int:
    digits = "".join(character for character in path.stem if character.isdigit())
    return int(digits or 0)


def write_page_index(output_dir: Path, pages: list[Path]) -> Path:
    index_path = output_dir / "pages-index.html"
    cards = "\n".join(
        f'<figure><img src="{html.escape(page.name)}" loading="lazy"><figcaption>第 {page_number(page)} 页</figcaption></figure>'
        for page in pages
    )
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Word 全页检查</title>
<style>
body {{ margin: 20px; font-family: sans-serif; background: #eef2f7; }}
main {{ display: grid; grid-template-columns: repeat(4, minmax(220px, 1fr)); gap: 16px; }}
figure {{ margin: 0; padding: 10px; background: white; border: 1px solid #cbd5e1; }}
img {{ width: 100%; height: auto; display: block; }}
figcaption {{ margin-top: 8px; text-align: center; color: #334155; }}
</style>
</head>
<body><h1>Word 全页检查（{len(pages)} 页）</h1><main>{cards}</main></body>
</html>
"""
    index_path.write_text(content, encoding="utf-8")
    return index_path


def render_report(
    docx_path: Path,
    audit: DocxAudit,
    pages: list[Path],
    renderer: str,
    output_dir: Path,
    visual_confirmed: bool,
) -> str:
    error_count = sum(issue.severity == ERROR for issue in audit.issues)
    lines = [
        "# Word 版式质检报告",
        "",
        f"- DOCX：`{docx_path}`",
        f"- 检查时间：{current_timestamp()}",
        f"- 结构检查：{'通过' if error_count == 0 else '未通过'}",
        f"- 全页渲染：{'已完成' if pages else '仅生成 PDF，需补充逐页图片'}",
        f"- 渲染器：{renderer}",
        f"- 渲染页数：{len(pages)}",
        f"- 页面图片目录：`{output_dir}`",
        f"- 页面索引：`{output_dir / 'pages-index.html'}`",
        f"- 逐页目视检查：{'已完成' if visual_confirmed else '待确认'}",
        "",
        "## 结构统计",
        "",
        "| 项目 | 数量/内容 |",
        "|---|---|",
        f"| 段落 | {audit.paragraph_count} |",
        f"| 结构化标题 | {audit.heading_count} |",
        f"| 表格 | {audit.table_count} |",
        f"| 图片/绘图 | {audit.image_count} |",
        f"| PAGE 字段 | {audit.page_field_count} |",
        f"| TOC 字段 | {audit.toc_field_count} |",
        f"| 作者属性 | {audit.author or '空'} |",
        f"| 最后修改者 | {audit.last_modified_by or '空'} |",
        "",
        "## 自动检查发现",
        "",
        "| 级别 | 代码 | 内容 |",
        "|---|---|---|",
    ]
    if audit.issues:
        lines.extend(f"| {issue.severity} | {issue.code} | {issue.message} |" for issue in audit.issues)
    else:
        lines.append("| 提示 | OK | 未发现结构问题 |")
    lines.extend(
        [
            "",
            "## 逐页发现",
            "",
            "| 页码 | 问题 | 修复 | 复核 |",
            "|---|---|---|---|",
            "",
            "## 最终结论",
            "",
            "逐页检查应覆盖缺字、溢出、截断、孤立标题、空白页、目录页码、页眉页脚、表格和图片清晰度。",
            "图件还应检查图内重复标题、无意义英文眉题、底部备注、连线穿越图块、字体过小、替代文本和图文名称不一致。",
            "",
        ]
    )
    if visual_confirmed:
        lines.append("结构检查无错误，全部渲染页面已完成目视检查。")
    else:
        lines.append("当前只完成自动结构检查和页面渲染，尚不能标记正式交付完成。")
    lines.append("")
    return "\n".join(lines)


def run_qa(workspace: Path, docx_path: Path, visual_confirmed: bool) -> tuple[DocxAudit, list[Path], Path]:
    source_file_names, source_ids = source_carrier_terms(workspace)
    audit = audit_docx(
        docx_path,
        read_task_fields(workspace),
        source_file_names,
        source_ids,
    )
    output_dir = workspace / ".agent" / "word-qa" / timestamp_slug()
    pages, renderer = render_pages(docx_path, output_dir)
    if pages:
        write_page_index(output_dir, pages)
    error_count = sum(issue.severity == ERROR for issue in audit.issues)
    if visual_confirmed and (error_count or not pages):
        raise ValueError("结构检查存在错误或未生成逐页图片，不能确认目视检查完成")
    report_path = workspace / "03-过程成果" / "07-Word版式质检报告.md"
    report_path.write_text(render_report(docx_path, audit, pages, renderer, output_dir, visual_confirmed), encoding="utf-8")
    machine_report = output_dir / "audit.json"
    machine_report.write_text(json.dumps(asdict(audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if visual_confirmed:
        update_state(
            workspace,
            "completed",
            100,
            "交付正式版",
            active_work_item="Word 全页质检完成",
            artifact=report_path.relative_to(workspace).as_posix(),
            verification=f"DOCX 结构通过，已逐页检查 {len(pages)} 页",
        )
    else:
        update_state(
            workspace,
            "qa_pending",
            95,
            "检查全部页面图片，修复后运行 qa --confirm-visual",
            active_work_item="Word 全页渲染与目视检查",
            artifact=report_path.relative_to(workspace).as_posix(),
            verification=f"已渲染 {len(pages)} 页，结构错误 {error_count} 个",
        )
    return audit, pages, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="检查并渲染概要设计 DOCX")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--docx", help="指定 DOCX；默认使用正式版目录中最新文件")
    parser.add_argument("--confirm-visual", action="store_true", help="仅在全部页面已人工检查后使用")
    args = parser.parse_args()
    workspace = resolve_workspace(args.workspace)
    docx_path = find_docx(workspace, args.docx)
    try:
        audit, pages, report_path = run_qa(workspace, docx_path, args.confirm_visual)
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    errors = sum(issue.severity == ERROR for issue in audit.issues)
    print(f"Word 质检完成：{errors} 个结构错误，渲染 {len(pages)} 页")
    print(report_path)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
