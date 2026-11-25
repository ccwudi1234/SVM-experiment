# -*- coding: utf-8 -*-
"""
决策树实验 · 主程序
==========================================================================
课程实验：决策树（ID3 / C4.5 / CART）+ 随机森林
数据集：UCI Mushroom，8124 条样本、22 个类别特征、二分类（可食 / 有毒）

本程序负责把各模块串起来，依次完成：
    1. 读取数据、查看概况                     （data_loader）
    2. 训练两棵决策树：基尼指数 / 信息熵        （models.decision_tree）
    3. 训练随机森林并画图                     （models.random_forest）
    4. 过拟合分析与剪枝实验                    （models.decision_tree）
    5. 选做：自己编写的 ID3 / C4.5 决策树       （models.handwritten_tree）
    6. 统一评估指标                           （metrics）
    7. 所有图表输出到 outputs/                （visualization）

运行方式（在项目根目录执行）：
    python 源代码/decision_tree_project/main.py
    python 源代码/decision_tree_project/main.py --data 数据集/mushroom/agaricus-lepiota.data

输出（工作区根目录 图表/）：
    tree_gini.png、tree_entropy.png、confusion_matrices.png、feature_importance.png、
    rf_single_tree.png、rf_oob_curve.png、depth_curve.png、pruning.png、
    results.json、tree_rules_*.txt、handwritten_rules.txt
==========================================================================
"""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import numpy as np
from sklearn.model_selection import cross_val_score, train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import export_text

from src import data_loader, experiments, metrics, visualization
from src.config import (
    CLASS_NAMES,
    FEATURES,
    OUTPUTS_DIR,
    RANDOM_STATE,
    STRATEGIES,
    resolve_data_path,
)
from src.models import decision_tree, handwritten_tree, random_forest


def section(title: str) -> None:
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


