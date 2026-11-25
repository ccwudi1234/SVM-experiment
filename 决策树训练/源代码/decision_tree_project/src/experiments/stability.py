# -*- coding: utf-8 -*-
"""实验三：树结构稳定性分析。

同一份数据、同一套参数，只改变"随机划分/重采样"，观察：
  1. 单棵决策树的结构（叶节点数、深度）会不会变？
  2. 根节点选的特征是否始终一样？
  3. 特征重要性排序是否稳定？随机森林是否比单棵树更稳定？
衡量方式：30 次不同的随机划分，记录树结构；用 Jaccard 相似度比较两次结果
"重要性前 3 的特征集合"的重合程度，并统计每个特征重要性的标准差。
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from ..config import RANDOM_STATE
from ..data_loader import encode_for_sklearn
from .. import visualization


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b)


def run(X, y, feature_names, output_dir, seeds=30):
    leaves, depths, root_counts = [], [], {}
    importances, rf_importances = [], []
    top3_sets, rf_top3_sets = [], []

    for s in range(seeds):
        X_tr, X_te, y_tr, _ = train_test_split(
            X, y, test_size=0.3, random_state=s, stratify=y)
        X_tr, _, _ = encode_for_sklearn(X_tr, X_te)
        tree = DecisionTreeClassifier(random_state=RANDOM_STATE).fit(X_tr, y_tr)
        leaves.append(int(tree.get_n_leaves()))
        depths.append(int(tree.get_depth()))
        root = feature_names[tree.tree_.feature[0]]
        root_counts[root] = root_counts.get(root, 0) + 1
        imp = tree.feature_importances_
        importances.append(imp)
        top3_sets.append(set(np.argsort(imp)[::-1][:3].tolist()))

        rf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE).fit(X_tr, y_tr)
        rf_imp = rf.feature_importances_
        rf_importances.append(rf_imp)
        rf_top3_sets.append(set(np.argsort(rf_imp)[::-1][:3].tolist()))

    def mean_jaccard(sets):
        values = [_jaccard(sets[i], sets[j])
                  for i in range(len(sets)) for j in range(i + 1, len(sets))]
        return float(np.mean(values)), float(np.median(values))

    jac_mean, jac_median = mean_jaccard(top3_sets)
    rf_jac_mean, rf_jac_median = mean_jaccard(rf_top3_sets)

    imp_arr = np.array(importances)
    rf_imp_arr = np.array(rf_importances)
    top_features = [int(i) for i in np.argsort(imp_arr.mean(axis=0))[::-1][:6]]
    root_top = max(root_counts, key=root_counts.get)

    result = {
        "seeds": seeds,
        "leaves": leaves,
        "depths": depths,
        "leaves_mean": float(np.mean(leaves)),
        "leaves_std": float(np.std(leaves)),
        "leaves_min": int(np.min(leaves)),
        "leaves_max": int(np.max(leaves)),
        "depth_mode": int(np.bincount(depths).argmax()),
        "depth_min": int(np.min(depths)),
        "depth_max": int(np.max(depths)),
        "root_counts": root_counts,
        "root_top": root_top,
        "root_top_ratio": root_counts[root_top] / seeds,
        "top3_jaccard_tree": jac_mean,
        "top3_jaccard_tree_median": jac_median,
        "top3_jaccard_rf": rf_jac_mean,
        "top3_jaccard_rf_median": rf_jac_median,
        "importance_std_tree": float(imp_arr.std(axis=0).mean()),
        "importance_std_rf": float(rf_imp_arr.std(axis=0).mean()),
        "top_features": top_features,
        "top_feature_names": [feature_names[i] for i in top_features],
        "top_importance_std_tree": imp_arr.std(axis=0)[top_features].tolist(),
        "top_importance_std_rf": rf_imp_arr.std(axis=0)[top_features].tolist(),
    }

    path = output_dir / "stability.png"
    visualization.plot_stability(result, feature_names, path)
    result["figure"] = str(path)
    return result
