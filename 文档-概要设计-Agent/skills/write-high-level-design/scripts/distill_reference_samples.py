from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from common import current_timestamp, resolve_workspace


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
EXTENDED_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
REFERENCE_ROLES = {"目录结构参考", "内容参考", "样式参考"}


@dataclass(frozen=True)
class SampleMetrics:
    pages: str
    paragraphs: int
    headings: str
    body_characters: int
    tables: int
    images: int
    paragraph_density: str
    status: str


def word_tag(name: str) -> str:
    return f"{{{WORD_NAMESPACE}}}{name}"


def text_of(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.findall(f".//{word_tag('t')}")).strip()


def heading_level(style: str) -> str | None:
    normalized = style.strip().lower()
    match = re.search(r"([1-9])$", normalized)
    if normalized.startswith(("heading", "标题")):
        return match.group(1) if match else "未分级"
    return None


def docx_metrics(path: Path) -> SampleMetrics:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = [paragraph for paragraph in document.findall(f".//{word_tag('p')}") if text_of(paragraph)]
        heading_counts: Counter[str] = Counter()
        body_characters = 0
        body_paragraphs = 0
        for paragraph in paragraphs:
            styles = paragraph.findall(f"./{word_tag('pPr')}/{word_tag('pStyle')}")
            level = next(
                (heading_level(style.get(word_tag("val")) or "") for style in styles if heading_level(style.get(word_tag("val")) or "")),
                None,
            )
            if level:
                heading_counts[level] += 1
            else:
                body_paragraphs += 1
                body_characters += len(re.sub(r"\s+", "", text_of(paragraph)))
        pages = "未知"
        if "docProps/app.xml" in archive.namelist():
            app = ET.fromstring(archive.read("docProps/app.xml"))
            page_element = app.find(f"{{{EXTENDED_NAMESPACE}}}Pages")
            if page_element is not None and page_element.text:
                pages = page_element.text.strip()
        heading_total = sum(heading_counts.values())
        density = f"{body_paragraphs / heading_total:.1f}" if heading_total else "无标题"
        headings = "、".join(f"H{level}={count}" for level, count in sorted(heading_counts.items())) or "未识别"
        return SampleMetrics(
            pages=pages,
            paragraphs=len(paragraphs),
            headings=headings,
            body_characters=body_characters,
            tables=len(document.findall(f".//{word_tag('tbl')}")),
            images=sum(1 for name in archive.namelist() if name.startswith("word/media/") and not name.endswith("/")),
            paragraph_density=density,
            status="已解析",
        )


def markdown_metrics(path: Path) -> SampleMetrics:
    content = path.read_text(encoding="utf-8")
    headings = Counter(str(len(match.group(1))) for match in re.finditer(r"^(#{1,6})\s+.+$", content, re.MULTILINE))
    body_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "|", "![", "<!--"))
    ]
    heading_total = sum(headings.values())
    density = f"{len(body_lines) / heading_total:.1f}" if heading_total else "无标题"
    return SampleMetrics(
        pages="不适用",
        paragraphs=len(body_lines),
        headings="、".join(f"H{level}={count}" for level, count in sorted(headings.items())) or "未识别",
        body_characters=len(re.sub(r"\s+", "", "\n".join(body_lines))),
        tables=sum(1 for line in content.splitlines() if line.strip().startswith("|---")),
        images=len(re.findall(r"!\[[^\]]*]\([^)]+\)", content)),
        paragraph_density=density,
        status="已解析",
    )


def sample_metrics(path: Path) -> SampleMetrics:
    if path.suffix.lower() == ".docx":
        return docx_metrics(path)
    if path.suffix.lower() in {".md", ".txt"}:
        return markdown_metrics(path)
    return SampleMetrics("未知", 0, "未解析", 0, 0, 0, "未知", f"暂不解析 {path.suffix.lower() or '无扩展名'}")


def load_manifest(workspace: Path) -> dict:
    path = workspace / ".agent" / "source-manifest" / "source-manifest.json"
    if not path.exists():
        raise FileNotFoundError("请先运行 inspect 生成资料清单")
    return json.loads(path.read_text(encoding="utf-8"))


def source_path(workspace: Path, relative_path: str) -> Path:
    prefix = "外部只读："
    return Path(relative_path[len(prefix):]).expanduser() if relative_path.startswith(prefix) else workspace / relative_path


def render_report(workspace: Path, manifest: dict) -> str:
    records = [
        source
        for source in manifest.get("sources", [])
        if source.get("effective_role") in REFERENCE_ROLES and source.get("access_status") in (None, "可访问")
    ]
    lines = [
        "# 参考样本蒸馏规范",
        "",
        f"- 生成时间：{current_timestamp()}",
        "- 使用边界：只提取结构、篇幅、密度和图表形式，不复制样本项目名称、业务事实、指标、版本或结论。",
        "- 当前项目的合同、需求、源码证据和用户指令始终高于样本特征。",
        "",
        "## 样本量化特征",
        "",
        "| 编号 | 用途 | 文件 | SHA-256 | 页数 | 段落 | 标题分布 | 正文字数 | 表格 | 图片 | 每标题正文段落 | 状态 |",
        "|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for source in records:
        path = source_path(workspace, str(source.get("relative_path", "")))
        try:
            metrics = sample_metrics(path)
        except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
            metrics = SampleMetrics("未知", 0, "解析失败", 0, 0, 0, "未知", f"失败：{error}")
        display_path = path.name.replace("|", "｜")
        lines.append(
            f"| {source.get('source_id', '-')} | {source.get('effective_role', '-')} | {display_path} | "
            f"{source.get('sha256', '-')} | {metrics.pages} | {metrics.paragraphs} | {metrics.headings} | "
            f"{metrics.body_characters} | {metrics.tables} | {metrics.images} | {metrics.paragraph_density} | {metrics.status} |"
        )
    if not records:
        lines.append("| - | - | 未发现目录、内容或样式参考样本 | - | - | - | - | - | - | - | - | 待投递 |")
    lines.extend(
        [
            "",
            "## 本项目采用规则",
            "",
            "- 章节层级与顺序：待 Agent 根据多个样本的共同特征和当前项目要求填写。",
            "- 章节展开密度：待填写；不得直接把样本页数设置为硬性指标。",
            "- 表格使用：仅在多对象固定字段比较时使用，避免每个小节重复同构表格。",
            "- 图件使用：架构、流程和数据关系优先用图；图中名称必须来自当前项目证据。",
            "- 禁止继承：样本项目名称、业务对象、指标参数、技术版本、本地路径和未验证结论。",
            "",
            "## 人工确认",
            "",
            "- [ ] 已确认样本只用于形式和内容展开方式。",
            "- [ ] 已填写 `编写任务.md` 中的参考样本禁用词。",
            "- [ ] 已将适用特征转换为当前项目规则，而不是逐页仿制。",
            "",
        ]
    )
    return "\n".join(lines)


def distill_workspace(workspace: Path, manifest: dict | None = None) -> Path:
    target = workspace / "02-资料识别" / "参考样本蒸馏规范.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_report(workspace, manifest or load_manifest(workspace)), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="蒸馏目录、内容和样式参考文档的形式特征")
    parser.add_argument("workspace", help="工作区名称或路径")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        target = distill_workspace(workspace)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"已生成参考样本蒸馏规范：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
