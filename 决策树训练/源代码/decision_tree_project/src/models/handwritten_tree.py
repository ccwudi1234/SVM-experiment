# -*- coding: utf-8 -*-
"""选做：自己编写决策树（ID3 / 简化 C4.5，多路分裂）。

与 scikit-learn 的 CART 实现不同，这里不调用任何现成的树模型，全部自己实现：
    - ID3 ：按"信息增益"选择划分特征
    - C4.5：按"信息增益率"选择划分特征（对取值多的特征做惩罚）

核心函数：
    entropy(y)                  信息熵 H(D)
    information_gain(x_col, y)  信息增益 g(D,A) = H(D) - H(D|A)
    gain_ratio(x_col, y)        信息增益率 g_R(D,A) = g(D,A) / H_A(D)
    build_tree(...)             递归建树（每个取值一个分支，多路分裂）
    predict_tree(...)           单样本预测
    train_and_evaluate(...)     训练 + 评估 + 规则导出
"""
# C4.5 仅实现直接最大化增益率；未包含增益候选筛选和剪枝，不等同于完整 C4.5。
import numpy as np

from ..config import CLASS_NAMES


class TreeNode:
    """决策树节点。

    内部节点：feature 记录按哪个特征划分，children 记录"取值 → 子节点"；
    叶节点：label 记录预测类别。
    majority 用于兜底：测试样本出现训练时没见过的取值时，返回该节点多数类。
    """

    __slots__ = ("feature", "children", "label", "majority")

    def __init__(self, feature=None, children=None, label=None, majority=None):
        self.feature = feature
        self.children = children if children is not None else {}
        self.label = label
        self.majority = majority


# ----------------------------------------------------------------------
# 1. 纯度度量与特征选择准则
# ----------------------------------------------------------------------
def entropy(y: np.ndarray) -> float:
    """信息熵：H(D) = -Σ p_k · log2(p_k)"""
    p = np.bincount(y).astype(float)
    p = p[p > 0] / len(y)
    return float(-(p * np.log2(p)).sum())


def information_gain(x_col: np.ndarray, y: np.ndarray) -> float:
    """信息增益：g(D,A) = H(D) - Σ (|D_v|/|D|)·H(D_v)"""
    base = entropy(y)
    total = len(y)
    conditional = 0.0
    for value in np.unique(x_col):
        mask = x_col == value
        conditional += mask.sum() / total * entropy(y[mask])
    return base - conditional


def gain_ratio(x_col: np.ndarray, y: np.ndarray) -> float:
    """信息增益率：g_R(D,A) = g(D,A) / H_A(D)"""
    gain = information_gain(x_col, y)
    counts = np.unique(x_col, return_counts=True)[1]
    p = counts / counts.sum()
    split_info = float(-(p * np.log2(p)).sum())
    return gain / (split_info + 1e-9) if split_info > 1e-9 else 0.0


def split_scores(X: np.ndarray, y: np.ndarray, feature_names, method: str = "id3"):
    """计算当前数据集上所有特征的分裂得分，用于分析"根节点为什么选这个特征"。"""
    scorer = information_gain if method == "id3" else gain_ratio
    pairs = [(feature_names[j], float(scorer(X[:, j], y))) for j in range(X.shape[1])]
    return sorted(pairs, key=lambda x: -x[1])


# ----------------------------------------------------------------------
# 2. 递归建树
# ----------------------------------------------------------------------
def build_tree(X: np.ndarray, y: np.ndarray, features: list[int],
               method: str = "id3", depth: int = 0,
               max_depth: int = 8) -> TreeNode:
    """递归建树。features 是当前节点还能使用的特征下标列表。"""
    majority = int(np.bincount(y).argmax())

    # 停止条件：样本纯了 / 没有特征可用 / 达到最大深度
    if len(np.unique(y)) == 1 or not features or depth >= max_depth:
        return TreeNode(label=majority, majority=majority)

    scorer = information_gain if method == "id3" else gain_ratio
    scores = [scorer(X[:, j], y) for j in features]
    best_pos = int(np.argmax(scores))
    best_j = features[best_pos]

    # 所有特征都分不开 → 生成叶节点
    if scores[best_pos] <= 1e-12:
        return TreeNode(label=majority, majority=majority)

    node = TreeNode(feature=best_j, majority=majority)
    remain = [j for j in features if j != best_j]
    for value in np.unique(X[:, best_j]):
        mask = X[:, best_j] == value
        node.children[value] = build_tree(
            X[mask], y[mask], remain, method, depth + 1, max_depth
        )
    return node


def predict_tree(node: TreeNode, x: np.ndarray) -> int:
    """沿树向下走到叶节点；遇到训练时没见过的取值，返回当前节点的多数类。"""
    while node.label is None:
        value = x[node.feature]
        if value in node.children:
            node = node.children[value]
        else:
            return node.majority
    return node.label


def predict(node: TreeNode, X: np.ndarray) -> np.ndarray:
    return np.array([predict_tree(node, x) for x in X])


def count_nodes(node: TreeNode) -> tuple[int, int]:
    """返回 (节点总数, 叶节点数)，用于和 sklearn 的树比较规模。"""
    if node.label is not None:
        return 1, 1
    total, leaves = 1, 0
    for child in node.children.values():
        n, leaf = count_nodes(child)
        total += n
        leaves += leaf
    return total, leaves


def tree_rules(node: TreeNode, feature_names, depth: int = 0,
               lines: list[str] | None = None) -> list[str]:
    """把树导出成文本规则，便于分析模型和写报告。"""
    if lines is None:
        lines = []
    indent = "    " * depth
    if node.label is not None:
        lines.append(f"{indent}└─ 预测：{CLASS_NAMES[node.label]}")
        return lines
    for value, child in node.children.items():
        lines.append(f"{indent}├─ {feature_names[node.feature]} = {value}")
        tree_rules(child, feature_names, depth + 1, lines)
    return lines


# ----------------------------------------------------------------------
# 3. 训练 + 评估
# ----------------------------------------------------------------------
def train_and_evaluate(method: str, X_train_raw: np.ndarray, y_train: np.ndarray,
                       X_test_raw: np.ndarray, y_test: np.ndarray,
                       feature_names, max_depth: int = 8):
    """训练并对测试集预测，返回模型、预测结果、规模与规则。"""
    tree = build_tree(X_train_raw, y_train, list(range(X_train_raw.shape[1])),
                      method, 0, max_depth)
    y_pred = predict(tree, X_test_raw)
    nodes, leaves = count_nodes(tree)
    scores = split_scores(X_train_raw, y_train, feature_names, method)[:5]
    return {
        "tree": tree,
        "y_pred": y_pred,
        "nodes": nodes,
        "leaves": leaves,
        "rules": tree_rules(tree, feature_names)[:20],
        "top_split_scores": scores,
    }
