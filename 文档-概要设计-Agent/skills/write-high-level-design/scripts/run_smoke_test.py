from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

from common import agent_root


def run(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"命令执行失败：{' '.join(command)}\n{result.stdout}\n{result.stderr}")


def run_failure(command: list[str], cwd: Path, environment: dict[str, str], expected: str) -> None:
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True, check=False)
    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0 or expected not in combined:
        raise RuntimeError(f"命令未按预期失败：{' '.join(command)}\n{combined}")


def fill_sample_content(workspace: Path) -> None:
    task_file = workspace / "00-任务说明" / "编写任务.md"
    task = task_file.read_text(encoding="utf-8").replace("- 项目名称：\n", "- 项目名称：示例项目\n")
    task_file.write_text(task, encoding="utf-8")

    source_file = workspace / "01-资料投递" / "所有参考资料放这里" / "项目需求.md"
    source_file.write_text("# 项目需求\n\n系统应提供统一用户认证、业务处理和审计能力。\n", encoding="utf-8")
    sample_file = workspace / "01-资料投递" / "所有参考资料放这里" / "参考概要设计样例.md"
    sample_file.write_text(
        "# 样例结构\n\n## 总体设计\n\n以连续正文说明架构关系。\n\n## 业务流程\n\n用流程图解释协作顺序。\n",
        encoding="utf-8",
    )

    external_source = workspace.parents[1] / "external-python-source"
    external_source.mkdir(parents=True, exist_ok=True)
    (external_source / "service.py").write_text("def calculate(value: float) -> float:\n    return value * 2\n", encoding="utf-8")
    external_index = workspace / "01-资料投递" / "外部资料与源码索引.md"
    external_index.write_text(
        "# 外部资料与源码索引\n\n"
        "| 类型 | 名称 | 绝对路径 | 用途 | 只读 |\n"
        "|---|---|---|---|---|\n"
        f"| Python 源码 | 示例算法 | {external_source} | 算法入口和处理逻辑证据 | 是 |\n",
        encoding="utf-8",
    )


def complete_chapters(workspace: Path) -> None:
    chapter_dir = workspace / "03-过程成果" / "02-章节草稿"
    for path in chapter_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        content = content.replace("资料编号：待补充", "资料编号：R-001")
        section_index = 0

        def replacement(_: re.Match[str]) -> str:
            nonlocal section_index
            section_index += 1
            topic = f"{path.stem}设计主题{section_index}"
            return (
                f"本节围绕{topic}说明设计对象、职责范围和协作边界。"
                "相关能力由当前系统负责组织，外部参与方只通过约定接口交换必要信息，"
                "未取得证据的规模和时延不写成验收承诺。\n\n"
                f"{topic}按照输入校验、业务处理、状态记录和结果输出的顺序运行。"
                "异常时记录原因并进入可追踪状态，必要时执行重试或人工确认；"
                "后续通过接口检查、日志审计和业务场景验证设计结果。"
            )

        content = re.sub(
            r">\s*\[待编写]\s*根据资料使用清单补充内容、依据和待确认项。",
            replacement,
            content,
        )
        path.write_text(content, encoding="utf-8")
    trace_file = workspace / "03-过程成果" / "05-需求追踪矩阵.md"
    trace_file.write_text(
        "# 合同与需求追踪矩阵\n\n"
        "| 合同/需求编号 | 需求摘要 | 资料来源 | 证据状态 | 体系/子系统 | 功能模块 | 接口/数据 | 文档章节 | 验证方式 | 覆盖状态 |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| REQ-001 | 提供统一用户认证 | R-001 | C/S | 安全体系 | 身份认证模块 | 登录接口 | 2、3、7 | 接口与日志检查 | 已覆盖 |\n",
        encoding="utf-8",
    )
    ledger = workspace / "02-资料识别" / "源码与材料理解台账.md"
    ledger.write_text(
        "# 源码与材料理解台账\n\n"
        "## 结论摘要\n\n"
        "示例需求资料要求统一用户认证、业务处理和审计。本冒烟测试没有外部源码，仅验证 Agent 工作流。\n\n"
        "## 证据状态\n\n- R-001：C-项目需求。\n",
        encoding="utf-8",
    )


