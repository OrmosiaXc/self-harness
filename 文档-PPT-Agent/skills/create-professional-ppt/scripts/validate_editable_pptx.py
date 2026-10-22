#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree


NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
SLIDE_NAME_PATTERN = re.compile(r"slide(\d+)\.xml$")
PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:lorem|ipsum|tbd|todo|xxxx)\b|占位符|待替换",
    re.IGNORECASE,
)
LOCAL_PATH_PATTERN = re.compile(r"/Users/[^/\s]+/|[A-Za-z]:\\Users\\", re.IGNORECASE)
BOUNDARY_TOLERANCE_EMU = 100
FULL_SLIDE_RATIO = 0.95
MIN_NATIVE_OBJECTS = 4
EMU_PER_INCH = 914400


@dataclass(frozen=True)
class Bounds:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class SlideStats:
    page: int
    text_shapes: int
    autofit_text_shapes: int
    shapes: int
    pictures: int
    connectors: int
    graphic_frames: int
    text_characters: int
    objects_out_of_bounds: int
    full_slide_pictures: int

    @property
    def native_objects(self) -> int:
        return self.shapes + self.connectors + self.graphic_frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证 PPTX 的可编辑性、内容完整性和对象边界")
    parser.add_argument("pptx", type=Path, help="待检查的 PPTX")
    parser.add_argument("--json", type=Path, dest="json_output", required=True)
    parser.add_argument("--markdown", type=Path, dest="markdown_output", required=True)
    parser.add_argument("--expected-slides", type=int)
    parser.add_argument("--expected-titles", type=Path, help="JSON 数组或每行一个标题的文本文件")
    parser.add_argument("--forbidden-phrase", action="append", default=[])
    parser.add_argument("--layout-report", type=Path)
    parser.add_argument("--allow-missing-notes", action="store_true")
    parser.add_argument("--allow-missing-autofit", action="store_true")
    parser.add_argument("--allow-full-page-raster", action="store_true")
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="检查标题留白内容页，禁止对象进入父任务保留区",
    )
    parser.add_argument(
        "--reserved-title-height-in",
        type=float,
        default=1.15,
        help="从页面顶部开始计算的标题保留区高度，单位英寸",
    )
    parser.add_argument(
        "--reserved-footer-height-in",
        type=float,
        default=0.0,
        help="从页面底部开始计算的页脚保留区高度，单位英寸",
    )
    return parser.parse_args()


def numeric_slide_key(name: str) -> int:
    match = SLIDE_NAME_PATTERN.search(name)
    if match is None:
        raise ValueError(f"无法识别幻灯片文件名：{name}")
    return int(match.group(1))


