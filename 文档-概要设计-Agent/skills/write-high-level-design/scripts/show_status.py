from __future__ import annotations

import argparse
import json

from common import load_state, resolve_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description="显示概要设计长任务状态")
    parser.add_argument("workspace", help="工作区名称或路径")
    args = parser.parse_args()
    workspace = resolve_workspace(args.workspace)
    state = load_state(workspace)
    if not state:
        parser.error("状态文件不存在或格式无效")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
