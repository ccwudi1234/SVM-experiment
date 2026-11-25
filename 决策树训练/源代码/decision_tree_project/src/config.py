# -*- coding: utf-8 -*-
"""项目全局配置：路径、数据列名、随机种子等。

数据路径会按以下顺序自动查找，随便放在哪个布局下都能跑：
  1. <工作区>/数据集/mushroom/agaricus-lepiota.data
  2. <工作目录>/data/mushroom/agaricus-lepiota.data
  3. <提交包根目录>/数据集/mushroom/agaricus-lepiota.data
  4. <提交包根目录>/data/mushroom/agaricus-lepiota.data
也可以用命令行参数 --data 显式指定。
"""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent       # decision_tree_project/
OUTPUTS_DIR = PROJECT_DIR.parent.parent / "图表"            # 图表与结果输出目录（工作区根目录下的 图表/）

DATA_FILENAME = "agaricus-lepiota.data"
DATA_CANDIDATES = [
    PROJECT_DIR / "data" / "mushroom" / DATA_FILENAME,
    PROJECT_DIR.parent / "data" / "mushroom" / DATA_FILENAME,
    PROJECT_DIR.parent.parent / "数据集" / "mushroom" / DATA_FILENAME,
    PROJECT_DIR.parent.parent / "data" / "mushroom" / DATA_FILENAME,
]

RANDOM_STATE = 42
TEST_SIZE = 0.3

# UCI 原始文件没有表头，按官方文档补上 23 个列名
COLUMNS = [
    "class", "cap-shape", "cap-surface", "cap-color", "bruises", "odor",
    "gill-attachment", "gill-spacing", "gill-size", "gill-color",
    "stalk-shape", "stalk-root", "stalk-surface-above-ring",
    "stalk-surface-below-ring", "stalk-color-above-ring",
    "stalk-color-below-ring", "veil-type", "veil-color", "ring-number",
    "ring-type", "spore-print-color", "population", "habitat",
]
FEATURES = COLUMNS[1:]

CLASS_NAMES = ["可食", "有毒"]
MISSING_TOKEN = "missing"      # 原始数据用 ? 表示缺失，这里作为独立类别

# 两种特征选择策略：scikit-learn 用 criterion 参数区分
STRATEGIES = [
    ("gini", "CART · 基尼指数"),
    ("entropy", "ID3 思路 · 信息熵/信息增益"),
]


def resolve_data_path(cli_path: str | None = None) -> Path:
    """定位数据文件；找不到就抛出清晰的错误提示。"""
    if cli_path:
        p = Path(cli_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"指定的数据文件不存在：{p}")
    for p in DATA_CANDIDATES:
        if p.is_file():
            return p
    tried = "\n  ".join(str(p) for p in DATA_CANDIDATES)
    raise FileNotFoundError(
        "找不到数据集 agaricus-lepiota.data，已尝试：\n  " + tried +
        "\n请用 --data 指定数据文件路径，或把数据放到 <项目>/data/mushroom/ 下。"
    )