def parse_xml(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    return ElementTree.fromstring(archive.read(name))


def read_slide_size(archive: zipfile.ZipFile) -> tuple[int, int]:
    root = parse_xml(archive, "ppt/presentation.xml")
    slide_size = root.find("p:sldSz", NAMESPACES)
    if slide_size is None:
        raise ValueError("PPTX 中缺少幻灯片尺寸")
    return int(slide_size.attrib["cx"]), int(slide_size.attrib["cy"])


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def extract_slide_text(root: ElementTree.Element) -> str:
    return "".join(node.text or "" for node in root.findall(".//a:t", NAMESPACES))


def extract_bounds(element: ElementTree.Element) -> Bounds | None:
    transform = element.find("p:spPr/a:xfrm", NAMESPACES)
    if transform is None:
        transform = element.find("p:xfrm", NAMESPACES)
    if transform is None:
        return None
    offset = transform.find("a:off", NAMESPACES)
    extent = transform.find("a:ext", NAMESPACES)
    if offset is None or extent is None:
        return None
    return Bounds(
        x=int(offset.attrib.get("x", "0")),
        y=int(offset.attrib.get("y", "0")),
        width=int(extent.attrib.get("cx", "0")),
        height=int(extent.attrib.get("cy", "0")),
    )


def is_out_of_bounds(bounds: Bounds, slide_width: int, slide_height: int) -> bool:
    return (
        bounds.x < -BOUNDARY_TOLERANCE_EMU
        or bounds.y < -BOUNDARY_TOLERANCE_EMU
        or bounds.right > slide_width + BOUNDARY_TOLERANCE_EMU
        or bounds.bottom > slide_height + BOUNDARY_TOLERANCE_EMU
    )


def picture_is_full_slide(
    picture: ElementTree.Element,
    slide_width: int,
    slide_height: int,
) -> bool:
    bounds = extract_bounds(picture)
    if bounds is None:
        return False
    return (
        bounds.width >= slide_width * FULL_SLIDE_RATIO
        and bounds.height >= slide_height * FULL_SLIDE_RATIO
        and bounds.x <= slide_width * 0.03
        and bounds.y <= slide_height * 0.03
    )


def has_autofit(shape: ElementTree.Element) -> bool:
    return (
        shape.find(".//a:normAutofit", NAMESPACES) is not None
        or shape.find(".//a:spAutoFit", NAMESPACES) is not None
    )


def inspect_reserved_zones(
    root: ElementTree.Element,
    page: int,
    slide_height: int,
    title_height: int,
    footer_height: int,
) -> list[dict[str, object]]:
    object_groups = (
        ("shape", root.findall(".//p:sp", NAMESPACES)),
        ("picture", root.findall(".//p:pic", NAMESPACES)),
        ("connector", root.findall(".//p:cxnSp", NAMESPACES)),
        ("graphic_frame", root.findall(".//p:graphicFrame", NAMESPACES)),
    )
    issues: list[dict[str, object]] = []
    footer_top = slide_height - footer_height
    for object_type, elements in object_groups:
        for index, element in enumerate(elements, start=1):
            bounds = extract_bounds(element)
            if bounds is None:
                continue
            non_visual_properties = element.find(".//p:cNvPr", NAMESPACES)
            object_name = (
                non_visual_properties.attrib.get("name", "")
                if non_visual_properties is not None
                else ""
            )
            if title_height > 0 and bounds.y < title_height and bounds.bottom > 0:
                issues.append(
                    {
                        "page": page,
                        "zone": "title",
                        "object_type": object_type,
                        "object_index": index,
                        "object_name": object_name,
                        "bounds": asdict(bounds),
                    }
                )
            if (
                footer_height > 0
                and bounds.y < slide_height
                and bounds.bottom > footer_top
            ):
                issues.append(
                    {
                        "page": page,
                        "zone": "footer",
                        "object_type": object_type,
                        "object_index": index,
                        "object_name": object_name,
                        "bounds": asdict(bounds),
                    }
                )
    return issues


def inspect_slide(
    root: ElementTree.Element,
    page: int,
    slide_width: int,
    slide_height: int,
) -> tuple[SlideStats, list[dict[str, object]]]:
    shapes = root.findall(".//p:sp", NAMESPACES)
    pictures = root.findall(".//p:pic", NAMESPACES)
    connectors = root.findall(".//p:cxnSp", NAMESPACES)
    graphic_frames = root.findall(".//p:graphicFrame", NAMESPACES)
    all_objects = [*shapes, *pictures, *connectors, *graphic_frames]
    out_of_bounds: list[dict[str, object]] = []
    for index, element in enumerate(all_objects, start=1):
        bounds = extract_bounds(element)
        if bounds is not None and is_out_of_bounds(bounds, slide_width, slide_height):
            out_of_bounds.append(
                {
                    "page": page,
                    "object_index": index,
                    "bounds": asdict(bounds),
                }
            )

    text_shapes = [
        shape
        for shape in shapes
        if shape.find(".//p:txBody", NAMESPACES) is not None
        and shape.find(".//a:t", NAMESPACES) is not None
    ]
    stats = SlideStats(
        page=page,
        text_shapes=len(text_shapes),
        autofit_text_shapes=sum(has_autofit(shape) for shape in text_shapes),
        shapes=len(shapes),
        pictures=len(pictures),
        connectors=len(connectors),
        graphic_frames=len(graphic_frames),
        text_characters=sum(
            len(node.text or "")
            for shape in text_shapes
            for node in shape.findall(".//a:t", NAMESPACES)
        ),
        objects_out_of_bounds=len(out_of_bounds),
        full_slide_pictures=sum(
            picture_is_full_slide(picture, slide_width, slide_height)
            for picture in pictures
        ),
    )
    return stats, out_of_bounds


def load_expected_titles(path: Path | None) -> list[str]:
    if path is None:
        return []
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(content)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("expected-titles JSON 必须是字符串数组")
        return [item.strip() for item in value if item.strip()]
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_layout_report(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("布局报告必须是 JSON 对象")
    return value


def inspect_pptx(args: argparse.Namespace) -> dict[str, object]:
    expected_titles = load_expected_titles(args.expected_titles)
    expected_slides = args.expected_slides or len(expected_titles) or None
    with zipfile.ZipFile(args.pptx) as archive:
        slide_width, slide_height = read_slide_size(archive)
        slide_names = sorted(
            (
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ),
            key=numeric_slide_key,
        )
        roots = [(name, parse_xml(archive, name)) for name in slide_names]
        title_height = int(args.reserved_title_height_in * EMU_PER_INCH)
        footer_height = int(args.reserved_footer_height_in * EMU_PER_INCH)
        if args.content_only and (
            title_height < 0
            or footer_height < 0
            or title_height + footer_height >= slide_height
        ):
            raise ValueError("标题区和页脚区高度必须为非负数，且总和小于页面高度")
        inspected = [
            inspect_slide(root, numeric_slide_key(name), slide_width, slide_height)
            for name, root in roots
        ]
        slides = [item[0] for item in inspected]
        out_of_bounds = [issue for item in inspected for issue in item[1]]
        reserved_zone_issues = (
            [
                issue
                for name, root in roots
                for issue in inspect_reserved_zones(
                    root,
                    numeric_slide_key(name),
                    slide_height,
                    title_height,
                    footer_height,
                )
            ]
            if args.content_only
            else []
        )
        slide_texts = [extract_slide_text(root) for _, root in roots]
        notes_count = sum(
            name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
            for name in archive.namelist()
        )

    missing_title_pages = [
        page
        for page, expected_title in enumerate(expected_titles, start=1)
        if page > len(slide_texts)
        or normalize_text(expected_title) not in normalize_text(slide_texts[page - 1])
    ]
    placeholder_pages = [
        page
        for page, slide_text in enumerate(slide_texts, start=1)
        if PLACEHOLDER_PATTERN.search(slide_text)
    ]
    forbidden_phrase_pages = [
        page
        for page, slide_text in enumerate(slide_texts, start=1)
        if any(phrase in slide_text for phrase in args.forbidden_phrase)
    ]
    local_path_pages = [
        page
        for page, slide_text in enumerate(slide_texts, start=1)
        if LOCAL_PATH_PATTERN.search(slide_text)
    ]
    pages_without_autofit = [
        slide.page
        for slide in slides
        if slide.text_shapes != slide.autofit_text_shapes
    ]
    flattened_pages = [slide.page for slide in slides if slide.full_slide_pictures > 0]
    layout_report = load_layout_report(args.layout_report)

    checks = {
        "presentation_has_slides": bool(slides),
        "page_count_matches": expected_slides is None or len(slides) == expected_slides,
        "notes_count_matches": args.allow_missing_notes or notes_count == len(slides),
        "every_page_has_editable_text": all(slide.text_shapes > 0 for slide in slides),
        "every_text_shape_has_autofit": args.allow_missing_autofit or not pages_without_autofit,
        "no_objects_out_of_bounds": not out_of_bounds,
        "no_full_slide_raster_pages": args.allow_full_page_raster or not flattened_pages,
        "every_page_has_native_objects": all(
            slide.native_objects >= MIN_NATIVE_OBJECTS for slide in slides
        ),
        "expected_titles_present": not missing_title_pages,
        "no_placeholder_text": not placeholder_pages,
        "forbidden_phrases_absent": not forbidden_phrase_pages,
        "no_local_path_leaks": not local_path_pages,
        "build_layout_report_passed": layout_report is None
        or (
            layout_report.get("status") == "passed"
            and not layout_report.get("outOfBounds")
            and not layout_report.get("footerCollisions")
            and not layout_report.get("estimatedOverflow")
        ),
        "reserved_integration_zones_clear": not reserved_zone_issues,
    }
    totals = {
        "slides": len(slides),
        "notes": notes_count,
        "text_shapes": sum(slide.text_shapes for slide in slides),
        "autofit_text_shapes": sum(slide.autofit_text_shapes for slide in slides),
        "shapes": sum(slide.shapes for slide in slides),
        "pictures": sum(slide.pictures for slide in slides),
        "connectors": sum(slide.connectors for slide in slides),
        "graphic_frames": sum(slide.graphic_frames for slide in slides),
        "text_characters": sum(slide.text_characters for slide in slides),
    }
    return {
        "pptx": str(args.pptx.resolve()),
        "status": "passed" if all(checks.values()) else "failed",
        "expected_slides": expected_slides,
        "slide_size_emu": {"width": slide_width, "height": slide_height},
        "checks": checks,
        "totals": totals,
        "missing_title_pages": missing_title_pages,
        "placeholder_pages": placeholder_pages,
        "forbidden_phrase_pages": forbidden_phrase_pages,
        "local_path_pages": local_path_pages,
        "pages_without_autofit": pages_without_autofit,
        "flattened_pages": flattened_pages,
        "objects_out_of_bounds": out_of_bounds,
        "reserved_zone_issues": reserved_zone_issues,
        "reserved_zones": {
            "content_only": args.content_only,
            "title_height_in": args.reserved_title_height_in if args.content_only else 0,
            "footer_height_in": args.reserved_footer_height_in if args.content_only else 0,
        },
        "layout_report": layout_report,
        "slides": [
            {**asdict(slide), "native_objects": slide.native_objects}
            for slide in slides
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    totals = report["totals"]
    checks = report["checks"]
    assert isinstance(totals, dict)
    assert isinstance(checks, dict)
    labels = {
        "presentation_has_slides": "演示文稿包含页面",
        "page_count_matches": "页数符合预期",
        "notes_count_matches": "演讲者备注与页数一致",
        "every_page_has_editable_text": "每页均包含可编辑文本",
        "every_text_shape_has_autofit": "文本框均启用自动适配",
        "no_objects_out_of_bounds": "不存在画布越界对象",
        "no_full_slide_raster_pages": "不存在整页栅格图片",
        "every_page_has_native_objects": "每页包含足够原生对象",
        "expected_titles_present": "预期标题均存在",
        "no_placeholder_text": "不存在占位文字",
        "forbidden_phrases_absent": "不存在禁用措辞",
        "no_local_path_leaks": "不存在本机路径泄漏",
        "build_layout_report_passed": "生成阶段布局报告通过",
        "reserved_integration_zones_clear": "标题和页脚保留区无子章节对象",
    }
    lines = [
        "# 可编辑 PowerPoint 结构验证报告",
        "",
        f"- 文件：`{report['pptx']}`",
        f"- 状态：**{report['status']}**",
        f"- 页数：{totals['slides']}",
        f"- 演讲者备注：{totals['notes']}",
        f"- 可编辑文本框：{totals['text_shapes']}",
        f"- 自动适配文本框：{totals['autofit_text_shapes']}",
        f"- 原生形状：{totals['shapes']}",
        f"- 图片对象：{totals['pictures']}",
        "",
        "## 核心检查",
        "",
    ]
    lines.extend(
        f"- {'通过' if passed else '未通过'}：{labels[name]}"
        for name, passed in checks.items()
    )
    lines.extend(
        [
            "",
            "## 逐页统计",
            "",
            "| 页码 | 文本框 | 自动适配 | 形状 | 连接线 | 图片 | 越界 | 原生对象 |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    slides = report["slides"]
    assert isinstance(slides, list)
    lines.extend(
        "| {page} | {text_shapes} | {autofit_text_shapes} | {shapes} | "
        "{connectors} | {pictures} | {objects_out_of_bounds} | {native_objects} |".format(
            **slide
        )
        for slide in slides
    )
    reserved_zone_issues = report["reserved_zone_issues"]
    assert isinstance(reserved_zone_issues, list)
    if reserved_zone_issues:
        lines.extend(
            [
                "",
                "## 集成保留区问题",
                "",
                "| 页码 | 区域 | 对象类型 | 对象名称 |",
                "|---:|---|---|---|",
            ]
        )
        lines.extend(
            "| {page} | {zone} | {object_type} | {object_name} |".format(**issue)
            for issue in reserved_zone_issues
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "结构验证用于发现页数、标题、备注、可编辑对象、边界和禁止项问题，"
            "不能替代 PPTX → PDF → 逐页图片后的人工视觉检查。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if not args.pptx.is_file():
        raise SystemExit(f"PPTX 不存在：{args.pptx}")
    report = inspect_pptx(args)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        f"{json.dumps(report, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report["checks"]}, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