def main(data_arg: str | None = None) -> dict:
    data_path = resolve_data_path(data_arg)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    visualization.setup_chinese_font()
    results = {"figures": {}, "tables": {}, "notes": {"data_path": str(data_path)}}

    # ------------------------------------------------------------------
    # 1. 数据
    # ------------------------------------------------------------------
    section("1. 数据概况")
    df = data_loader.load_raw(data_path)
    info = data_loader.describe(df)
    print(f"样本数 {info['rows']}，特征数 {info['features']}，类别分布 {info['class_counts']}")
    print(f"缺失值：{info['missing']}")
    results["tables"]["data_summary"] = info

    X, y = data_loader.prepare(df)
    X_train_raw, X_test_raw, y_train, y_test = data_loader.split(X, y)
    print(f"训练集 {len(X_train_raw)} 条，测试集 {len(X_test_raw)} 条")
    X_train, X_test, encoder = data_loader.encode_for_sklearn(X_train_raw, X_test_raw)
    # 编码值 → 原始类别取值的映射，用于把图上的数字阈值还原成类别（如 gill-color ∈ {b,e,g,h}）
    category_map = {f: list(cats) for f, cats in zip(FEATURES, encoder.categories_)}

    # ------------------------------------------------------------------
    # 2. 两种特征选择策略的决策树
    # ------------------------------------------------------------------
    section("2. 决策树的两种特征选择策略")
    trees, preds, names = {}, {}, {}
    for criterion, name in STRATEGIES:
        model = decision_tree.train(X_train, y_train, criterion)
        pred_train = model.predict(X_train)
        pred_test = model.predict(X_test)
        cv = cross_val_score(
            Pipeline([("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
                      ("tree", decision_tree.train(X_train, y_train, criterion))]),
            X_train_raw, y_train,
            cv=StratifiedKFold(5, shuffle=True, random_state=RANDOM_STATE))
        m = metrics.metric_row(y_test, pred_test)

        trees[criterion], preds[criterion] = model, pred_test
        names[criterion] = name
        results["tables"][f"tree_{criterion}"] = {
            "name": name,
            "metrics": m,
            "train_accuracy": float(metrics.metric_row(y_train, pred_train)["accuracy"]),
            "cv_mean": float(cv.mean()),
            "cv_std": float(cv.std()),
            "depth": int(model.get_depth()),
            "leaves": int(model.get_n_leaves()),
            "first_split_feature": FEATURES[model.tree_.feature[0]],
            "cm": metrics.confusion(y_test, pred_test),
        }
        print(f"\n[{name}]  criterion='{criterion}'")
        print(f"  训练准确率 {results['tables'][f'tree_{criterion}']['train_accuracy']:.4f}，"
              f"测试准确率 {m['accuracy']:.4f}，5 折 CV {cv.mean():.4f} ± {cv.std():.4f}")
        print(f"  精确率(macro) {m['precision_macro']:.4f}，"
              f"召回率(macro) {m['recall_macro']:.4f}，F1(macro) {m['f1_macro']:.4f}")
        print(f"  树深 {model.get_depth()}，叶节点 {model.get_n_leaves()}，"
              f"根节点分裂特征：{FEATURES[model.tree_.feature[0]]}")
        print(f"  混淆矩阵 {results['tables'][f'tree_{criterion}']['cm']}")

    # 完整树的规则文本（报告附件里可以逐条查看）
    for criterion, name in STRATEGIES:
        rules = export_text(trees[criterion], feature_names=FEATURES)
        (OUTPUTS_DIR / f"tree_rules_{criterion}.txt").write_text(rules, encoding="utf-8")

    # 可视化：两棵树 + 混淆矩阵
    for criterion, name in STRATEGIES:
        shallow = decision_tree.train_shallow(X_train, y_train, criterion, max_depth=2)
        visualization.plot_decision_tree(
            shallow, FEATURES, CLASS_NAMES,
            OUTPUTS_DIR / f"tree_{criterion}.png",
            f"决策树（{name}，max_depth=2）",
            category_map=category_map,
        )
        results["figures"][f"tree_{criterion}"] = str(OUTPUTS_DIR / f"tree_{criterion}.png")

    # 完整决策树（不截断，高清大图，可放大查看每个节点）
    for criterion, name in STRATEGIES:
        visualization.plot_full_tree(
            trees[criterion], FEATURES, CLASS_NAMES,
            OUTPUTS_DIR / f"full_tree_{criterion}.png",
            f"完整决策树（{name}）",
            category_map=category_map,
        )
        results["figures"][f"full_tree_{criterion}"] = str(
            OUTPUTS_DIR / f"full_tree_{criterion}.png")


    # ------------------------------------------------------------------
    # 3. 随机森林
    # ------------------------------------------------------------------
    section("3. 随机森林")
    rf = random_forest.train(X_train, y_train, n_estimators=100)
    pred_rf = rf.predict(X_test)
    rf_m = metrics.metric_row(y_test, pred_rf)
    visualization.plot_confusion_matrices(
        y_test,
        {**preds, "random_forest": pred_rf},
        {"gini": "基尼指数", "entropy": "信息熵", "random_forest": "随机森林"},
        OUTPUTS_DIR / "confusion_matrices.png",
    )
    results["figures"]["confusion_matrices"] = str(OUTPUTS_DIR / "confusion_matrices.png")
    top_features = random_forest.feature_importance(rf, FEATURES)[:10]
    results["tables"]["random_forest"] = {
        "metrics": rf_m,
        "n_estimators": 100,
        "oob_score": float(rf.oob_score_),
        "cm": metrics.confusion(y_test, pred_rf),
        "top_features": [{"feature": f, "importance": v} for f, v in top_features],
    }
    print(f"  测试准确率 {rf_m['accuracy']:.4f}，OOB 准确率 {rf.oob_score_:.4f}")
    print(f"  精确率(macro) {rf_m['precision_macro']:.4f}，"
          f"召回率(macro) {rf_m['recall_macro']:.4f}，F1(macro) {rf_m['f1_macro']:.4f}")
    print("  特征重要性前 5：" +
          "，".join(f"{f}={v:.3f}" for f, v in top_features[:5]))

    visualization.plot_feature_importance(
        {
            "决策树·基尼": trees["gini"].feature_importances_,
            "决策树·信息熵": trees["entropy"].feature_importances_,
            "随机森林": rf.feature_importances_,
        },
        FEATURES, top_k=10, path=OUTPUTS_DIR / "feature_importance.png",
    )
    results["figures"]["feature_importance"] = str(OUTPUTS_DIR / "feature_importance.png")

    visualization.plot_forest_tree(
        rf.estimators_[0], FEATURES, CLASS_NAMES,
        OUTPUTS_DIR / "rf_single_tree.png",
        category_map=category_map,
    )
    results["figures"]["rf_single_tree"] = str(OUTPUTS_DIR / "rf_single_tree.png")

    oob = random_forest.oob_curve(X_train, y_train)
    results["tables"]["rf_oob_curve"] = oob
    visualization.plot_oob_curve(oob, OUTPUTS_DIR / "rf_oob_curve.png")
    results["figures"]["rf_oob_curve"] = str(OUTPUTS_DIR / "rf_oob_curve.png")

    # ------------------------------------------------------------------
    # 4. 过拟合分析与剪枝
    # ------------------------------------------------------------------
    section("4. 过拟合分析与剪枝")
    X_fit_raw, X_val_raw, y_fit, y_val = train_test_split(
        X_train_raw, y_train, test_size=0.25, stratify=y_train, random_state=RANDOM_STATE)
    X_fit, X_val, _ = data_loader.encode_for_sklearn(X_fit_raw, X_val_raw)
    depth_rows = []
    for depth in range(1, 16):
        model = decision_tree.train_with_depth(X_fit, y_fit, depth)
        depth_rows.append((
            depth,
            float(metrics.metric_row(y_fit, model.predict(X_fit))["accuracy"]),
            float(metrics.metric_row(y_val, model.predict(X_val))["accuracy"]),
        ))
    results["tables"]["depth_curve"] = depth_rows
    visualization.plot_depth_curve(depth_rows, OUTPUTS_DIR / "depth_curve.png")
    results["figures"]["depth_curve"] = str(OUTPUTS_DIR / "depth_curve.png")
    print("  深度-准确率：")
    for depth, train_acc, test_acc in depth_rows:
        print(f"    depth={depth:<3} 训练={train_acc:.4f} 验证={test_acc:.4f}")

    pruning_rows = []
    for alpha in [0.0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]:
        model = decision_tree.train_with_alpha(X_fit, y_fit, alpha)
        pruning_rows.append((
            alpha,
            int(model.get_n_leaves()),
            float(metrics.metric_row(y_fit, model.predict(X_fit))["accuracy"]),
            float(metrics.metric_row(y_val, model.predict(X_val))["accuracy"]),
        ))
    results["tables"]["pruning"] = pruning_rows
    visualization.plot_pruning(pruning_rows, OUTPUTS_DIR / "pruning.png")
    results["figures"]["pruning"] = str(OUTPUTS_DIR / "pruning.png")
    print("  后剪枝 ccp_alpha：")
    for alpha, leaves, train_acc, test_acc in pruning_rows:
        print(f"    alpha={alpha:<6} 叶节点={leaves:<4} 训练={train_acc:.4f} 验证={test_acc:.4f}")

    # ------------------------------------------------------------------
    # 5. 选做：自己编写的 ID3 / C4.5 决策树
    # ------------------------------------------------------------------
    section("5. 选做：自己编写的 ID3 / C4.5 决策树")
    hand_results = {}
    for method, name in [("id3", "手写ID3(信息增益)"), ("c4.5", "手写C4.5(信息增益率)")]:
        out = handwritten_tree.train_and_evaluate(
            method, np.asarray(X_train_raw), y_train,
            np.asarray(X_test_raw), y_test, FEATURES,
        )
        m = metrics.metric_row(y_test, out["y_pred"])
        hand_results[name] = {
            "metrics": m,
            "nodes": out["nodes"],
            "leaves": out["leaves"],
            "rules_head": out["rules"],
            "top_split_scores": out["top_split_scores"],
        }
        criterion_name = "信息增益" if method == "id3" else "信息增益率"
        root_feature, root_score = out["top_split_scores"][0]
        print(f"  {name}: 准确率={m['accuracy']:.4f} 节点数={out['nodes']} "
              f"叶节点={out['leaves']}")
        print(f"    根节点选择：{root_feature}（{criterion_name} {root_score:.4f}）")
    results["tables"]["handwritten"] = hand_results
    (OUTPUTS_DIR / "handwritten_rules.txt").write_text(
        "\n".join(hand_results["手写ID3(信息增益)"]["rules_head"]), encoding="utf-8"
    )

    # ------------------------------------------------------------------
    # 6. 扩展实验：划分比例、难度梯度、代价敏感、结构稳定性
    # ------------------------------------------------------------------
    section("6. 扩展实验：划分比例、难度梯度、代价敏感、结构稳定性")
    ext = experiments.run_all(X, y, FEATURES, OUTPUTS_DIR)
    results["tables"]["extensions"] = ext
    for key in ("split_ratio", "difficulty", "cost_sensitive", "stability"):
        results["figures"][key] = ext[key]["figure"]

    split = ext["split_ratio"]
    diff, cost, stab = ext["difficulty"], ext["cost_sensitive"], ext["stability"]

    print("  训练/测试划分比例（含 9:1，探索性对照）：")
    for r in split["ratios"]:
        print(f"    测试集 {r[0]:.0%}（训练 {r[1]} / 测试 {r[2]} 条）→ "
              f"决策树 {r[4]:.4f}±{r[5]:.4f}，随机森林 {r[6]:.4f}±{r[7]:.4f}；"
              f"1 条误判影响 {r[8]:.3f}%")
    print("  难度梯度：")
    print(f"    训练集只用 5% 时测试准确率 {diff['learning_curve'][0][3]:.4f}，"
          f"用 100% 时 {diff['learning_curve'][-1][3]:.4f}")
    full_k = next((k for k, acc in diff["feature_subset"] if acc == 1.0), None)
    if full_k is None:
        print("    各特征子集的平均测试准确率均低于 100%")
    else:
        print(f"    探索性对照中，前 {full_k} 个特征首次达到平均测试准确率 100%")
    noise10 = next(r[1] for r in diff["noise"] if abs(r[0] - 0.10) < 1e-9)
    print(f"    训练集标签噪声 10% 时，测试准确率降至 {noise10:.4f}")
    print("  代价敏感（训练集加 10% 噪声构造不完美模型）：")
    for ratio, best in cost["best"].items():
        default_cost = cost["default"][ratio]["cost"]
        print(f"    FN:FP={ratio}:1 → 最优阈值 {best['threshold']:.2f}，"
              f"漏判 {best['fn']}、误判 {best['fp']}，总代价 {best['cost']:.0f}"
              f"（默认阈值 0.5 时为 {default_cost:.0f}）")
    print("  结构稳定性（30 次不同随机划分）：")
    print(f"    叶节点数 {stab['leaves_mean']:.1f} ± {stab['leaves_std']:.1f}"
          f"（{stab['leaves_min']}~{stab['leaves_max']}），深度 {stab['depth_min']}~{stab['depth_max']}")
    print(f"    根节点最常选 {stab['root_top']}（{stab['root_top_ratio']:.0%}）；"
          f"前 3 特征集合 Jaccard 平均：单树 {stab['top3_jaccard_tree']:.2f}，"
          f"随机森林 {stab['top3_jaccard_rf']:.2f}")
    print(f"    特征重要性标准差：单树 {stab['importance_std_tree']:.4f}，"
          f"随机森林 {stab['importance_std_rf']:.4f}")

    # ------------------------------------------------------------------
    # 7. 汇总
    # ------------------------------------------------------------------
    section("7. 汇总")
    rows = []
    for criterion, name in STRATEGIES:
        t = results["tables"][f"tree_{criterion}"]
        rows.append([name, t["metrics"]["accuracy"], t["metrics"]["precision_macro"],
                     t["metrics"]["recall_macro"], t["metrics"]["f1_macro"]])
    rows.append(["随机森林", rf_m["accuracy"], rf_m["precision_macro"],
                 rf_m["recall_macro"], rf_m["f1_macro"]])
    for name, hand in hand_results.items():
        m = hand["metrics"]
        rows.append([name, m["accuracy"], m["precision_macro"],
                     m["recall_macro"], m["f1_macro"]])
    results["tables"]["summary"] = rows
    print(metrics.summary_table(rows))

    with open(OUTPUTS_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n所有图表与结果已保存到：{OUTPUTS_DIR}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="决策树 + 随机森林实验")
    parser.add_argument("--data", default=None, help="数据集文件路径（默认自动查找）")
    args = parser.parse_args()
    main(args.data)
