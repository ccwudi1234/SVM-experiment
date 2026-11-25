# -*- coding: utf-8 -*-
"""随机森林模型。

随机森林 = Bagging + 随机特征子空间：
  1. 对训练集做多次有放回抽样，每份样本训练一棵决策树；
  2. 每次节点分裂只在随机挑选的一部分特征中找最优划分；
  3. 预测时所有树投票。
这样能降低单棵树的方差，抑制过拟合；袋外（OOB）样本可用来估计泛化误差。
"""
from sklearn.ensemble import RandomForestClassifier

from ..config import RANDOM_STATE


def train(X_train, y_train, n_estimators: int = 100,
          oob_score: bool = True) -> RandomForestClassifier:
    """训练随机森林。"""
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        oob_score=oob_score,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    model.fit(X_train, y_train)
    return model


def oob_curve(X_train, y_train, ks=(1, 3, 5, 10, 20, 50, 100, 200)):
    """树的数量从少到多时，OOB 准确率的变化（用于画收敛曲线）。"""
    curve = []
    for k in ks:
        model = RandomForestClassifier(
            n_estimators=k, oob_score=True, random_state=RANDOM_STATE, n_jobs=1
        ).fit(X_train, y_train)
        curve.append((k, float(model.oob_score_)))
    return curve


def feature_importance(model: RandomForestClassifier, feature_names) -> list[tuple[str, float]]:
    """返回按重要性从高到低排序的特征列表。"""
    pairs = list(zip(feature_names, model.feature_importances_.tolist()))
    return sorted(pairs, key=lambda x: -x[1])
