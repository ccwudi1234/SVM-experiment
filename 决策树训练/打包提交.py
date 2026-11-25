# -*- coding: utf-8 -*-
"""
打包提交脚本（Python 版，避免 PowerShell 执行策略拦截）
=========================================================================
按实验要求生成：决策树-专业班级-学号-姓名.zip
压缩包内含三个部分：数据集 / python 源代码（整个项目）/ 实验报告

用法示例（在 D:\\个人资料库（学习）\\机器学习\\决策树训练 目录下运行）：
    python 打包提交.py --major-class 计算机2201 --student-id 20220001 --name 张三 ^
        --report 决策树实验报告.docx

参数：
    --major-class  专业班级，如：计算机2201
    --student-id   学号，如：20220001
    --name         姓名，如：张三
    --report       实验报告 Word 文件路径（如 实验报告/决策树实验报告.docx）
    --data-dir     数据集目录，默认 data
    --code-dir     项目源码目录，默认 decision_tree_project
    --out-dir      输出目录，默认 提交
    --force        已存在同名压缩包时覆盖
=========================================================================
"""
import argparse
import os
import sys
import zipfile
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
SKIP_PARTS = {"__pycache__", ".git", ".idea", ".vscode", ".workbuddy", ".claude", ".cursor", ".windsurf", ".codex", ".agents"}
SKIP_SUFFIX = {".pyc", ".pyo"}


def project_files(folder):
    for base, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_PARTS and not d.startswith('.')]
        for name in files:
            path = Path(base) / name
            if path.suffix not in SKIP_SUFFIX:
                yield path


def collect(data_dir: Path, code_dir: Path, report: Path) -> list[tuple[Path, str]]:
    """返回 [(源文件路径, 压缩包内路径), ...]"""
    items: list[tuple[Path, str]] = []

    # 1) 数据集：整个目录
    for p in sorted(project_files(data_dir)):
        if p.is_file():
            items.append((p, f"数据集/{p.relative_to(data_dir).as_posix()}"))

    # 2) 源代码：整个项目目录（含 README、requirements，跳过缓存文件）
    for p in sorted(project_files(code_dir)):
        if not p.is_file():
            continue
        if SKIP_PARTS & set(p.parts) or p.suffix in SKIP_SUFFIX:
            continue
        items.append((p, f"源代码/{code_dir.name}/{p.relative_to(code_dir).as_posix()}"))

    # 3) 保留复现说明中的报告目录结构
    items.append((report, f"实验报告/{report.name}"))
    root = code_dir.parent.parent
    for name in ("build_report.py", "polish_report.py", "omml.py", "refine_experiments.py", "check_100_percent.py", "render_word_local.py"):
        path = root / "工具" / name
        if not path.is_file():
            raise FileNotFoundError(f"缺少复现脚本：{path}")
        items.append((path, f"工具/{name}"))
    for folder in ("图表", "模板与要求"):
        for path in sorted(project_files(root / folder)):
            items.append((path, f"{folder}/{path.relative_to(root / folder).as_posix()}"))
    for name in ("AGENTS.md", "复现说明.md", "requirements-report.txt", "打包提交.py"):
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"缺少复现说明：{path}")
        items.append((path, name))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="生成决策树实验提交压缩包")
    ap.add_argument("--major-class", required=True, help="专业班级，如 计算机2201")
    ap.add_argument("--student-id", required=True, help="学号")
    ap.add_argument("--name", required=True, help="姓名")
    ap.add_argument("--report", required=True, help="实验报告 .docx 路径")
    ap.add_argument("--data-dir", default="数据集", help="数据集目录（默认 数据集）")
    ap.add_argument("--code-dir", default="源代码/decision_tree_project", help="项目源码目录")
    ap.add_argument("--out-dir", default="提交", help="输出目录（默认 提交）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的压缩包")
    args = ap.parse_args()

    root = Path.cwd()
    data_dir = root / args.data_dir
    code_dir = root / args.code_dir
    report = Path(args.report)
    if not report.is_absolute():
        report = root / report
    out_dir = root / args.out_dir

    # ---- 基本校验 ----
    if not report.is_file():
        print(f"[错误] 找不到实验报告：{report}")
        return 1
    if report.suffix.lower() not in {".docx", ".doc"}:
        print("[错误] 实验报告必须是 Word 文档（.docx / .doc）")
        return 1
    if not data_dir.is_dir() or not any(project_files(data_dir)):
        print(f"[错误] 数据集目录不存在或为空：{data_dir}")
        return 1
    if not code_dir.is_dir() or not (code_dir / "main.py").is_file():
        print(f"[错误] 项目源码目录不存在或缺少 main.py：{code_dir}")
        return 1

    base = f"决策树-{args.major_class}-{args.student_id}-{args.name}"
    zip_path = out_dir / f"{base}.zip"
    if zip_path.exists() and not args.force:
        print(f"[错误] 已存在 {zip_path}，确认覆盖请加 --force")
        return 1

    items = collect(data_dir, code_dir, report)

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_zip = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in items:
            zf.write(src, arc)
    tmp_zip.replace(zip_path)

    # ---- 结果 ----
    size = zip_path.stat().st_size
    size_mb = size / 1024 / 1024
    print("\n====== 打包结果 ======")
    print(f"压缩包：{zip_path}")
    print(f"大小：{size_mb:.2f} MB（上限 20 MB）")
    print(f"文件数：{len(items)}")
    print("内容：")
    for src, arc in items:
        print(f"  - {arc}  ({src.stat().st_size / 1024:.1f} KB)")

    if size > MAX_BYTES:
        print("\n[警告] 压缩包超过 20 MB，请压缩数据集或去掉无关文件后再提交！")
        return 1
    print("\n[OK] 压缩包小于 20 MB，符合提交要求。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
