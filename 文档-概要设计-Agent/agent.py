#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parent
SCRIPT_DIR = AGENT_ROOT / "skills" / "write-high-level-design" / "scripts"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="中文概要设计 Agent 命令入口")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="新建文档工作区")
    new_parser.add_argument("name", help="文档或项目名称")

    inspect_parser = subparsers.add_parser("inspect", help="识别工作区资料")
    inspect_parser.add_argument("workspace", help="工作区名称或路径")

    distill_parser = subparsers.add_parser("distill", help="重新蒸馏参考样本的结构与篇幅特征")
    distill_parser.add_argument("workspace", help="工作区名称或路径")

    outline_parser = subparsers.add_parser("outline", help="生成标准提纲和章节骨架")
    outline_parser.add_argument("workspace", help="工作区名称或路径")
    outline_parser.add_argument("--force", action="store_true", help="覆盖 Agent 生成的现有提纲骨架")

    validate_parser = subparsers.add_parser("validate", help="执行质量检查")
    validate_parser.add_argument("workspace", help="工作区名称或路径")
    validate_parser.add_argument("--mode", choices=("structure", "final"), default="structure")

    render_parser = subparsers.add_parser("render", help="合并章节并生成交付文件")
    render_parser.add_argument("workspace", help="工作区名称或路径")
    render_parser.add_argument("--format", choices=("markdown", "docx", "all"), default="all")
    render_parser.add_argument("--allow-incomplete", action="store_true", help="允许带占位符生成预览稿")
    render_parser.add_argument("--publish-dir", help="将正式成果复制到用户明确指定的外部目录")

    chapter_parser = subparsers.add_parser("render-chapter", help="生成单章 Markdown/DOCX 预览，不合并总文档")
    chapter_parser.add_argument("workspace", help="工作区名称或路径")
    chapter_parser.add_argument("--chapter", type=int, required=True, help="章节编号")
    chapter_parser.add_argument("--format", choices=("markdown", "docx", "all"), default="all")

    qa_parser = subparsers.add_parser("qa", help="检查 DOCX 结构并渲染全部页面")
    qa_parser.add_argument("workspace", help="工作区名称或路径")
    qa_parser.add_argument("--docx", help="指定 DOCX；默认使用正式版目录中最新文件")
    qa_parser.add_argument("--confirm-visual", action="store_true", help="仅在逐页目视检查完成后使用")

    preflight_parser = subparsers.add_parser("preflight-word", help="编辑或替换 Word 前检查占用、权限和文件保护")
    preflight_parser.add_argument("workspace", help="工作区名称或路径")
    preflight_parser.add_argument("--docx", help="指定 DOCX；默认使用正式版目录中最新文件")

    status_parser = subparsers.add_parser("status", help="显示长任务状态")
    status_parser.add_argument("workspace", help="工作区名称或路径")

    checkpoint_parser = subparsers.add_parser("checkpoint", help="记录长任务检查点")
    checkpoint_parser.add_argument("workspace", help="工作区名称或路径")
    checkpoint_parser.add_argument("--step", required=True, help="当前或刚完成的工作项")
    checkpoint_parser.add_argument("--status", choices=("in_progress", "completed", "blocked"), required=True)
    checkpoint_parser.add_argument("--next", dest="next_action", required=True, help="下一步唯一动作")
    checkpoint_parser.add_argument("--artifact", action="append", default=[], help="本阶段产物，可重复传入")
    checkpoint_parser.add_argument("--verification", default="尚未执行", help="验证命令或结果")
    checkpoint_parser.add_argument("--blocker", default="无", help="真实阻塞事项")

    revision_parser = subparsers.add_parser("revise-plan", help="分析本轮调整影响范围")
    revision_parser.add_argument("workspace", help="工作区名称或路径")

    revision_done_parser = subparsers.add_parser("revise-done", help="归档已完成的调整")
    revision_done_parser.add_argument("workspace", help="工作区名称或路径")
    revision_done_parser.add_argument("--summary", required=True, help="本轮修改摘要")

    return parser


def script_arguments(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.command == "new":
        return "new_document.py", [args.name]
    if args.command == "inspect":
        return "inspect_sources.py", [args.workspace]
    if args.command == "distill":
        return "distill_reference_samples.py", [args.workspace]
    if args.command == "outline":
        return "build_outline.py", [args.workspace, *(["--force"] if args.force else [])]
    if args.command == "validate":
        return "validate_document.py", [args.workspace, "--mode", args.mode]
    if args.command == "render":
        extra = [args.workspace, "--format", args.format]
        if args.allow_incomplete:
            extra.append("--allow-incomplete")
        if args.publish_dir:
            extra.extend(["--publish-dir", args.publish_dir])
        return "render_document.py", extra
    if args.command == "render-chapter":
        return "render_document.py", [args.workspace, "--chapter", str(args.chapter), "--format", args.format]
    if args.command == "qa":
        extra = [args.workspace]
        if args.docx:
            extra.extend(["--docx", args.docx])
        if args.confirm_visual:
            extra.append("--confirm-visual")
        return "qa_document.py", extra
    if args.command == "preflight-word":
        extra = [args.workspace]
        if args.docx:
            extra.extend(["--docx", args.docx])
        return "preflight_word.py", extra
    if args.command == "status":
        return "show_status.py", [args.workspace]
    if args.command == "checkpoint":
        extra = [
            args.workspace,
            "--step",
            args.step,
            "--status",
            args.status,
            "--next",
            args.next_action,
            "--verification",
            args.verification,
            "--blocker",
            args.blocker,
        ]
        for artifact in args.artifact:
            extra.extend(["--artifact", artifact])
        return "checkpoint.py", extra
    if args.command == "revise-plan":
        return "prepare_revision.py", [args.workspace]
    if args.command == "revise-done":
        return "complete_revision.py", [args.workspace, "--summary", args.summary]
    raise ValueError(f"不支持的命令：{args.command}")


def main() -> int:
    args = build_parser().parse_args()
    script_name, extra_args = script_arguments(args)
    script_path = SCRIPT_DIR / script_name
    result = subprocess.run([sys.executable, str(script_path), *extra_args], cwd=AGENT_ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
