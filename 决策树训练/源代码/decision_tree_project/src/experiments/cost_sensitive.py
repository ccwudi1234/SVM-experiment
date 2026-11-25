# -*- coding: utf-8 -*-
"""实验二：代价敏感与阈值分析。

背景：把"有毒"判成"可食"（漏判 FN）的代价远高于"可食"判成"有毒"（误判 FP）。
做法：
  1. 在干净数据上模型输出的是 0/1 硬概率，阈值分析没有意义；
     因此人为给训练集加 10% 标签噪声，构造一个"不完美"的模型；
  2. 用随机森林（多棵树投票）得到更平滑的有毒概率，
     扫描分类阈值 0.02~0.98，计算漏判数、误判数、精确率、召回率；
  3. 在验证集上按不同代价比选择阈值，冻结后评估测试集，
     与默认阈值 0.5 比较。
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from ..config import RANDOM_STATE
from ..data_loader import encode_for_sklearn
from .. import visualization

NOISE = 0.10                 # 训练集标签噪声比例（构造"不完美"模型）
COST_RATIOS = (1, 5, 10)     # 漏判代价 : 误判代价


def _confusion(pred, y_te):
    tp = int(((pred == 1) & (y_te == 1)).sum())
    fp = int(((pred == 1) & (y_te == 0)).sum())
    fn = int(((pred == 0) & (y_te == 1)).sum())
    tn = int(((pred == 0) & (y_te == 0)).sum())
    return tp, fp, fn, tn


def threshold_curve(X, y):
    """扫描阈值，返回 (阈值曲线, 各代价比下的最优阈值)。"""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y)
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_tr, y_tr, test_size=0.25, stratify=y_tr, random_state=RANDOM_STATE)
    X_tr, X_val, encoder = encode_for_sklearn(X_tr, X_val)
    X_te = encoder.transform(X_te)
    rng = np.random.default_rng(RANDOM_STATE)
    y_noisy = y_tr.copy()
    flip = rng.choice(len(y_tr), int(len(y_tr) * NOISE), replace=False)
    y_noisy[flip] = 1 - y_noisy[flip]
    # 用随机森林的投票比例作为"有毒概率"，比单棵树更平滑，阈值扫描才有意义
    model = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)
    model.fit(X_tr, y_noisy)
    proba = model.predict_proba(X_val)[:, 1]

    thresholds = np.round(np.arange(0.02, 0.99, 0.01), 2)
    rows = []
    for t in thresholds:
        pred = (proba >= t).astype(int)
        tp, fp, fn, tn = _confusion(pred, y_val)
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        rows.append((float(t), tp, fp, fn, tn, float(precision), float(recall)))

    best, default = {}, {}
    for ratio in COST_RATIOS:
        costs = [ratio * row[3] + 1 * row[2] for row in rows]   # FN 代价 ratio，FP 代价 1
        k = int(np.argmin(costs))
        best[ratio] = {
            "threshold": float(rows[k][0]),
            "cost": float(costs[k]),
            "fn": int(rows[k][3]),
            "fp": int(rows[k][2]),
            "recall": float(rows[k][6]),
            "precision": float(rows[k][5]),
        }
        # 默认阈值 0.5 的对照
        k05 = int(np.argmin(np.abs(thresholds - 0.5)))
        default[ratio] = {
            "cost": float(costs[k05]),
            "fn": int(rows[k05][3]),
            "fp": int(rows[k05][2]),
        }

    validation_best = {k: dict(v) for k, v in best.items()}
    test_proba = model.predict_proba(X_te)[:, 1]
    for ratio in COST_RATIOS:
        for target, threshold in ((best[ratio], best[ratio]["threshold"]), (default[ratio], 0.5)):
            tp, fp, fn, tn = _confusion((test_proba >= threshold).astype(int), y_te)
            target.update(cost=float(ratio * fn + fp), fn=fn, fp=fp,
                          recall=tp / max(1, tp + fn), precision=tp / max(1, tp + fp))
    return {
        "validation_best": validation_best,
        "selection": "validation only; frozen thresholds evaluated on test",
        "curve": rows,
        "best": best,
        "default": default,
        "noise": NOISE,
        "cost_ratios": list(COST_RATIOS),
        "clean_accuracy": float(RandomForestClassifier(
            n_estimators=100, random_state=RANDOM_STATE).fit(X_tr, y_tr).score(X_te, y_te)),
        "noisy_accuracy": float(np.mean((test_proba >= 0.5).astype(int) == y_te)),
        "prediction_rule": "poison probability >= threshold; ties classified as poison",
        "n_test": int(len(y_te)),
        "n_poison": int((y_te == 1).sum()),
    }


def run(X, y, output_dir):
    result = threshold_curve(X, y)
    path = output_dir / "cost_sensitive.png"
    visualization.plot_cost_sensitive(result["curve"], result["validation_best"], path)
    result["figure"] = str(path)
    return result
