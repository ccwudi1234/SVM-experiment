# -*- coding: utf-8 -*-
"""实验一：难度梯度实验。

包含三组子实验，逐步"为难"模型：
  1. 学习曲线：训练集只用 5%~100% 的样本，看训练/测试准确率如何变化；
  2. 特征子集：只保留重要性前 k 个特征（k=1..22），看需要多少特征才能达到 100%；
  3. 标签噪声：把训练集 5%/10%/20%/30% 的标签随机翻转，看测试准确率如何下降。
"""
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from ..config import RANDOM_STATE
from ..data_loader import encode_for_sklearn
from .. import visualization


def _stratified_subsample(y, fraction, seed):
    """按类别分层抽样，保证两类比例不变。"""
    rng = np.random.default_rng(seed)
    idx = []
    for label in np.unique(y):
        pool = np.where(y == label)[0]
        take = max(1, int(round(len(pool) * fraction)))
        idx.extend(rng.choice(pool, size=take, replace=False).tolist())
    return np.array(sorted(idx))


def learning_curve(X, y, fractions=(0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.85, 1.0), seeds=5):
    """训练集比例 → 训练/测试准确率（测试集固定为 30% 留出）。"""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y)
    rows = []
    for frac in fractions:
        train_accs, test_accs = [], []
        for s in range(seeds):
            idx = _stratified_subsample(y_tr, frac, RANDOM_STATE + s)
            X_subset, X_test, _ = encode_for_sklearn(X_tr.iloc[idx], X_te)
            model = DecisionTreeClassifier(random_state=RANDOM_STATE).fit(X_subset, y_tr[idx])
            train_accs.append(model.score(X_subset, y_tr[idx]))
            test_accs.append(model.score(X_test, y_te))
        rows.append((float(frac), float(np.mean(train_accs)), float(np.std(train_accs)),
                     float(np.mean(test_accs)), float(np.std(test_accs))))
    return rows


def feature_subset(X, y, seeds=3):
    """保留重要性前 k 个特征 → 准确率。

    先在全部特征上训练一棵树，按该树给出的特征重要性排序，再逐个取前 k 个重训，
    这样能看出"几个特征就够用"。
    """
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y)
    X_tr, X_te, _ = encode_for_sklearn(X_tr, X_te)
    full = DecisionTreeClassifier(random_state=RANDOM_STATE).fit(X_tr, y_tr)
    order = np.argsort(full.feature_importances_)[::-1]

    rows = []
    for k in range(1, len(order) + 1):
        cols = order[:k]
        accs = []
        for s in range(seeds):
            model = DecisionTreeClassifier(random_state=RANDOM_STATE + s).fit(
                X_tr[:, cols], y_tr)
            accs.append(model.score(X_te[:, cols], y_te))
        rows.append((int(k), float(np.mean(accs))))
    return rows, [int(i) for i in order[:10]]


def noise_curve(X, y, ratios=(0.0, 0.05, 0.10, 0.20, 0.30), seeds=5):
    """训练集标签噪声比例 → 测试准确率。"""
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y)
    X_tr, X_te, _ = encode_for_sklearn(X_tr, X_te)
    rows = []
    for ratio in ratios:
        accs = []
        for s in range(seeds):
            rng = np.random.default_rng(RANDOM_STATE + s)
            y_noisy = y_tr.copy()
            if ratio > 0:
                idx = rng.choice(len(y_noisy), size=int(len(y_noisy) * ratio), replace=False)
                y_noisy[idx] = 1 - y_noisy[idx]
            model = DecisionTreeClassifier(random_state=RANDOM_STATE).fit(X_tr, y_noisy)
            accs.append(model.score(X_te, y_te))
        rows.append((float(ratio), float(np.mean(accs)), float(np.std(accs))))
    return rows


def run(X, y, output_dir):
    lc = learning_curve(X, y)
    fs, feat_order = feature_subset(X, y)
    noise = noise_curve(X, y)
    path = output_dir / "difficulty.png"
    visualization.plot_difficulty(lc, fs, noise, path)
    return {
        "learning_curve": lc,
        "feature_subset": fs,
        "feature_order": feat_order,
        "noise": noise,
        "figure": str(path),
    }
