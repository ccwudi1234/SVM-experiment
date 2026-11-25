# -*- coding: utf-8 -*-
"""可视化模块：所有图都在这里画，主流程只负责调用。

产出图（保存到 outputs/）：
    tree_gini.png            基尼指数决策树
    tree_entropy.png         信息熵决策树
    confusion_matrices.png   两种策略的混淆矩阵
    feature_importance.png   决策树 vs 随机森林特征重要性
    rf_single_tree.png       随机森林中的一棵树
    rf_oob_curve.png         OOB 准确率随树数量的变化
    depth_curve.png          树深-准确率（过拟合分析）
    pruning.png              后剪枝强度-准确率
"""
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from sklearn.tree import plot_tree


def setup_chinese_font() -> None:
    """让 matplotlib 能显示中文（Windows 自带微软雅黑/黑体）。"""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in ["Microsoft YaHei", "SimHei", "SimSun"]:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _save(fig, path: Path, dpi: int = 150) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def _relabel_conditions(annotations, feature_names, category_map) -> None:
    """把图上的 "gill-color <= 3.50" 换算回原始类别，如 "gill-color ∈ {b,e,g,h}"。

    scikit-learn 的决策树只接受数值输入，所以类别特征先用 OrdinalEncoder 编码成
    0,1,2,...；树的分裂阈值是这些编码值。这里按"编码值 → 原始取值"的顺序把
    阈值还原成类别集合，让图可以直接看懂。
    """
    for ann in annotations:
        text = ann.get_text()
        if " <= " not in text:
            continue
        first_line, _, rest = text.partition("\n")
        feature, _, threshold = first_line.partition(" <= ")
        feature = feature.strip()
        if feature not in feature_names:
            continue
        categories = category_map.get(feature)
        if not categories:
            continue
        try:
            cut = int(float(threshold))
        except ValueError:
            continue
        left, right = categories[:cut + 1], categories[cut + 1:]
        if len(left) > 5:            # 集合太长就不换算，保留数字阈值
            continue
        # 统一展示"属于左分支（True）的类别集合"，与图上的"是/否"箭头对应
        ann.set_text(f"{feature} ∈ {{{','.join(left)}}}\n{rest}")
    for ann in annotations:
        text = ann.get_text().strip()
        if text == "True":
            ann.set_text("是")
        elif text == "False":
            ann.set_text("否")


def plot_decision_tree(model, feature_names, class_names, path: Path,
                       title: str, max_depth: int = 2,
                       category_map: dict | None = None) -> None:
    """画一棵决策树（默认只显示前 2 层，保证图中文字清晰）。

    category_map 传入 {特征名: [原始取值, ...]} 时，节点条件会换算成原始类别，
    例如 "gill-color <= 3.50" 显示为 "gill-color ∈ {b,e,g,h}"。
    """
    fig = plt.figure(figsize=(7, 4.2))
    annotations = plot_tree(model, feature_names=feature_names, class_names=class_names,
                            filled=True, rounded=True, fontsize=11, max_depth=max_depth)
    if category_map:
        _relabel_conditions(annotations, feature_names, category_map)
    plt.title(title, fontsize=13)
    _save(fig, path)


def plot_full_tree(model, feature_names, class_names, path: Path, title: str,
                   category_map: dict | None = None) -> None:
    """把决策树完整画出来（不截断深度）。

    完整树节点很多，所以用很大的画布 + 高分辨率，保证放大后每个节点的
    划分条件、样本数和类别都能看清。
    """
    n_leaves = model.get_n_leaves()
    depth = model.get_depth()
    # 每个叶节点预留约 1.9 英寸，避免最深层的节点框互相重叠
    width = max(20.0, 1.9 * n_leaves)
    height = max(9.0, 2.3 * depth)
    fig = plt.figure(figsize=(width, height))
    annotations = plot_tree(model, feature_names=feature_names, class_names=class_names,
                            filled=True, rounded=True, fontsize=9)
    if category_map:
        _relabel_conditions(annotations, feature_names, category_map)
    plt.title(f"{title}（深度 {depth}，叶节点 {n_leaves} 个）", fontsize=16)
    _save(fig, path, dpi=150)


def plot_confusion_matrices(y_true, preds: dict, titles: dict, path: Path) -> None:
    """并排画多个混淆矩阵。"""
    n = len(preds)
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 4.5))
    if n == 1:
        axes = [axes]
    for ax, (key, y_pred) in zip(axes, preds.items()):
        cm = np.array(__import__("sklearn").metrics.confusion_matrix(y_true, y_pred))
        im = ax.imshow(cm, cmap="Blues")
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=13,
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        ax.set_xticks(range(cm.shape[0]))
        ax.set_yticks(range(cm.shape[0]))
        ax.set_xticklabels(["可食", "有毒"])
        ax.set_yticklabels(["可食", "有毒"])
        ax.set_xlabel("预测类别")
        ax.set_ylabel("真实类别")
        ax.set_title(titles[key], fontsize=11)
        fig.colorbar(im, ax=ax, fraction=0.046)
    _save(fig, path)


