from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from common import chapters_for_workspace, current_timestamp, resolve_workspace, timestamp_slug, update_state


CHINESE_NUMBERS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def adjustment_text(workspace: Path) -> str:
    path = workspace / "04-调整意见" / "调整要求.md"
    if not path.exists():
        raise FileNotFoundError(f"调整要求文件不存在：{path}")
    content = path.read_text(encoding="utf-8").strip()
    meaningful_lines = [line for line in content.splitlines() if line.strip() and not line.startswith("#") and "直接使用自然语言" not in line]
    if not meaningful_lines:
        raise ValueError("调整要求尚未填写")
    return content


def detect_chapters(workspace: Path, content: str) -> list[int]:
    chapters = chapters_for_workspace(workspace)
    if any(keyword in content for keyword in ("全局", "全部章节", "整体", "全文", "重排目录")):
        return [chapter.number for chapter in chapters]

    detected: set[int] = set()
    for raw_number in re.findall(r"第\s*([一二三四五六七八九1-9])\s*章", content):
        detected.add(CHINESE_NUMBERS.get(raw_number, int(raw_number) if raw_number.isdigit() else 0))
    for chapter in chapters:
        keywords = (chapter.title, *chapter.sections)
        if any(keyword.lower() in content.lower() for keyword in keywords):
            detected.add(chapter.number)
    chapter_numbers = {chapter.number for chapter in chapters}
    return sorted(number for number in detected if number in chapter_numbers)


def create_snapshot(workspace: Path, affected: list[int]) -> Path:
    chapters = chapters_for_workspace(workspace)
    snapshot = workspace / ".agent" / "snapshots" / timestamp_slug()
    snapshot.mkdir(parents=True, exist_ok=False)
    files = [
        workspace / "04-调整意见" / "调整要求.md",
        workspace / "03-过程成果" / "01-当前提纲.md",
        workspace / "03-过程成果" / "00-章节索引.md",
        workspace / "03-过程成果" / "05-需求追踪矩阵.md",
    ]
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    files.extend(chapter_dir / chapter.filename for chapter in chapters if chapter.number in affected)
    for source in files:
        if source.exists():
            target = snapshot / source.relative_to(workspace)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return snapshot


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_revision_manifest(workspace: Path, affected: list[int], snapshot: Path) -> Path:
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    chapters = chapters_for_workspace(workspace)
    manifest = {
        "created_at": current_timestamp(),
        "snapshot": snapshot.relative_to(workspace).as_posix(),
        "affected_chapters": affected,
        "chapter_hashes": {
            str(chapter.number): file_hash(chapter_dir / chapter.filename)
            for chapter in chapters
            if (chapter_dir / chapter.filename).exists()
        },
    }
    target = workspace / ".agent" / "chapter-context" / "revision-manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def render_plan(workspace: Path, content: str, affected: list[int], snapshot: Path) -> str:
    new_source_dir = workspace / "04-调整意见" / "新增资料放这里"
    new_sources = sorted(path.relative_to(workspace).as_posix() for path in new_source_dir.rglob("*") if path.is_file() and not path.name.startswith("."))
    chapter_names = {chapter.number: chapter.title for chapter in chapters_for_workspace(workspace)}
    lines = [
        "# 修订影响分析",
        "",
        f"- 生成时间：{current_timestamp()}",
        f"- 快照目录：{snapshot.relative_to(workspace).as_posix()}",
        f"- 影响章节：{'、'.join(f'{number} {chapter_names[number]}' for number in affected) if affected else '未自动识别，需 Agent 判断'}",
        "",
        "## 用户调整要求",
        "",
        content,
        "",
        "## 新增资料",
        "",
    ]
    lines.extend(f"- {source}" for source in new_sources)
    if not new_sources:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 执行检查项",
            "",
            "- [ ] 重新识别新增资料并更新资料使用清单",
            "- [ ] 修订受影响章节",
            "- [ ] 检查相邻章节、图表和术语一致性",
            "- [ ] 更新问题与假设和需求追踪矩阵",
            "- [ ] 运行质量检查",
            "- [ ] 归档本轮调整",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_revision(workspace: Path) -> Path:
    content = adjustment_text(workspace)
    affected = detect_chapters(workspace, content)
    snapshot = create_snapshot(workspace, affected)
    write_revision_manifest(workspace, affected, snapshot)
    plan_path = workspace / ".agent" / "chapter-context" / "revision-plan.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(render_plan(workspace, content, affected, snapshot), encoding="utf-8")
    update_state(workspace, "revision_planned", 60, "按修订影响分析修改章节并完成本轮调整")
    return plan_path


def main() -> int:
    parser = argparse.ArgumentParser(description="分析调整要求并创建安全快照")
    parser.add_argument("workspace", help="工作区名称或路径")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        plan_path = prepare_revision(workspace)
    except (ValueError, FileNotFoundError, FileExistsError, OSError) as error:
        parser.error(str(error))
    print(f"已生成修订影响分析：{plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
