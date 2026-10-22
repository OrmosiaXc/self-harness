from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from common import chapters_for_workspace, current_timestamp, resolve_workspace, timestamp_slug, update_state


ADJUSTMENT_TEMPLATE = """# 本轮调整

直接使用自然语言填写。可以指定全局、目录、某章或某节；如果未指定，Agent 自动分析影响范围。
"""


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_revision_scope(workspace: Path) -> list[int]:
    manifest_path = workspace / ".agent" / "chapter-context" / "revision-manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    affected = {int(number) for number in manifest.get("affected_chapters", [])}
    if not affected:
        return []
    previous_hashes = manifest.get("chapter_hashes", {})
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    changed = [
        chapter.number
        for chapter in chapters_for_workspace(workspace)
        if (chapter_dir / chapter.filename).exists()
        and previous_hashes.get(str(chapter.number)) != file_hash(chapter_dir / chapter.filename)
    ]
    unexpected = sorted(number for number in changed if number not in affected)
    if unexpected:
        raise ValueError("检测到修订范围外章节被修改：" + "、".join(str(number) for number in unexpected))
    return changed


def archive_revision(workspace: Path, summary: str) -> Path:
    changed = verify_revision_scope(workspace)
    adjustment_file = workspace / "04-调整意见" / "调整要求.md"
    plan_file = workspace / ".agent" / "chapter-context" / "revision-plan.md"
    manifest_file = workspace / ".agent" / "chapter-context" / "revision-manifest.json"
    archive_dir = workspace / ".agent" / "snapshots" / f"{timestamp_slug()}-completed"
    archive_dir.mkdir(parents=True, exist_ok=False)
    for source in (adjustment_file, plan_file, manifest_file):
        if source.exists():
            shutil.copy2(source, archive_dir / source.name)

    record_file = workspace / "04-调整意见" / "调整记录.md"
    if not record_file.exists():
        record_file.write_text("# 调整记录\n\n| 批次 | 时间 | 调整摘要 | 影响章节 | 结果 |\n|---|---|---|---|---|\n", encoding="utf-8")
    record = record_file.read_text(encoding="utf-8")
    batch = sum(1 for line in record.splitlines() if line.startswith("| R")) + 1
    affected = "、".join(str(number) for number in changed) if changed else "见归档修订影响分析"
    record += f"| R{batch:03d} | {current_timestamp()} | {summary.replace('|', '｜')} | {affected} | 已完成 |\n"
    record_file.write_text(record, encoding="utf-8")
    adjustment_file.write_text(ADJUSTMENT_TEMPLATE, encoding="utf-8")
    update_state(workspace, "writing", 75, "检查修订结果并运行质量检查")
    return archive_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="归档已完成的调整意见")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--summary", required=True, help="本轮修改摘要")
    args = parser.parse_args()
    if not args.summary.strip():
        parser.error("修改摘要不能为空")
    try:
        workspace = resolve_workspace(args.workspace)
        archive_dir = archive_revision(workspace, args.summary.strip())
    except (ValueError, FileNotFoundError, FileExistsError, OSError) as error:
        parser.error(str(error))
    print(f"已归档本轮调整：{archive_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