def plot_feature_importance(importances: dict, feature_names, top_k: int,
                            path: Path) -> None:
    """把多个模型（两棵决策树 + 随机森林）的特征重要性画成分组柱状图。"""
    order = np.argsort(list(importances.values())[-1])[::-1][:top_k]
    x = np.arange(len(order))
    width = 0.8 / len(importances)
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (label, values) in enumerate(importances.items()):
        offset = (i - (len(importances) - 1) / 2) * width
        ax.bar(x + offset, values[order], width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels([feature_names[i] for i in order], rotation=30, ha="right")
    ax.set_ylabel("特征重要性")
    ax.set_title("特征重要性对比（随机森林 vs 单棵决策树）")
    ax.legend()
    _save(fig, path)


def plot_forest_tree(model, feature_names, class_names, path: Path,
                     category_map: dict | None = None) -> None:
    """画随机森林中的一棵树（只看第一层，括号表示未展开的子树）。"""
    fig = plt.figure(figsize=(6.5, 4.2))
    annotations = plot_tree(model, feature_names=feature_names, class_names=class_names,
                            filled=True, rounded=True, fontsize=12, max_depth=1)
    if category_map:
        _relabel_conditions(annotations, feature_names, category_map)
    plt.title("随机森林中的一棵决策树（前 1 层）", fontsize=13)
    _save(fig, path)


def plot_oob_curve(curve: list, path: Path) -> None:
    """OOB 准确率随树数量变化。"""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ks = [k for k, _ in curve]
    scores = [v for _, v in curve]
    ax.plot(ks, scores, "o-")
    ax.set_xlabel("树的棵数 n_estimators")
    ax.set_ylabel("OOB 准确率")
    ax.set_title("随机森林 OOB 准确率随树数量变化")
    ax.grid(alpha=0.3)
    _save(fig, path)


def plot_depth_curve(rows: list, path: Path) -> None:
    """树深-准确率曲线（预剪枝/过拟合分析）。"""
    depths = [r[0] for r in rows]
    train = [r[1] for r in rows]
    test = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(depths, train, "o-", label="训练准确率")
    ax.plot(depths, test, "s-", label="验证准确率")
    ax.set_xlabel("max_depth（预剪枝：限制树深）")
    ax.set_ylabel("准确率")
    ax.set_title("树深与准确率：深度-过拟合曲线")
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, path)


def plot_pruning(rows: list, path: Path) -> None:
    """后剪枝 ccp_alpha 与准确率的关系。"""
    alphas = [r[0] for r in rows]
    train = [r[2] for r in rows]
    test = [r[3] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(alphas, train, "o-", label="训练准确率")
    ax.plot(alphas, test, "s-", label="验证准确率")
    ax.set_xscale("symlog", linthresh=0.001)
    ax.set_xlabel("ccp_alpha（后剪枝强度）")
    ax.set_ylabel("准确率")
    ax.set_title("后剪枝 ccp_alpha 与准确率")
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, path)

