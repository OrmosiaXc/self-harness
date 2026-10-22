from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from common import current_timestamp, resolve_workspace


ERROR = "错误"
WARNING = "警告"
PROTECTED_ATTRIBUTES = {"com.apple.provenance", "com.apple.quarantine"}


@dataclass(frozen=True)
class PreflightIssue:
    severity: str
    code: str
    message: str


def opened_by_process(path: Path) -> str:
    lsof = shutil.which("lsof")
    if not lsof or not path.exists():
        return ""
    result = subprocess.run([lsof, str(path)], text=True, capture_output=True, check=False)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return "\n".join(lines[1:]) if len(lines) > 1 else ""


def extended_attributes(path: Path) -> set[str]:
    if not path.exists() or not hasattr(os, "listxattr"):
        return set()
    try:
        return set(os.listxattr(path))
    except OSError:
        return set()


def inspect_word_path(path: Path) -> list[PreflightIssue]:
    issues: list[PreflightIssue] = []
    parent = path.parent
    if not parent.exists():
        issues.append(PreflightIssue(ERROR, "OUTPUT_PARENT_MISSING", f"目标目录不存在：{parent}"))
        return issues
    if not os.access(parent, os.W_OK):
        issues.append(PreflightIssue(ERROR, "OUTPUT_PARENT_NOT_WRITABLE", f"目标目录不可写：{parent}"))
    if not path.exists():
        return issues
    try:
        with path.open("rb") as stream:
            stream.read(4)
    except OSError as error:
        issues.append(PreflightIssue(ERROR, "DOCX_NOT_READABLE", f"文件不可读：{error}"))
        return issues
    if not os.access(path, os.W_OK):
        issues.append(PreflightIssue(ERROR, "DOCX_NOT_WRITABLE", f"文件不可写：{path}"))
    process_detail = opened_by_process(path)
    if process_detail:
        issues.append(PreflightIssue(ERROR, "DOCX_IN_USE", "文件正被 Word、WPS 或其他进程占用，请关闭后再替换"))
    protected = extended_attributes(path) & PROTECTED_ATTRIBUTES
    if protected:
        issues.append(
            PreflightIssue(
                WARNING,
                "MACOS_PROTECTED_ATTRIBUTE",
                "检测到 macOS 文件属性：" + "、".join(sorted(protected)) + "；若读取失败，请另存可编辑副本或上传附件",
            )
        )
    try:
        with zipfile.ZipFile(path) as archive:
            damaged = archive.testzip()
            if damaged:
                issues.append(PreflightIssue(ERROR, "DOCX_PACKAGE_DAMAGED", f"DOCX 包含损坏组件：{damaged}"))
    except zipfile.BadZipFile:
        issues.append(PreflightIssue(ERROR, "DOCX_PACKAGE_INVALID", "文件不是有效的 DOCX 压缩包"))
    return issues


def assert_output_available(path: Path) -> None:
    errors = [issue for issue in inspect_word_path(path) if issue.severity == ERROR]
    if errors:
        raise OSError("；".join(issue.message for issue in errors))


def newest_docx(workspace: Path) -> Path:
    candidates = sorted(
        (workspace / "05-交付成果" / "02-正式版").glob("*.docx"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("正式版目录中没有 DOCX，请使用 --docx 指定文件")
    return candidates[0]


def render_report(path: Path, issues: list[PreflightIssue]) -> str:
    lines = [
        "# Word 编辑预检报告",
        "",
        f"- 文件：`{path}`",
        f"- 检查时间：{current_timestamp()}",
        f"- 结论：{'存在阻塞' if any(issue.severity == ERROR for issue in issues) else '可继续'}",
        "",
        "| 级别 | 代码 | 内容 |",
        "|---|---|---|",
    ]
    if issues:
        lines.extend(f"| {issue.severity} | {issue.code} | {issue.message} |" for issue in issues)
    else:
        lines.append("| 提示 | OK | 文件可读写、未被占用且 DOCX 包结构有效 |")
    lines.extend(
        [
            "",
            "预检不会移除扩展属性、关闭应用或覆盖文件。发现保护属性时优先让用户另存可编辑副本或上传附件。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="在编辑或替换 Word 前检查文件可用性")
    parser.add_argument("workspace", help="工作区名称或路径")
    parser.add_argument("--docx", help="需要检查的 DOCX；默认选择正式版目录中的最新文件")
    args = parser.parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        path = Path(args.docx).expanduser().resolve() if args.docx else newest_docx(workspace)
        issues = inspect_word_path(path)
        report = workspace / "03-过程成果" / "09-Word编辑预检报告.md"
        report.write_text(render_report(path, issues), encoding="utf-8")
    except (FileNotFoundError, OSError) as error:
        parser.error(str(error))
    errors = sum(issue.severity == ERROR for issue in issues)
    print(f"Word 编辑预检完成：{errors} 个阻塞")
    print(report)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
