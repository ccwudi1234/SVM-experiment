# -*- coding: utf-8 -*-
"""决策树模型（两种特征选择策略）。

- criterion="gini"    ：CART 算法，用基尼指数选择划分特征
- criterion="entropy" ：用信息熵（信息增益）选择划分特征，对应 ID3 的思路

注意：scikit-learn 的树本身是 CART 实现，对类别特征按取值做二分裂；
"entropy" 只是把分裂准则换成信息熵，并不是原生的多路分裂 ID3。
"""
from sklearn.tree import DecisionTreeClassifier

from ..config import RANDOM_STATE


def train(X_train, y_train, criterion: str = "gini") -> DecisionTreeClassifier:
    """训练一棵决策树。"""
    model = DecisionTreeClassifier(criterion=criterion, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    return model


def train_shallow(X_train, y_train, criterion: str = "gini", max_depth: int = 2):
    """训练一棵限深的决策树，专门用于画图（深树画出来看不清）。"""
    model = DecisionTreeClassifier(
        criterion=criterion, max_depth=max_depth, random_state=RANDOM_STATE
    )
    model.fit(X_train, y_train)
    return model


def train_with_depth(X_train, y_train, max_depth: int):
    """指定树深训练（用于“深度-过拟合”实验）。"""
    model = DecisionTreeClassifier(max_depth=max_depth, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    return model


def train_with_alpha(X_train, y_train, ccp_alpha: float):
    """指定代价复杂度参数训练（用于“后剪枝”实验）。"""
    model = DecisionTreeClassifier(ccp_alpha=ccp_alpha, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)
    return model