# ----------------------------------------------------------------------
# 扩展实验的图：难度梯度、代价敏感、结构稳定性、划分比例
# ----------------------------------------------------------------------
def plot_difficulty(learning_curve, feature_subset, noise, path: Path) -> None:
    """难度梯度：学习曲线 / 特征子集 / 标签噪声，三联图。"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))

    ax = axes[0]
    fracs = [r[0] * 100 for r in learning_curve]
    ax.errorbar(fracs, [r[1] for r in learning_curve], yerr=[r[2] for r in learning_curve],
                marker="o", label="训练准确率", capsize=3)
    ax.errorbar(fracs, [r[3] for r in learning_curve], yerr=[r[4] for r in learning_curve],
                marker="s", label="测试准确率", capsize=3)
    ax.set_xlabel("训练集使用比例（%）")
    ax.set_ylabel("准确率")
    ax.set_title("学习曲线：训练集大小的影响")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ks = [r[0] for r in feature_subset]
    accs = [r[1] for r in feature_subset]
    ax.plot(ks, accs, "^-", color="tab:green")
    full_k = next((r[0] for r in feature_subset if r[1] >= 0.9999), None)
    if full_k:
        ax.axvline(full_k, color="tab:red", linestyle="--", alpha=0.7)
        ax.annotate(f"{full_k} 个特征即达 100%", xy=(full_k, 0.9),
                    xytext=(full_k + 1.0, 0.75), fontsize=9, color="tab:red")
    ax.set_xlabel("保留重要性前 k 个特征")
    ax.set_ylabel("测试准确率")
    ax.set_title("特征子集：需要几个特征")
    ax.grid(alpha=0.3)

    ax = axes[2]
    ratios = [r[0] * 100 for r in noise]
    ax.errorbar(ratios, [r[1] for r in noise], yerr=[r[2] for r in noise],
                marker="o", color="tab:orange", capsize=3)
    ax.set_xlabel("训练集标签噪声比例（%）")
    ax.set_ylabel("测试准确率")
    ax.set_title("标签噪声：模型是否被带偏")
    ax.grid(alpha=0.3)

    _save(fig, path)


def plot_cost_sensitive(curve, best: dict, path: Path) -> None:
    """代价敏感：阈值-总代价曲线 + 阈值-精确率/召回率曲线。"""
    thresholds = [r[0] for r in curve]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    ax = axes[0]
    for ratio, color in zip(sorted(best), ["tab:blue", "tab:orange", "tab:red"]):
        costs = [ratio * r[3] + r[2] for r in curve]
        ax.plot(thresholds, costs, color=color, label=f"漏判代价:误判代价 = {ratio}:1")
        ax.axvline(best[ratio]["threshold"], color=color, linestyle="--", alpha=0.6)
        ax.plot(best[ratio]["threshold"], best[ratio]["cost"], "o", color=color)
    ax.set_xlabel("分类阈值（有毒概率 ≥ 阈值判为有毒）")
    ax.set_ylabel("验证集总代价")
    ax.set_title("阈值与总代价（虚线为最小代价阈值）")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(thresholds, [r[5] for r in curve], label="精确率", color="tab:purple")
    ax.plot(thresholds, [r[6] for r in curve], label="召回率（有毒类）", color="tab:green")
    ax.set_xlabel("分类阈值")
    ax.set_ylabel("指标值")
    ax.set_title("阈值与精确率 / 召回率")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    _save(fig, path)


def plot_stability(result: dict, feature_names, path: Path) -> None:
    """结构稳定性：根节点特征频数 / 叶节点数分布 / 特征重要性标准差对比。"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

    ax = axes[0]
    roots = result["root_counts"]
    names = list(roots)
    counts = [roots[n] for n in names]
    ax.bar(range(len(names)), counts, color="tab:blue")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel(f"次数（共 {result['seeds']} 次划分）")
    ax.set_title("根节点选择什么特征")
    ax.grid(alpha=0.3, axis="y")

    ax = axes[1]
    ax.boxplot(result["leaves"], widths=0.4)
    ax.scatter([1] * len(result["leaves"]), result["leaves"], alpha=0.5, s=18, color="tab:blue")
    ax.set_xticks([1])
    ax.set_xticklabels(["叶节点数"])
    ax.set_ylabel("叶节点数")
    ax.set_title(f"树规模分布（{result['leaves_min']}~{result['leaves_max']}）")
    ax.grid(alpha=0.3, axis="y")

    ax = axes[2]
    x = range(len(result["top_features"]))
    width = 0.38
    ax.bar([i - width / 2 for i in x], result["top_importance_std_tree"], width,
           label="单棵决策树")
    ax.bar([i + width / 2 for i in x], result["top_importance_std_rf"], width,
           label="随机森林")
    ax.set_xticks(list(x))
    ax.set_xticklabels(result["top_feature_names"], rotation=30, ha="right")
    ax.set_ylabel("特征重要性的标准差")
    ax.set_title("重要性稳定性：单树 vs 随机森林")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, axis="y")

    _save(fig, path)


def plot_split_ratio(rows: list, path: Path) -> None:
    """不同训练/测试划分比例下的准确率（百分比坐标，含 9:1；标出本实验采用的 7:3）。"""
    test_sizes = [r[0] * 100 for r in rows]
    tree_train = [r[3] * 100 for r in rows]
    tree_test = [r[4] * 100 for r in rows]
    tree_std = [r[5] * 100 for r in rows]
    rf_test = [r[6] * 100 for r in rows]
    rf_std = [r[7] * 100 for r in rows]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.errorbar(test_sizes, tree_train, marker="o", label="决策树·训练准确率")
    ax.errorbar(test_sizes, tree_test, yerr=tree_std, marker="s",
                label="决策树·测试准确率", capsize=3)
    ax.errorbar(test_sizes, rf_test, yerr=rf_std, marker="^",
                label="随机森林·测试准确率", capsize=3)
    ax.axvline(30, color="tab:red", linestyle="--", alpha=0.6, label="本实验采用 7:3")
    lowest = min(tree_test + rf_test)
    ax.set_ylim(lowest - 0.15, 100.05)
    ax.set_xlabel("测试集比例（%）")
    ax.set_ylabel("准确率（%）")
    ax.set_title("训练/测试划分比例对准确率的影响")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    _save(fig, path)
