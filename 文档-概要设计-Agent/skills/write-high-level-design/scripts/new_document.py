from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import agent_root, update_state, validate_document_name


TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".txt"}


def replace_document_token(workspace: Path, name: str) -> None:
    for path in workspace.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            content = path.read_text(encoding="utf-8")
            if "{{DOCUMENT_NAME}}" in content:
                path.write_text(content.replace("{{DOCUMENT_NAME}}", name), encoding="utf-8")


def create_workspace(name: str) -> Path:
    normalized_name = validate_document_name(name)
    root = agent_root()
    template = root / "workspaces" / "_新文档模板"
    destination = root / "workspaces" / normalized_name
    if not template.is_dir():
        raise FileNotFoundError(f"工作区模板不存在：{template}")
    if destination.exists():
        raise FileExistsError(f"工作区已存在，不会覆盖：{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(template, destination)
    replace_document_token(destination, normalized_name)
    update_state(destination, "created", 0, "填写编写任务并投递资料")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="新建概要设计工作区")
    parser.add_argument("name", help="文档或项目名称")
    args = parser.parse_args()
    try:
        destination = create_workspace(args.name)
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        parser.error(str(error))
    print(f"已创建工作区：{destination}")
    print("下一步：填写 00-任务说明/编写任务.md；所有资料可直接投递，需保持原位的资料或源码在外部索引中登记只读路径")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