def smoke_test() -> None:
    source_root = agent_root()
    preserved_directory = os.environ.get("HLD_AGENT_SMOKE_DIR", "").strip()
    context = (
        nullcontext(preserved_directory)
        if preserved_directory
        else tempfile.TemporaryDirectory(prefix="hld-agent-smoke-")
    )
    with context as temporary_directory:
        Path(temporary_directory).mkdir(parents=True, exist_ok=True)
        test_root = Path(temporary_directory) / "agent"
        if test_root.exists():
            raise FileExistsError(f"冒烟测试保留目录已存在：{test_root}")
        shutil.copytree(source_root, test_root, ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__"))
        environment = os.environ.copy()
        environment["HLD_AGENT_ROOT"] = str(test_root)
        agent = [sys.executable, str(test_root / "agent.py")]

        run([*agent, "new", "冒烟测试概要设计"], test_root, environment)
        workspace = test_root / "workspaces" / "冒烟测试概要设计"
        fill_sample_content(workspace)
        run([*agent, "inspect", "冒烟测试概要设计"], test_root, environment)
        manifest_path = workspace / ".agent" / "source-manifest" / "source-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        external_records = [record for record in manifest["sources"] if record["source_kind"] == "Python 源码"]
        if len(external_records) != 1 or external_records[0]["access_status"] != "可访问":
            raise RuntimeError("外部源码索引未正确登记")
        sample_distillation = workspace / "02-资料识别" / "参考样本蒸馏规范.md"
        if "参考概要设计样例.md" not in sample_distillation.read_text(encoding="utf-8"):
            raise RuntimeError("参考样本未完成形式特征蒸馏")
        sample_distillation.write_text(
            sample_distillation.read_text(encoding="utf-8").replace("- [ ]", "- [x]"),
            encoding="utf-8",
        )
        run([*agent, "outline", "冒烟测试概要设计"], test_root, environment)
        run([*agent, "render-chapter", "冒烟测试概要设计", "--chapter", "3", "--format", "all"], test_root, environment)
        adjustment_file = workspace / "04-调整意见" / "调整要求.md"
        adjustment_file.write_text("# 本轮调整\n\n第三章增加统一认证架构说明。\n", encoding="utf-8")
        run([*agent, "revise-plan", "冒烟测试概要设计"], test_root, environment)
        outside_scope = workspace / "03-过程成果" / "02-章节草稿" / "02-需求分析.md"
        outside_scope_original = outside_scope.read_text(encoding="utf-8")
        outside_scope.write_text(outside_scope_original + "\n\n范围外临时修改。\n", encoding="utf-8")
        run_failure(
            [*agent, "revise-done", "冒烟测试概要设计", "--summary", "范围完整性测试"],
            test_root,
            environment,
            "检测到修订范围外章节被修改",
        )
        outside_scope.write_text(outside_scope_original, encoding="utf-8")
        run([*agent, "revise-done", "冒烟测试概要设计", "--summary", "补充统一认证架构调整计划"], test_root, environment)
        run([*agent, "validate", "冒烟测试概要设计", "--mode", "structure"], test_root, environment)
        complete_chapters(workspace)
        depth_probe = workspace / "03-过程成果" / "02-章节草稿" / "01-概述.md"
        depth_original = depth_probe.read_text(encoding="utf-8")
        depth_probe.write_text(depth_original + "\n\n## 1.99 临时浅层检查\n\n过短。\n", encoding="utf-8")
        run_failure([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment, "质量检查完成")
        review = json.loads((workspace / ".agent" / "reviews" / "latest.json").read_text(encoding="utf-8"))
        if not any(issue["code"] == "SECTION_TOO_SHALLOW" for issue in review["issues"]):
            raise RuntimeError("章节内容深度门禁未触发")
        depth_probe.write_text(depth_original + "\n\n本地资料路径为 /Users/example/reference.docx。\n", encoding="utf-8")
        run_failure([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment, "质量检查完成")
        review = json.loads((workspace / ".agent" / "reviews" / "latest.json").read_text(encoding="utf-8"))
        if not any(issue["code"] == "LOCAL_PATH_LEAK" for issue in review["issues"]):
            raise RuntimeError("正式内容泄漏门禁未触发")
        depth_probe.write_text(depth_original + "\n\n本节设计结论来自资料编号 R-001。\n", encoding="utf-8")
        run_failure([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment, "质量检查完成")
        review = json.loads((workspace / ".agent" / "reviews" / "latest.json").read_text(encoding="utf-8"))
        if not any(issue["code"] == "SOURCE_ID_EXPOSED" for issue in review["issues"]):
            raise RuntimeError("资料编号泄漏门禁未触发")
        depth_probe.write_text(depth_original + "\n\n本文档编写依赖参考文件参考概要设计样例.md。\n", encoding="utf-8")
        run_failure([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment, "质量检查完成")
        review = json.loads((workspace / ".agent" / "reviews" / "latest.json").read_text(encoding="utf-8"))
        if not any(issue["code"] == "REFERENCE_FILE_EXPOSED" for issue in review["issues"]):
            raise RuntimeError("参考材料载体泄漏门禁未触发")
        task_file = workspace / "00-任务说明" / "编写任务.md"
        task_original = task_file.read_text(encoding="utf-8")
        task_file.write_text(
            task_original.replace("本地资源依赖说明：不写入", "本地资源依赖说明：写入逻辑依赖"),
            encoding="utf-8",
        )
        run([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment)
        depth_probe.write_text(depth_original + "\n\n逻辑依赖位于 /Users/example/参考概要设计样例.md。\n", encoding="utf-8")
        run_failure([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment, "质量检查完成")
        review = json.loads((workspace / ".agent" / "reviews" / "latest.json").read_text(encoding="utf-8"))
        if not any(issue["code"] == "LOCAL_PATH_LEAK" for issue in review["issues"]):
            raise RuntimeError("逻辑依赖开关不应放开本机绝对路径")
        task_file.write_text(task_original, encoding="utf-8")
        depth_probe.write_text(depth_original, encoding="utf-8")
        run([*agent, "validate", "冒烟测试概要设计", "--mode", "final"], test_root, environment)
        publish_dir = test_root / "published"
        run(
            [*agent, "render", "冒烟测试概要设计", "--format", "all", "--publish-dir", str(publish_dir)],
            test_root,
            environment,
        )
        run([*agent, "preflight-word", "冒烟测试概要设计"], test_root, environment)
        external_source = test_root / "external-python-source"
        run_failure(
            [
                *agent,
                "render",
                "冒烟测试概要设计",
                "--format",
                "markdown",
                "--publish-dir",
                str(external_source / "generated"),
            ],
            test_root,
            environment,
            "成果目录不能位于只读源码目录中",
        )
        run([*agent, "qa", "冒烟测试概要设计"], test_root, environment)
        run([*agent, "qa", "冒烟测试概要设计", "--confirm-visual"], test_root, environment)

        formal_dir = workspace / "05-交付成果" / "02-正式版"
        expected = (
            formal_dir / "冒烟测试概要设计.md",
            formal_dir / "冒烟测试概要设计.docx",
            workspace / "03-过程成果" / "07-Word版式质检报告.md",
            workspace / "03-过程成果" / "08-分章预览" / "第03章-系统总体设计-预览.docx",
            workspace / "03-过程成果" / "09-Word编辑预检报告.md",
            workspace / "02-资料识别" / "参考样本蒸馏规范.md",
            publish_dir / "冒烟测试概要设计.md",
            publish_dir / "冒烟测试概要设计.docx",
        )
        missing = [path for path in expected if not path.exists() or path.stat().st_size == 0]
        if missing:
            raise RuntimeError("缺少冒烟测试产物：" + "、".join(str(path) for path in missing))


def main() -> int:
    smoke_test()
    print("概要设计 Agent 冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
