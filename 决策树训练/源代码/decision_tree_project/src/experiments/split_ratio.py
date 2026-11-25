# -*- coding: utf-8 -*-
"""实验一：训练/测试划分比例的影响（含 9:1）。

本实验是四组扩展实验中的第一组：后续所有实验都基于 7:3 的划分，
因此先验证这个比例是否合理。

固定数据、固定模型，只改变"训练集/测试集"比例：
  9:1、8:2、7:3、6:4、5:5，
每种比例重复 10 次不同随机划分，观察：
  1. 决策树与随机森林的测试准确率如何变化；
  2. 测试集越小，1 条误判对准确率的影响有多大（评估"粒度"）。
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from ..config import RANDOM_STATE
from ..data_loader import encode_for_sklearn
from .. import visualization

RATIOS = (0.1, 0.2, 0.3, 0.4, 0.5)   # 测试集比例：9:1 ~ 5:5
SEEDS = 10


def run(X, y, output_dir):
    rows = []
    for ratio in RATIOS:
        tree_train, tree_test, rf_test = [], [], []
        for s in range(SEEDS):
            X_tr, X_te, y_tr, y_te = train_test_split(
                X, y, test_size=ratio, random_state=s, stratify=y)
            X_tr, X_te, _ = encode_for_sklearn(X_tr, X_te)
            tree = DecisionTreeClassifier(random_state=RANDOM_STATE).fit(X_tr, y_tr)
            tree_train.append(tree.score(X_tr, y_tr))
            tree_test.append(tree.score(X_te, y_te))

            rf = RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE).fit(X_tr, y_tr)
            rf_test.append(rf.score(X_te, y_te))
        n_train = len(X_tr)
        n_test = len(X_te)
        rows.append((
            float(ratio),
            n_train,
            n_test,
            float(np.mean(tree_train)),
            float(np.mean(tree_test)), float(np.std(tree_test)),
            float(np.mean(rf_test)), float(np.std(rf_test)),
            float(100.0 / n_test),          # 1 条误判对准确率的影响（百分点）
        ))

    path = output_dir / "split_ratio.png"
    visualization.plot_split_ratio(rows, path)
    return {"ratios": rows, "figure": str(path), "seeds": SEEDS}
