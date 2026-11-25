# -*- coding: utf-8 -*-
"""数据读取与预处理。

职责：读取 UCI 蘑菇数据集 → 处理缺失值 → 编码 → 划分训练/测试集。
本模块不涉及任何模型训练或绘图。
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

from .config import (
    CLASS_NAMES,
    FEATURES,
    COLUMNS,
    MISSING_TOKEN,
    RANDOM_STATE,
    TEST_SIZE,
)


def load_raw(data_path: Path) -> pd.DataFrame:
    """读取原始数据（无表头，'?' 表示缺失）。"""
    df = pd.read_csv(data_path, header=None, names=COLUMNS)
    return df.replace("?", np.nan)


def describe(df: pd.DataFrame) -> dict:
    """返回数据概况，用于打印和写报告。"""
    class_counts = df["class"].value_counts()
    missing = df.isna().sum()
    return {
        "rows": int(len(df)),
        "features": len(FEATURES),
        "class_counts": {
            "edible": int(class_counts.get("e", 0)),
            "poisonous": int(class_counts.get("p", 0)),
        },
        "missing": {k: int(v) for k, v in missing[missing > 0].items()},
    }


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """把 22 个类别特征和标签分离出来。

    缺失值作为独立类别 "missing" 参与建模（决策树可以直接处理）。
    返回值：X（字符串 DataFrame，保留原始类别取值）、y（0=可食，1=有毒）。
    """
    X = df[FEATURES].fillna(MISSING_TOKEN).astype(str)
    y = (df["class"] == "p").astype(int).to_numpy()
    return X, y


def split(X: pd.DataFrame, y: np.ndarray):
    """按 7:3 分层抽样划分训练集/测试集。"""
    return train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )


def encode_for_sklearn(X_train: pd.DataFrame, X_test: pd.DataFrame):
    """序数编码为基线；阈值分裂受类别排列影响，应与独热编码对照。"""
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X_tr = encoder.fit_transform(X_train)
    X_te = encoder.transform(X_test)
    return X_tr, X_te, encoder
