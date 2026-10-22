#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw


PAGE_PATTERN = re.compile(r"(\d+)$")
DEFAULT_COLUMNS = 3
DEFAULT_ROWS = 3
LABEL_HEIGHT = 34
GAP = 18
BACKGROUND = (239, 243, 248)
LABEL_COLOR = (20, 35, 51)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把逐页 PNG 合成为 PPT QA 总览图")
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--columns", type=int, default=DEFAULT_COLUMNS)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    return parser.parse_args()


def image_page(path: Path) -> int:
    match = PAGE_PATTERN.search(path.stem)
    return int(match.group(1)) if match else 10**9


def find_images(image_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in image_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".png"
            and path.stem.startswith("slide")
        ),
        key=image_page,
    )


def make_sheet(paths: list[Path], output_path: Path, columns: int, rows: int) -> None:
    with Image.open(paths[0]) as first:
        ratio = first.width / first.height
    cell_width = 560
    cell_height = round(cell_width / ratio)
    sheet_width = GAP + columns * (cell_width + GAP)
    sheet_height = GAP + rows * (cell_height + LABEL_HEIGHT + GAP)
    sheet = Image.new("RGB", (sheet_width, sheet_height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        row, column = divmod(index, columns)
        x = GAP + column * (cell_width + GAP)
        y = GAP + row * (cell_height + LABEL_HEIGHT + GAP)
        with Image.open(path) as image:
            rendered = image.convert("RGB")
            rendered.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
            image_x = x + (cell_width - rendered.width) // 2
            image_y = y + (cell_height - rendered.height) // 2
            sheet.paste(rendered, (image_x, image_y))
        draw.text((x, y + cell_height + 7), path.stem, fill=LABEL_COLOR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def main() -> None:
    args = parse_args()
    if args.columns < 1 or args.rows < 1:
        raise SystemExit("columns 和 rows 必须大于 0")
    images = find_images(args.image_dir)
    if not images:
        raise SystemExit(f"未找到 slide*.png：{args.image_dir}")
    page_size = args.columns * args.rows
    sheet_count = math.ceil(len(images) / page_size)
    for sheet_index in range(sheet_count):
        start = sheet_index * page_size
        group = images[start : start + page_size]
        first_page = image_page(group[0])
        last_page = image_page(group[-1])
        output_path = args.output_dir / (
            f"00_PPTX总览_{first_page:02d}-{last_page:02d}页.png"
        )
        make_sheet(group, output_path, args.columns, args.rows)
        print(f"已生成：{output_path}")


if __name__ == "__main__":
    main()
